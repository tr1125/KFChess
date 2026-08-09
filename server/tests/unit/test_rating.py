from kungfu_chess.model.piece import Piece

from server import db, protocol
from server.rating import RatingService, expected_score, is_king_vs_king, updated_rating


# --- expected_score / updated_rating (pure ELO math) ---

def test_expected_score_is_half_for_equal_ratings():
    assert expected_score(1500, 1500) == 0.5


def test_updated_rating_worked_example_winner():
    # 1500 vs 1500, K=32, winner -> 1516 (see KFChess_Server_Plan.md's history).
    assert updated_rating(1500, expected_score(1500, 1500), 1, k_factor=32) == 1516


def test_updated_rating_worked_example_loser():
    assert updated_rating(1500, expected_score(1500, 1500), 0, k_factor=32) == 1484


def test_updated_rating_defaults_to_config_k_factor():
    assert updated_rating(1500, 0.5, 1) == 1516


# --- is_king_vs_king ---

def _piece(color, kind):
    return Piece(color=color, kind=kind, cell=None)


def test_is_king_vs_king_true_for_bare_kings():
    rows = [[_piece("b", "K"), None], [None, _piece("w", "K")]]
    assert is_king_vs_king(rows) is True


def test_is_king_vs_king_false_when_another_piece_remains():
    rows = [[_piece("b", "K"), None], [_piece("w", "P"), _piece("w", "K")]]
    assert is_king_vs_king(rows) is False


def test_is_king_vs_king_false_for_an_empty_board():
    rows = [[None, None], [None, None]]
    assert is_king_vs_king(rows) is False


# --- RatingService.finalize_game ---

def make_service_with_users(white_rating=1200, black_rating=1200):
    # Seed ratings by writing the User rows directly - db.update_after_game
    # is what's under test (via finalize_game) and also bumps the
    # win/loss/draw counters, so using it here to seed data would
    # corrupt the very counts these tests assert on.
    session = db.create_session_factory("sqlite:///:memory:")()
    db.create_user(session, "alice", "hash")
    db.create_user(session, "bob", "hash")
    db.get_user(session, "alice").rating = white_rating
    db.get_user(session, "bob").rating = black_rating
    session.commit()
    return RatingService(session), session


def test_finalize_game_white_wins_updates_both_ratings_and_persists():
    service, session = make_service_with_users(1500, 1500)

    result = service.finalize_game("alice", "bob", protocol.RESULT_WHITE_WINS)

    assert result == {"white": 1516, "black": 1484}
    assert db.get_user(session, "alice").rating == 1516
    assert db.get_user(session, "bob").rating == 1484
    assert db.get_user(session, "alice").wins == 1
    assert db.get_user(session, "bob").losses == 1


def test_finalize_game_black_wins_updates_both_ratings():
    service, session = make_service_with_users(1500, 1500)

    result = service.finalize_game("alice", "bob", protocol.RESULT_BLACK_WINS)

    assert result == {"white": 1484, "black": 1516}
    assert db.get_user(session, "bob").wins == 1
    assert db.get_user(session, "alice").losses == 1


def test_finalize_game_draw_updates_both_ratings_towards_each_other():
    service, session = make_service_with_users(1400, 1600)

    result = service.finalize_game("alice", "bob", protocol.RESULT_DRAW)

    # expected_score(1400, 1600) ~= 0.24, S=0.5 -> rating moves up for the
    # lower-rated player and down for the higher-rated one.
    assert result["white"] > 1400
    assert result["black"] < 1600
    assert db.get_user(session, "alice").draws == 1
    assert db.get_user(session, "bob").draws == 1


def test_finalize_game_draw_between_equal_ratings_is_a_no_op():
    service, session = make_service_with_users(1200, 1200)

    result = service.finalize_game("alice", "bob", protocol.RESULT_DRAW)

    assert result == {"white": 1200, "black": 1200}