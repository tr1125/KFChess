"""End-to-end tests of GameEngine wiring model/rules/realtime together,
working entirely in board cell coordinates. Pixel-to-cell mapping is
covered separately in test_board_mapper.py / test_controller.py.
"""

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import MotionTracker
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def signature(piece):
    return None if piece is None else (piece.color, piece.kind)


def sig_row(row):
    return [signature(piece) for piece in row]


def sig_rows(rows):
    return [sig_row(row) for row in rows]


def make_engine(rows, **kwargs):
    board = board_from(rows)
    rule_engine = RuleEngine(default_piece_rules())
    engine = GameEngine(board, rule_engine, **kwargs)
    return engine, board


# --- selection and click behavior ---

def test_select_piece_and_move_settles_after_wait():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(1, 1)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, None], [None, ("w", "K"), None], [None, None, None]]


def test_click_empty_cell_does_not_select():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(1, 1)
    engine.click(2, 2)
    engine.wait(1000)
    assert signature(board.get(0, 0)) == ("w", "K")


def test_click_outside_board_is_ignored():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(3, 0)
    engine.click(-1, 0)
    assert signature(board.get(0, 0)) == ("w", "K")


def test_clicking_another_friendly_piece_replaces_selection():
    rows = [["wR", ".", "wK"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)  # select wR
    engine.click(0, 2)  # reselect wK instead
    engine.click(1, 2)  # move wK down
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[("w", "R"), None, None], [None, None, ("w", "K")]]


def test_move_not_yet_settled_before_duration_elapses():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(1, 1)
    engine.wait(1)
    assert signature(board.get(0, 0)) == ("w", "K")


# --- duration proportional to distance ---

