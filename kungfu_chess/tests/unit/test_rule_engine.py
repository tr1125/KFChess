"""These is_legal_move tests check movement legality against the real
rules of chess, not against any specific fixture - they validate the
design on its own terms. settle_clear_move / settle_airborne_capture /
apply_promotion_choice tests cover RuleEngine's settlement
responsibilities once the real-time arbiter has already classified a due
move as clear or as an airborne capture (arbiter classification itself
is tested in test_real_time_arbiter.py).

Board fixtures are still written as plain token grids ("wR", ".") for
readability - board_from()/piece_from_token() below convert them into
real Piece objects, since Board now stores Piece | None rather than
strings.
"""

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.rules.piece_rules import PieceRules, PromotionRule, default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine


def make_engine():
    return RuleEngine(default_piece_rules())


def piece_from_token(token):
    return Piece(color=token[0], kind=token[1])


def board_from(rows):
    return Board([[None if cell == "." else piece_from_token(cell) for cell in row] for row in rows])


def empty_board(size=5):
    return board_from([["."] * size for _ in range(size)])


def signature(piece):
    return None if piece is None else (piece.color, piece.kind)


def legal(engine, token, board, from_rc, to_rc):
    return engine.is_legal_move(piece_from_token(token), board, Position(*from_rc), Position(*to_rc))


# --- King: one square, any direction ---

def test_king_one_step_orthogonal_is_legal():
    assert legal(make_engine(), "wK", empty_board(), (2, 2), (2, 3))


def test_king_one_step_diagonal_is_legal():
    assert legal(make_engine(), "wK", empty_board(), (2, 2), (3, 3))


def test_king_two_squares_is_illegal():
    assert not legal(make_engine(), "wK", empty_board(), (2, 2), (2, 4))


# --- Rook: any distance, orthogonal only ---

def test_rook_straight_line_is_legal():
    assert legal(make_engine(), "wR", empty_board(), (0, 0), (0, 4))


def test_rook_diagonal_is_illegal():
    assert not legal(make_engine(), "wR", empty_board(), (0, 0), (2, 2))


# --- Bishop: any distance, diagonal only ---

def test_bishop_diagonal_is_legal():
    assert legal(make_engine(), "wB", empty_board(), (0, 0), (3, 3))


def test_bishop_straight_line_is_illegal():
    assert not legal(make_engine(), "wB", empty_board(), (0, 0), (0, 3))


# --- Queen: any distance, straight or diagonal ---

def test_queen_straight_line_is_legal():
    assert legal(make_engine(), "wQ", empty_board(), (1, 1), (1, 4))


def test_queen_diagonal_is_legal():
    assert legal(make_engine(), "wQ", empty_board(), (1, 1), (3, 3))


def test_queen_knight_shape_is_illegal():
    assert not legal(make_engine(), "wQ", empty_board(), (1, 1), (3, 2))


# --- Knight: L-shape only ---

def test_knight_l_shape_is_legal():
    assert legal(make_engine(), "wN", empty_board(), (2, 2), (0, 1))


def test_knight_straight_line_is_illegal():
    assert not legal(make_engine(), "wN", empty_board(), (2, 2), (2, 4))


def test_knight_diagonal_is_illegal():
    assert not legal(make_engine(), "wN", empty_board(), (2, 2), (4, 4))


# --- Off-board destinations are never legal ---

def test_destination_off_board_is_illegal():
    assert not legal(make_engine(), "wR", empty_board(), (0, 0), (0, 10))


# --- Blocking: sliding pieces cannot move through another piece ---

