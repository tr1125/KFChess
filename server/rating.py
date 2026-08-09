"""ELO rating updates + King-vs-King (insufficient material) draw
detection (Stage 3 - see KFChess_Server_Plan.md Sec 0).

is_king_vs_king is a pure board check, deliberately kept outside
GameEngine/RuleEngine's automatic settle path: several existing test
boards across kungfu_chess/tests/ are bare King-vs-King fixtures used to
test unrelated things, and wiring this in there would make those tests
freeze on their very first move. Instead this is called explicitly by
Room (server/rooms.py), which then calls the engine's own additive,
opt-in GameEngine.force_draw() - so nothing here ever touches the board
or game state directly.
"""

from kungfu_chess.rules.piece_rules import KING_TYPE

from server import config, db, protocol


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def updated_rating(rating, expected, actual_score, k_factor=None):
    k = k_factor if k_factor is not None else config.K_FACTOR
    return round(rating + k * (actual_score - expected))


def is_king_vs_king(board_rows):
    """True if the only pieces left on the board (either color) are
    kings - the sole automatic draw condition in this project (no other
    insufficient-material case, no stalemate/move-limit logic).
    """
    pieces = [piece for row in board_rows for piece in row if piece is not None]
    return bool(pieces) and all(piece.kind == KING_TYPE for piece in pieces)


class RatingService:
    def __init__(self, session):
        self._session = session

    def finalize_game(self, white_username, black_username, result):
        """result: one of protocol.RESULT_WHITE_WINS/RESULT_BLACK_WINS/
        RESULT_DRAW. Computes each player's new rating via the standard
        ELO formula, persists it, and returns {"white": new_rating,
        "black": new_rating} for the outbound game_ended message.
        """
        white = db.get_user(self._session, white_username)
        black = db.get_user(self._session, black_username)

        white_expected = expected_score(white.rating, black.rating)
        black_expected = expected_score(black.rating, white.rating)

        if result == protocol.RESULT_DRAW:
            white_score, black_score = 0.5, 0.5
            white_outcome, black_outcome = db.OUTCOME_DRAW, db.OUTCOME_DRAW
        elif result == protocol.RESULT_WHITE_WINS:
            white_score, black_score = 1.0, 0.0
            white_outcome, black_outcome = db.OUTCOME_WIN, db.OUTCOME_LOSS
        else:
            white_score, black_score = 0.0, 1.0
            white_outcome, black_outcome = db.OUTCOME_LOSS, db.OUTCOME_WIN

        new_white_rating = updated_rating(white.rating, white_expected, white_score)
        new_black_rating = updated_rating(black.rating, black_expected, black_score)

        db.update_after_game(self._session, white_username, new_white_rating, white_outcome)
        db.update_after_game(self._session, black_username, new_black_rating, black_outcome)

        return {"white": new_white_rating, "black": new_black_rating}