def test_multi_cell_slide_not_settled_just_before_duration_elapses():
    rows = [["wR", ".", ".", "."], [".", ".", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 3)
    engine.wait(2999)
    assert signature(board.get(0, 0)) == ("w", "R")


def test_two_cell_move_before_and_after_arrival():
    rows = [["wR", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(1000)
    assert board.get(0, 2) is None
    engine.wait(1000)
    assert signature(board.get(0, 2)) == ("w", "R")


def test_multi_cell_slide_settled_once_duration_elapses():
    rows = [["wR", ".", ".", "."], [".", ".", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 3)
    engine.wait(3000)
    assert sig_row(board.rows()[0]) == [None, None, None, ("w", "R")]


def test_illegal_shape_move_is_never_scheduled_even_after_waiting():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(2, 2)  # diagonal - illegal for a rook
    engine.wait(5000)
    assert signature(board.get(0, 0)) == ("w", "R")


# --- no redirecting a piece mid-route; no cooldown after arrival ---

def test_piece_cannot_be_reselected_while_still_in_transit():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(500)
    engine.click(0, 0)  # attempt to reselect the moving rook - ignored
    engine.click(0, 1)
    engine.wait(1500)
    assert sig_rows(board.rows()) == [[None, None, ("w", "R")], [None, None, None]]


def test_piece_can_move_again_immediately_after_arrival_no_cooldown():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    engine.click(0, 2)
    engine.click(1, 2)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, None], [None, None, ("w", "R")]]


# --- advanced real-time interaction cases ---

def test_enemy_collision_capture_on_arrival():
    rows = [["wR", ".", "bK"], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R")]


def test_premove_is_blocked_while_enemy_is_in_transit():
    rows = [["bR", ".", "."], [".", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.click(0, 0)  # select bR
    engine.click(2, 0)  # request bR -> (2, 0)
    engine.wait(500)
    engine.click(2, 2)  # select wK
    engine.click(1, 1)  # attempt to move wK while bR still in flight - blocked
    engine.wait(2000)
    assert sig_rows(board.rows()) == [
        [None, None, None],
        [None, None, None],
        [("b", "R"), None, ("w", "K")],
    ]


def test_friendly_piece_at_destination_cancels_in_transit_move():
    rows = [["wR", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.click(1, 2)  # select wK
    engine.click(0, 2)  # request wK -> (0, 2)
    engine.click(0, 0)  # select wR
    engine.click(0, 2)  # request wR -> (0, 2), same destination as wK
    engine.wait(2000)
    assert sig_rows(board.rows()) == [[("w", "R"), None, ("w", "K")], [None, None, None]]


def test_movement_conflict_first_registered_piece_wins_destination():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(2, 0)  # wR -> (2, 0), registered first
    engine.click(2, 2)  # select wK
    engine.click(2, 0)  # wK -> (2, 0), same destination, registered second
    engine.wait(2000)
    assert sig_rows(board.rows()) == [
        [None, None, None],
        [None, None, None],
        [("w", "R"), None, ("w", "K")],
    ]


# --- game-over on king capture ---

def test_capturing_enemy_king_ends_the_game():
    rows = [["wR", ".", "bK"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    assert engine.is_game_over()
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R")]


def test_move_commands_ignored_after_game_over():
    rows = [["wR", ".", "bK"], [".", "wK", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    assert engine.is_game_over()
    engine.click(1, 1)
    engine.click(0, 1)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, ("w", "R")], [None, ("w", "K"), None]]


# --- pawn promotion and two-square initial push ---

def test_white_pawn_reaching_row_zero_auto_promotes_to_queen_by_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(1, 1)
    engine.click(0, 1)
    engine.wait(1000)
    assert signature(board.get(0, 1)) == ("w", "Q")
    assert engine.pending_promotions() == [{"row": 0, "col": 1, "color": "w", "choices": ("Q", "R", "B", "N")}]


def test_choose_promotion_can_override_the_auto_promoted_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(1, 1)
    engine.click(0, 1)
    engine.wait(1000)
    assert signature(board.get(0, 1)) == ("w", "Q")  # auto-promoted first

    engine.choose_promotion(0, 1, "N")
    assert signature(board.get(0, 1)) == ("w", "N")  # then overridden
    assert not engine.pending_promotions()
    assert engine.move_history()[-2:] == ["b3=Q", "b3=N"]


def test_other_moves_are_not_blocked_while_a_promotion_choice_is_still_open():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "bR"], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(1, 1)
    engine.click(0, 1)
    engine.wait(1000)  # wP auto-promotes to wQ; a choice is still open

    engine.click(1, 3)  # select bR
    engine.click(1, 2)  # request bR -> (1, 2) - not blocked by the open promotion choice
    engine.wait(1000)

    assert signature(board.get(1, 2)) == ("b", "R")
    assert engine.pending_promotions()  # the choice is still open, unresolved


def test_choose_promotion_with_invalid_choice_is_a_no_op_and_keeps_the_auto_promoted_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(1, 1)
    engine.click(0, 1)
    engine.wait(1000)
    engine.choose_promotion(0, 1, "K")
    assert signature(board.get(0, 1)) == ("w", "Q")  # still the auto-promoted default
    pending = engine.pending_promotions()
    assert pending == [{"row": 0, "col": 1, "color": "w", "choices": ("Q", "R", "B", "N")}]


def test_black_pawn_reaching_last_row_auto_promotes_to_queen_by_default():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", ".", ".", "."],
        [".", "bP", ".", "."],
        [".", ".", ".", "."],
    ]
    engine, board = make_engine(rows)
    engine.click(2, 1)
    engine.click(3, 1)
    engine.wait(1000)
    assert signature(board.get(3, 1)) == ("b", "Q")
    assert engine.pending_promotions()


def test_black_pawn_promotes_to_the_chosen_piece_once_selected():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", ".", ".", "."],
        [".", "bP", ".", "."],
        [".", ".", ".", "."],
    ]
    engine, board = make_engine(rows)
    engine.click(2, 1)
    engine.click(3, 1)
    engine.wait(1000)
    engine.choose_promotion(3, 1, "R")
    assert signature(board.get(3, 1)) == ("b", "R")


def test_white_pawn_two_square_push_from_start_row():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", ".", ".", "."],
        [".", ".", ".", "."],
        [".", "wP", ".", "."],
        [".", ".", ".", "."],
    ]
    engine, board = make_engine(rows)
    engine.click(3, 1)
    engine.click(1, 1)
    engine.wait(2000)
    assert signature(board.get(1, 1)) == ("w", "P")


def test_white_pawn_two_square_push_blocked_by_piece_on_path():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", ".", ".", "."],
        [".", "bN", ".", "."],
        [".", "wP", ".", "."],
        [".", ".", ".", "."],
    ]
    engine, board = make_engine(rows)
    engine.click(3, 1)
    engine.click(1, 1)
    engine.wait(3000)
    assert signature(board.get(3, 1)) == ("w", "P")
    assert board.get(1, 1) is None


# --- jumping ---

def test_jump_with_no_arriving_enemy_leaves_board_unchanged():
    rows = [[".", ".", "."], [".", "wK", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(1, 1)
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")


def test_airborne_piece_captures_arriving_enemy():
    rows = [[".", ".", "."], [".", "wK", "bR"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(1, 1)
    engine.click(1, 2)
    engine.click(1, 1)
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")
    assert board.get(1, 2) is None


def test_piece_is_normal_target_again_after_jump_window_ends():
    rows = [[".", ".", "."], [".", "wK", "bR"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(1, 1)
    engine.wait(1000)  # jump window elapses; wK lands normally
    engine.click(1, 2)
    engine.click(1, 1)
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("b", "R")


def test_moving_piece_cannot_jump():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.jump(0, 0)  # ignored - wR is mid-route
    engine.wait(2000)
    assert signature(board.get(0, 2)) == ("w", "R")


def test_already_airborne_piece_cannot_re_jump():
    rows = [[".", ".", "."], [".", "wK", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(1, 1)
    engine.jump(1, 1)  # ignored - already airborne
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")


def test_jump_on_empty_cell_is_a_no_op():
    rows = [[".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(0, 0)
    engine.wait(1000)
    assert board.get(0, 0) is None


# --- move history / scores wiring ---

def test_engine_records_a_settled_move():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows)
    engine.click(2, 2)  # select wR
    engine.click(2, 0)  # request move to (2, 0)
    engine.wait(2000)  # 2-cell rook move settles
    assert engine.move_history() == ["Ra1"]


def test_engine_uses_an_injected_game_state():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    board = board_from(rows)
    rule_engine = RuleEngine(default_piece_rules())
    game_state = GameState()
    engine = GameEngine(board, rule_engine, game_state=game_state)

    engine.click(2, 2)
    engine.click(2, 0)
    engine.wait(2000)

    assert engine.move_history() == ["Ra1"]
    assert game_state.move_history() == ["Ra1"]  # the injected instance itself was mutated


def test_engine_scores_start_at_zero():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows)
    assert engine.scores() == {"w": 0, "b": 0}


def test_engine_credits_capture_via_game_state():
    rows = [["bR", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows)
    engine.click(2, 2)  # select wR
    engine.click(0, 2)  # move up column 2, not yet capturing
    engine.wait(2000)
    engine.click(0, 2)  # select wR again
    engine.click(0, 0)  # capture bR
    engine.wait(2000)
    assert engine.scores() == {"w": 5, "b": 0}


def test_game_state_exposes_the_snapshot_the_view_reads_from():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    assert sig_rows(engine.game_state().board_rows()) == [[("w", "K"), None]]


def test_choose_promotion_is_a_no_op_after_game_over():
    rows = [["wR", ".", "bK"], [".", "wP", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    assert engine.is_game_over()

    engine.choose_promotion(1, 1, "Q")  # no-op: game is already over
    assert signature(board.get(1, 1)) == ("w", "P")


def test_reselecting_a_friendly_piece_that_has_a_pending_move_keeps_current_selection():
    rows = [["wR", "wN", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)  # select wR
    engine.click(1, 0)  # request wR -> (1, 0), now in flight
    engine.click(0, 1)  # select wN
    engine.click(0, 0)  # attempt to reselect wR - ignored, it's mid-route
    engine.wait(1000)
    assert signature(board.get(1, 0)) == ("w", "R")  # wR's original move still went through


def test_jump_is_a_no_op_while_paused():
    rows = [["wR", ".", "bK"], [".", "wK", "."]]
    engine, board = make_engine(rows)
    engine.click(0, 0)
    engine.click(0, 2)
    engine.wait(2000)
    assert engine.is_game_over()

    engine.jump(1, 1)  # no-op: game is over
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")


def test_jump_outside_board_is_ignored():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    engine.jump(5, 5)
    engine.wait(1000)
    assert signature(board.get(0, 0)) == ("w", "K")


def test_engine_uses_injected_motion_and_arbiter():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    board = board_from(rows)
    rule_engine = RuleEngine(default_piece_rules())
    motion = MotionTracker()
    arbiter = RealTimeArbiter()
    engine = GameEngine(board, rule_engine, motion=motion, arbiter=arbiter)

    engine.click(2, 2)
    engine.click(2, 0)
    assert motion.has_pending_move_from(Position(2, 2))