def test_rook_cannot_move_through_a_blocker():
    rows = [
        ["wR", ".", "wN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    assert not legal(make_engine(), "wR", board_from(rows), (0, 0), (0, 4))


def test_rook_can_capture_enemy_piece_at_blocker_position():
    rows = [
        ["wR", ".", "bN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    assert legal(make_engine(), "wR", board_from(rows), (0, 0), (0, 2))


def test_rook_cannot_land_on_own_piece():
    rows = [
        ["wR", ".", "wN", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", ".", "."],
    ]
    assert not legal(make_engine(), "wR", board_from(rows), (0, 0), (0, 2))


def test_bishop_cannot_move_through_a_blocker():
    rows = [
        ["wB", ".", ".", ".", "."],
        [".", "wN", ".", ".", "."],
        [".", ".", ".", ".", "."],
        [".", ".", ".", "bN", "."],
        [".", ".", ".", ".", "."],
    ]
    assert not legal(make_engine(), "wB", board_from(rows), (0, 0), (3, 3))


def test_knight_can_jump_over_blockers():
    rows = [
        ["wN", "bN", "."],
        ["bN", "bN", "."],
        [".", ".", "."],
    ]
    assert legal(make_engine(), "wN", board_from(rows), (0, 0), (2, 1))


# --- Capture rules apply the same way to every piece ---

def test_cannot_capture_own_color():
    rows = [["wK", "wN"], [".", "."]]
    assert not legal(make_engine(), "wK", board_from(rows), (0, 0), (0, 1))


def test_can_capture_enemy_color():
    rows = [["wK", "bN"], [".", "."]]
    assert legal(make_engine(), "wK", board_from(rows), (0, 0), (0, 1))


# --- Pawn: direction depends on color, move and capture are different shapes ---

def test_white_pawn_moves_one_cell_forward_is_legal():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    assert legal(make_engine(), "wP", board_from(rows), (1, 1), (0, 1))


def test_white_pawn_cannot_move_two_cells_from_non_start_row():
    rows = [[".", ".", "."], [".", ".", "."], [".", "wP", "."], [".", ".", "."], [".", ".", "."]]
    assert not legal(make_engine(), "wP", board_from(rows), (2, 1), (0, 1))


def test_white_pawn_cannot_move_forward_onto_occupied_cell():
    rows = [[".", "bN", "."], [".", "wP", "."], [".", ".", "."]]
    assert not legal(make_engine(), "wP", board_from(rows), (1, 1), (0, 1))


def test_white_pawn_captures_diagonally():
    rows = [["bN", ".", "."], [".", "wP", "."], [".", ".", "."]]
    assert legal(make_engine(), "wP", board_from(rows), (1, 1), (0, 0))


def test_white_pawn_cannot_capture_diagonally_own_color():
    rows = [["wN", ".", "."], [".", "wP", "."], [".", ".", "."]]
    assert not legal(make_engine(), "wP", board_from(rows), (1, 1), (0, 0))


def test_white_pawn_cannot_move_diagonally_to_empty_cell():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    assert not legal(make_engine(), "wP", board_from(rows), (1, 1), (0, 0))


def test_black_pawn_moves_one_cell_forward_is_legal():
    rows = [[".", ".", "."], [".", "bP", "."], [".", ".", "."]]
    assert legal(make_engine(), "bP", board_from(rows), (1, 1), (2, 1))


def test_black_pawn_captures_diagonally():
    rows = [[".", "bP", "."], ["wN", ".", "."], [".", ".", "."]]
    assert legal(make_engine(), "bP", board_from(rows), (0, 1), (1, 0))


def test_black_pawn_cannot_move_diagonally_to_empty_cell():
    rows = [[".", "bP", "."], [".", ".", "."], [".", ".", "."]]
    assert not legal(make_engine(), "bP", board_from(rows), (0, 1), (1, 0))


# --- Pawn: two-square initial push ---

def test_white_pawn_can_move_two_cells_from_start_row():
    rows = [[".", ".", "."], [".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    assert legal(make_engine(), "wP", board_from(rows), (2, 1), (0, 1))


def test_white_pawn_two_cell_move_blocked_by_piece_on_path():
    rows = [[".", ".", "."], [".", "bR", "."], [".", "wP", "."], [".", ".", "."]]
    assert not legal(make_engine(), "wP", board_from(rows), (2, 1), (0, 1))


def test_black_pawn_can_move_two_cells_from_start_row():
    rows = [[".", ".", "."], [".", "bP", "."], [".", ".", "."], [".", ".", "."]]
    assert legal(make_engine(), "bP", board_from(rows), (1, 1), (3, 1))


# --- settle_clear_move: captures, promotion registration, history, game-over ---

def test_settle_clear_move_records_a_normal_move():
    board = board_from([["wR", "."]])
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    ends_game = engine.settle_clear_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert ends_game is False
    assert signature(board.get(0, 1)) == ("w", "R")
    assert state.move_history() == ["Rb1"]
    assert not state.is_game_over()


def test_settle_clear_move_credits_capture_and_signals_game_over_on_king():
    board = board_from([["wQ", "bK"]])
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    ends_game = engine.settle_clear_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert ends_game is True
    assert state.move_history() == ["Qxb1#"]
    assert state.scores() == {"w": 0, "b": 0}  # king is worth 0
    assert state.is_game_over()


def test_settle_clear_move_credits_mover_color_on_capture():
    board = board_from([["wQ", "bR"]])
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    engine.settle_clear_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert state.scores() == {"w": 5, "b": 0}  # rook is worth 5


def test_settle_clear_move_auto_promotes_to_the_default_while_keeping_a_pending_choice():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    board = board_from(rows)
    state = GameState()
    engine = make_engine()
    mover = board.get(1, 1)
    engine.settle_clear_move(board, state, mover, Position(1, 1), Position(0, 1))

    assert signature(board.get(0, 1)) == ("w", "Q")  # auto-promoted to the rule's default immediately
    pending = state.get_pending_promotion(Position(0, 1))
    assert pending.color == "w"
    assert pending.choices == ("Q", "R", "B", "N")  # still overridable
    assert state.move_history() == ["b3", "b3=Q"]


def test_settle_clear_move_does_not_schedule_promotion_for_non_triggering_move():
    board = board_from([["wR", "."]])
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    engine.settle_clear_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert not state.has_pending_promotion()


def test_settle_clear_move_honors_injected_custom_piece_rules():
    """A custom PieceRules (e.g. knight-on-4th-rank) changes what
    triggers a promotion, and to what it auto-promotes by default, without
    any change to RuleEngine itself. This rule omits default_choice, so
    the default falls back to choices[0] ("Q").
    """
    rows = [["wK", ".", "bK"], [".", ".", "."], [".", "wN", "."], [".", ".", "."]]
    board = board_from(rows)
    state = GameState()
    custom_rules = PieceRules(
        movement_patterns={}, promotion_rules=[PromotionRule("N", "w", 0, ("Q", "R"))], piece_values={"N": 3}
    )
    engine = RuleEngine(custom_rules)
    mover = board.get(2, 1)
    engine.settle_clear_move(board, state, mover, Position(2, 1), Position(0, 1))

    assert signature(board.get(0, 1)) == ("w", "Q")  # auto-promoted to the fallback default
    pending = state.get_pending_promotion(Position(0, 1))
    assert pending is not None
    assert pending.choices == ("Q", "R")


# --- settle_clear_move: an enemy-airborne destination is not a capture yet ---

def test_settle_clear_move_does_not_record_a_capture_when_destination_is_enemy_airborne():
    """Landing on an enemy currently AIRBORNE is a normal, quiet arrival -
    it's "safe" (see UI_PLAN.md Sec 2) until that piece's own landing
    instant, which is a separate mechanic (settle_airborne_capture,
    triggered from GameEngine._land_due_jumps)."""
    board = board_from([["wR", "bN"]])
    board.get(0, 1).state = PieceState.AIRBORNE
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    ends_game = engine.settle_clear_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert ends_game is False
    assert signature(board.get(0, 1)) == ("w", "R")  # overwrites the stale grid slot regardless
    assert state.move_history() == ["Rb1"]  # a quiet move, not "Rxb1"
    assert state.scores() == {"w": 0, "b": 0}  # nothing captured


# --- settle_stopped_move: a multi-cell move blocked mid-path, without touching the board ---

def test_settle_stopped_move_records_history_without_moving_the_piece():
    board = board_from([["wR", ".", "."]])
    state = GameState()
    engine = make_engine()
    mover = board.get(0, 0)
    board.apply_move(0, 0, 0, 1)  # simulate one already-completed leg
    engine.settle_stopped_move(board, state, mover, Position(0, 0), Position(0, 1))
    assert signature(board.get(0, 1)) == ("w", "R")  # untouched - it was already there
    assert state.move_history() == ["Rb1"]
    assert state.scores() == {"w": 0, "b": 0}
    assert not state.is_game_over()


def test_settle_stopped_move_still_checks_for_a_promotion_trigger():
    rows = [["wK", ".", "bK"], [".", "wP", "."]]
    board = board_from(rows)
    state = GameState()
    engine = make_engine()
    mover = board.get(1, 1)
    board.apply_move(1, 1, 0, 1)  # simulate the pawn having already reached the promotion rank
    engine.settle_stopped_move(board, state, mover, Position(1, 1), Position(0, 1))
    assert signature(board.get(0, 1)) == ("w", "Q")  # auto-promoted, same as settle_clear_move


# --- settle_airborne_capture ---

def test_settle_airborne_capture_records_comment_and_removes_attacker():
    board = board_from([["wR", "bN"]])
    state = GameState()
    engine = make_engine()
    attacker, defender = board.get(0, 0), board.get(0, 1)
    engine.settle_airborne_capture(board, state, attacker, defender, Position(0, 1), Position(0, 0))
    assert state.move_history() == ["{wR captured mid-air by bN at b1}"]
    assert board.get(0, 0) is None  # the arriving wR was removed, not moved
    assert signature(board.get(0, 1)) == ("b", "N")  # defender stays put


def test_settle_airborne_capture_credits_the_airborne_defender_not_the_arriver():
    board = board_from([["wR", "bN"]])
    state = GameState()
    engine = make_engine()
    attacker, defender = board.get(0, 0), board.get(0, 1)
    engine.settle_airborne_capture(board, state, attacker, defender, Position(0, 1), Position(0, 0))
    assert state.scores() == {"w": 0, "b": 5}  # bN captures wR (worth 5) mid-air


def test_settle_airborne_capture_reinstates_the_defender_when_attacker_overwrote_its_cell():
    """The realistic call shape from GameEngine._land_due_jumps: the
    attacker already settled onto the defender's home cell (from_position
    == position) sometime during the flight, overwriting it on the board
    - landing must put the defender back."""
    board = board_from([["bN"]])  # attacker now sits where the defender (never removed from the grid) lands
    state = GameState()
    engine = make_engine()
    attacker = board.get(0, 0)
    defender = Piece(color="w", kind="K")
    engine.settle_airborne_capture(board, state, attacker, defender, Position(0, 0), Position(0, 0))
    assert signature(board.get(0, 0)) == ("w", "K")  # defender reclaims its cell


def test_settle_airborne_capture_ends_the_game_on_a_king_capture():
    board = board_from([["bK"]])
    state = GameState()
    engine = make_engine()
    attacker = board.get(0, 0)
    defender = Piece(color="w", kind="N")
    ends_game = engine.settle_airborne_capture(board, state, attacker, defender, Position(0, 0), Position(0, 0))
    assert ends_game is True
    assert state.is_game_over()


# --- path_for_move ---

def test_path_for_move_for_a_slide_is_the_full_cell_by_cell_route():
    engine = make_engine()
    board = empty_board()
    path = engine.path_for_move(piece_from_token("wR"), board, Position(0, 0), Position(0, 3))
    assert path == [Position(0, 1), Position(0, 2), Position(0, 3)]


def test_path_for_move_for_a_knight_is_a_single_leg_regardless_of_distance():
    engine = make_engine()
    board = empty_board()
    path = engine.path_for_move(piece_from_token("wN"), board, Position(2, 2), Position(0, 1))
    assert path == [Position(0, 1)]


def test_path_for_move_for_a_pawn_double_step_is_two_legs():
    rows = [[".", "."], [".", "."], ["wP", "."], [".", "."]]  # height=4, white start row = 4-2=2
    board = board_from(rows)
    engine = make_engine()
    path = engine.path_for_move(piece_from_token("wP"), board, Position(2, 0), Position(0, 0))
    assert path == [Position(1, 0), Position(0, 0)]


# --- apply_promotion_choice ---

def test_apply_promotion_choice_replaces_piece_kind_and_records_history():
    board = board_from([["wK", "wP", ".", "bK"]])
    state = GameState()
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"), board.get(0, 1))
    engine = make_engine()

    applied = engine.apply_promotion_choice(board, state, Position(0, 1), "Q")

    assert applied is True
    assert signature(board.get(0, 1)) == ("w", "Q")
    assert not state.has_pending_promotion()
    assert state.move_history() == ["b1=Q"]


def test_apply_promotion_choice_rejects_a_choice_outside_configured_options():
    board = board_from([["wK", "wP", ".", "bK"]])
    state = GameState()
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"), board.get(0, 1))
    engine = make_engine()

    applied = engine.apply_promotion_choice(board, state, Position(0, 1), "K")

    assert applied is False
    assert signature(board.get(0, 1)) == ("w", "P")
    assert state.has_pending_promotion()


def test_apply_promotion_choice_is_a_no_op_when_nothing_pending_there():
    board = board_from([["wP"]])
    state = GameState()
    engine = make_engine()

    applied = engine.apply_promotion_choice(board, state, Position(0, 0), "Q")

    assert applied is False
    assert signature(board.get(0, 0)) == ("w", "P")


def test_apply_promotion_choice_is_a_no_op_when_the_pending_piece_has_since_moved_away():
    """position alone is a stale key once the promoted piece moves on -
    the square it was scheduled at may now be empty. Resolving against
    it anyway must not crash (see Board.promote, which assumes a piece
    is there)."""
    board = board_from([["wK", "wQ", ".", "bK"]])
    state = GameState()
    engine = make_engine()
    promoted = board.get(0, 1)
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"), promoted)
    board.apply_move(0, 1, 0, 2)  # the promoted piece moves on; (0, 1) is now empty

    applied = engine.apply_promotion_choice(board, state, Position(0, 1), "N")

    assert applied is False
    assert signature(board.get(0, 2)) == ("w", "Q")  # unaffected
    assert state.has_pending_promotion()  # left in place, same as an invalid-choice no-op


def test_apply_promotion_choice_is_a_no_op_when_a_different_piece_now_occupies_the_square():
    """The bug this guards against isn't just a crash - if some other
    piece has since landed on the stale square, resolving the pending
    choice against `position` alone would silently rewrite that
    unrelated piece's kind instead of no-op'ing."""
    board = board_from([["wK", "wQ", ".", "bK"]])
    state = GameState()
    engine = make_engine()
    promoted = board.get(0, 1)
    state.schedule_promotion(Position(0, 1), "w", ("Q", "R", "B", "N"), promoted)
    board.apply_move(0, 1, 0, 2)  # the promoted piece moves on
    board.place(0, 1, piece_from_token("bR"))  # an unrelated piece now sits at the stale square

    applied = engine.apply_promotion_choice(board, state, Position(0, 1), "N")

    assert applied is False
    assert signature(board.get(0, 1)) == ("b", "R")  # unrelated piece left untouched
