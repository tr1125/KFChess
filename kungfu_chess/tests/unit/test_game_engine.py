"""End-to-end tests of GameEngine wiring model/rules/realtime together,
working entirely in board cell coordinates via request_move/jump. Click-
selection semantics (which square is "selected", switching selection,
same-square-twice-is-a-jump) are UI-owned state and live in Controller -
see test_controller.py. Pixel-to-cell mapping is covered separately in
test_board_mapper.py.
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


# --- request_move behavior ---

def test_request_move_settles_after_wait():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 1, 1)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, None], [None, ("w", "K"), None], [None, None, None]]


def test_request_move_with_no_piece_at_source_is_a_no_op():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 2, 2)
    engine.wait(1000)
    assert signature(board.get(0, 0)) == ("w", "K")


def test_request_move_outside_board_is_ignored():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(3, 0, 0, 0)  # out-of-bounds source
    engine.request_move(0, 0, -1, 0)  # out-of-bounds destination
    assert signature(board.get(0, 0)) == ("w", "K")


def test_move_not_yet_settled_before_duration_elapses():
    rows = [["wK", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 1, 1)
    engine.wait(1)
    assert signature(board.get(0, 0)) == ("w", "K")


# --- duration proportional to distance ---

def test_multi_cell_slide_not_settled_just_before_duration_elapses():
    """Cell-by-cell movement (UI_PLAN.md Sec 2): by 2999ms, two of the
    three 1000ms-per-cell legs have already completed, so the rook is
    visibly at the second intermediate cell, not still at its origin -
    the last leg into the final destination isn't due until 3000ms.
    """
    rows = [["wR", ".", ".", "."], [".", ".", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 3)
    engine.wait(2999)
    assert signature(board.get(0, 2)) == ("w", "R")
    assert board.get(0, 3) is None


def test_multi_cell_slide_is_visible_at_intermediate_cells_partway_through():
    """The engine's own board state progresses cell by cell - not just a
    later rendering detail - so intermediate positions are directly
    observable through wait(), matching the glide the UI will later
    interpolate between (UI_PLAN.md Sec 5)."""
    rows = [["wR", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 3)
    engine.wait(1000)
    assert sig_row(board.rows()[0]) == [None, ("w", "R"), None, None]
    engine.wait(1000)
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R"), None]


def test_two_cell_move_before_and_after_arrival():
    rows = [["wR", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(1000)
    assert board.get(0, 2) is None
    engine.wait(1000)
    assert signature(board.get(0, 2)) == ("w", "R")


def test_multi_cell_slide_settled_once_duration_elapses():
    rows = [["wR", ".", ".", "."], [".", ".", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 3)
    engine.wait(3000)
    assert sig_row(board.rows()[0]) == [None, None, None, ("w", "R")]


def test_knight_move_takes_two_cells_worth_of_duration_despite_being_a_single_leg():
    """The knight's L-shape is legally a single leg (StepPattern has no
    intermediate cells to check - see rules/piece_rules.py), but it still
    spans a Chebyshev distance of 2, so it must take 2x the per-cell
    duration to settle, not 1x (see realtime/motion.py's leg-duration
    scaling - getting this wrong once silently halved knight speed)."""
    rows = [["wN", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 2, 1)
    engine.wait(1999)
    assert signature(board.get(0, 0)) == ("w", "N")  # not yet settled
    engine.wait(1)
    assert signature(board.get(2, 1)) == ("w", "N")


def test_illegal_shape_move_is_never_scheduled_even_after_waiting():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 2, 2)  # diagonal - illegal for a rook
    engine.wait(5000)
    assert signature(board.get(0, 0)) == ("w", "R")


# --- no redirecting a piece mid-route; long rest cooldown after arrival ---

def test_request_move_from_a_piece_that_is_still_in_transit_is_ignored():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(500)
    engine.request_move(0, 0, 0, 1)  # ignored - wR isn't IDLE, it's mid-route
    engine.wait(1500)
    assert sig_rows(board.rows()) == [[None, None, ("w", "R")], [None, None, None]]


def test_piece_cannot_move_again_during_long_rest():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows, long_rest_duration_ms=500)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)  # move settles; wR is now long-resting
    engine.request_move(0, 2, 1, 2)  # ignored - still resting
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, ("w", "R")], [None, None, None]]


def test_piece_can_move_again_after_long_rest_elapses():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows, long_rest_duration_ms=500)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)  # move settles; wR is now long-resting
    engine.wait(500)  # rest elapses
    engine.request_move(0, 2, 1, 2)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, None], [None, None, ("w", "R")]]


# --- advanced real-time interaction cases ---

def test_enemy_collision_capture_on_arrival():
    rows = [["wR", ".", "bK"], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R")]


def test_premove_is_blocked_while_enemy_is_in_transit():
    rows = [["bR", ".", "."], [".", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 2, 0)  # bR -> (2, 0)
    engine.wait(500)
    engine.request_move(2, 2, 1, 1)  # attempt to move wK while bR still in flight - blocked
    engine.wait(2000)
    assert sig_rows(board.rows()) == [
        [None, None, None],
        [None, None, None],
        [("b", "R"), None, ("w", "K")],
    ]


def test_friendly_piece_at_destination_cancels_in_transit_move():
    """wK (1 cell away) wins the shared destination first; wR (2 cells
    away) discovers the conflict only on its *second* leg, having
    already advanced one cell cleanly by then - cell-by-cell movement
    means it stops where it actually got to, not back at its origin."""
    rows = [["wR", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.request_move(1, 2, 0, 2)  # wK -> (0, 2)
    engine.request_move(0, 0, 0, 2)  # wR -> (0, 2), same destination as wK
    engine.wait(2000)
    assert sig_rows(board.rows()) == [[None, ("w", "R"), ("w", "K")], [None, None, None]]


def test_movement_conflict_first_registered_piece_wins_destination():
    """wK's own request here is simply illegal (a king cannot cross two
    squares in one move) and is rejected outright at request time - it
    never becomes a real-time collision at all, so wK stays exactly
    where it started, unaffected by cell-by-cell movement."""
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "wK"]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 2, 0)  # wR -> (2, 0), registered first
    engine.request_move(2, 2, 2, 0)  # wK -> (2, 0): illegal (2 squares), rejected at request time
    engine.wait(2000)
    assert sig_rows(board.rows()) == [
        [None, None, None],
        [None, None, None],
        [("w", "R"), None, ("w", "K")],
    ]


def test_friendly_block_on_a_moves_very_first_cell_does_not_trigger_rest():
    """The "stays IDLE, no rest" rule (UI_PLAN.md Sec 2) only applies when
    a move is blocked before covering even one cell. Here wB (1 cell
    away) claims wR's very first intended cell in the same real-time
    tick, before wR's own first leg is evaluated - wR never moves at
    all, so it's immediately movable again, and nothing is recorded in
    its history (contrast with the sibling tests above, where the losing
    piece has already advanced at least one cell and does get LONG_REST
    and a history entry).
    """
    rows = [["wR", ".", "."], ["wB", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 0, 0, 1)  # wB -> (0, 1) (a legal diagonal step), registered first
    engine.request_move(0, 0, 0, 2)  # wR -> (0, 2): its first leg target IS (0, 1)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[("w", "R"), ("w", "B"), None], [None, None, None]]
    assert engine.move_history() == ["Bb2"]  # only wB's settled move is recorded

    # wR never moved - it's immediately movable again, no rest owed.
    engine.request_move(0, 0, 1, 0)
    engine.wait(1000)
    assert signature(board.get(1, 0)) == ("w", "R")


def test_multi_cell_slide_captures_a_mid_path_enemy_and_stops_there_without_continuing():
    """A grounded enemy that appears partway through a slide's path in
    real time is captured and ends the move right there - the remaining
    originally-requested path is discarded (UI_PLAN.md Sec 2: "just re-
    evaluated per step", matching SlidePattern's own semantics).

    Opposite colors can never be concurrently in flight
    (has_opposing_color_in_flight), so the only way an enemy piece can
    newly "appear" as a grounded obstacle mid-slide - rather than already
    being a known blocker at request time - is if it was airborne (and
    therefore passable/legal to slide onto) when the slide was requested,
    then lands and grounds itself again partway through the slide's
    journey. Jumping isn't gated by color concurrency at all.
    """
    rows = [["wR", ".", "bB", "."]]
    engine, board = make_engine(rows)
    engine.jump(0, 2)  # bB airborne - passable, so wR's full 3-cell slide is legal
    engine.request_move(0, 0, 0, 3)
    engine.wait(1000)  # wR's first leg completes (-> 0,1); bB's jump lands, grounding it again at (0, 2)
    engine.wait(1000)  # wR's second leg discovers bB now grounded at (0, 2) and captures it
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R"), None]  # stopped at the capture, not (0, 3)
    assert board.get(0, 3) is None
    assert engine.scores() == {"w": 3, "b": 0}  # bishop (3) credited to white


# --- game-over on king capture ---

def test_capturing_enemy_king_ends_the_game():
    rows = [["wR", ".", "bK"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)
    assert engine.is_game_over()
    assert sig_row(board.rows()[0]) == [None, None, ("w", "R")]


def test_move_commands_ignored_after_game_over():
    rows = [["wR", ".", "bK"], [".", "wK", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)
    assert engine.is_game_over()
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)
    assert sig_rows(board.rows()) == [[None, None, ("w", "R")], [None, ("w", "K"), None]]


# --- pawn promotion and two-square initial push ---

def test_white_pawn_reaching_row_zero_auto_promotes_to_queen_by_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)
    assert signature(board.get(0, 1)) == ("w", "Q")
    assert engine.pending_promotions() == [{"row": 0, "col": 1, "color": "w", "choices": ("Q", "R", "B", "N")}]


def test_choose_promotion_can_override_the_auto_promoted_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)
    assert signature(board.get(0, 1)) == ("w", "Q")  # auto-promoted first

    engine.choose_promotion(0, 1, "N")
    assert signature(board.get(0, 1)) == ("w", "N")  # then overridden
    assert not engine.pending_promotions()
    assert engine.move_history()[-2:] == ["b3=Q", "b3=N"]


def test_other_moves_are_not_blocked_while_a_promotion_choice_is_still_open():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "bR"], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)  # wP auto-promotes to wQ; a choice is still open

    engine.request_move(1, 3, 1, 2)  # bR -> (1, 2) - not blocked by the open promotion choice
    engine.wait(1000)

    assert signature(board.get(1, 2)) == ("b", "R")
    assert engine.pending_promotions()  # the choice is still open, unresolved


def test_choose_promotion_with_invalid_choice_is_a_no_op_and_keeps_the_auto_promoted_default():
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)
    engine.choose_promotion(0, 1, "K")
    assert signature(board.get(0, 1)) == ("w", "Q")  # still the auto-promoted default
    pending = engine.pending_promotions()
    assert pending == [{"row": 0, "col": 1, "color": "w", "choices": ("Q", "R", "B", "N")}]


def test_choose_promotion_is_a_no_op_once_the_promoted_piece_has_moved_away():
    """pending_promotions() still lists the old square (nothing ever
    invalidates it just because the piece left), but choose_promotion
    must not act on a stale position - it must not crash, and must not
    touch whatever piece (if any) is there now (see RuleEngine.
    apply_promotion_choice's identity check)."""
    rows = [["wK", ".", ".", "bK"], [".", "wP", ".", "."], [".", ".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)  # wP auto-promotes to wQ at (0, 1)
    engine.wait(1000)  # LONG_REST elapses; the queen is IDLE again
    engine.request_move(0, 1, 0, 2)  # the promoted queen moves on
    engine.wait(1000)

    assert signature(board.get(0, 2)) == ("w", "Q")
    assert board.get(0, 1) is None  # the stale square is now empty
    assert engine.pending_promotions()  # still (stale-)reported as open

    engine.choose_promotion(0, 1, "N")  # must not raise, must not do anything

    assert board.get(0, 1) is None
    assert signature(board.get(0, 2)) == ("w", "Q")  # unaffected


def test_black_pawn_reaching_last_row_auto_promotes_to_queen_by_default():
    rows = [
        ["wK", ".", ".", "bK"],
        [".", ".", ".", "."],
        [".", "bP", ".", "."],
        [".", ".", ".", "."],
    ]
    engine, board = make_engine(rows)
    engine.request_move(2, 1, 3, 1)
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
    engine.request_move(2, 1, 3, 1)
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
    engine.request_move(3, 1, 1, 1)
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
    engine.request_move(3, 1, 1, 1)
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
    engine.request_move(1, 2, 1, 1)
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")
    assert board.get(1, 2) is None


def test_piece_is_normal_target_again_after_jump_window_ends():
    rows = [[".", ".", "."], [".", "wK", "bR"], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(1, 1)
    engine.wait(1000)  # jump window elapses; wK lands normally
    engine.request_move(1, 2, 1, 1)
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("b", "R")


def test_moving_piece_cannot_jump():
    rows = [["wR", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
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


def test_landed_jump_cannot_move_or_rejump_during_short_rest():
    rows = [[".", ".", "."], [".", "wK", "."], [".", ".", "."]]
    engine, board = make_engine(rows, short_rest_duration_ms=500)
    engine.jump(1, 1)
    engine.wait(1000)  # jump lands; wK is now short-resting
    engine.jump(1, 1)  # ignored - still resting
    engine.request_move(1, 1, 0, 1)  # ignored - still resting
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("w", "K")
    assert board.get(0, 1) is None


def test_landed_jump_can_move_again_after_short_rest_elapses():
    rows = [[".", ".", "."], [".", "wK", "."], [".", ".", "."]]
    engine, board = make_engine(rows, short_rest_duration_ms=500)
    engine.jump(1, 1)
    engine.wait(1000)  # jump lands; wK is now short-resting
    engine.wait(500)  # rest elapses
    engine.request_move(1, 1, 0, 1)
    engine.wait(1000)
    assert signature(board.get(0, 1)) == ("w", "K")


def test_jump_on_empty_cell_is_a_no_op():
    rows = [[".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.jump(0, 0)
    engine.wait(1000)
    assert board.get(0, 0) is None


def test_airborne_piece_captures_an_enemy_that_settled_there_earlier_in_the_flight():
    """An arriver isn't captured just by sitting on the airborne piece's
    cell - only at the exact landing instant (UI_PLAN.md Sec 2: "safe"
    until then) - shown here with the landing several ticks after the
    enemy already settled there peacefully.
    """
    rows = [[".", ".", "."], [".", "wK", "bR"], [".", ".", "."]]
    engine, board = make_engine(rows, jump_duration_ms=3000)
    engine.jump(1, 1)  # wK airborne until t=3000
    engine.request_move(1, 2, 1, 1)  # bR settles onto wK's cell at t=1000 - safe for now
    engine.wait(1000)
    assert signature(board.get(1, 1)) == ("b", "R")  # sitting there peacefully, not yet captured
    engine.wait(2000)  # wK's jump lands at t=3000
    assert signature(board.get(1, 1)) == ("w", "K")  # captured at the exact landing instant


def test_slide_continues_past_a_still_airborne_enemy_and_it_reclaims_its_cell_on_landing():
    """An enemy currently AIRBORNE doesn't block a slide - the mover can
    pass all the way through and beyond it (UI_PLAN.md Sec 2). Once the
    mover has moved on, the cell it passed through is empty again; the
    airborne piece still reclaims that same cell, unharmed, once its own
    jump window ends (see the fix to GameEngine._land_due_jumps - passing
    through must not orphan the airborne piece off the board).
    """
    rows = [["wR", ".", "bN", "."]]
    engine, board = make_engine(rows, jump_duration_ms=5000)
    engine.jump(0, 2)  # bN airborne well past wR's whole journey
    engine.request_move(0, 0, 0, 3)  # wR slides through bN's cell to the far side
    engine.wait(3000)
    assert sig_row(board.rows()[0]) == [None, None, None, ("w", "R")]  # past bN, not on it

    engine.wait(2000)  # bN's jump window ends at t=5000
    assert sig_row(board.rows()[0]) == [None, None, ("b", "N"), ("w", "R")]  # bN reclaims its cell


# --- move history / scores wiring ---

def test_engine_records_a_settled_move():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows)
    engine.request_move(2, 2, 2, 0)
    engine.wait(2000)  # 2-cell rook move settles
    assert engine.move_history() == ["Ra1"]


def test_engine_uses_an_injected_game_state():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    board = board_from(rows)
    rule_engine = RuleEngine(default_piece_rules())
    game_state = GameState()
    engine = GameEngine(board, rule_engine, game_state=game_state)

    engine.request_move(2, 2, 2, 0)
    engine.wait(2000)

    assert engine.move_history() == ["Ra1"]
    assert game_state.move_history() == ["Ra1"]  # the injected instance itself was mutated


def test_engine_scores_start_at_zero():
    rows = [["bK", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows)
    assert engine.scores() == {"w": 0, "b": 0}


def test_engine_credits_capture_via_game_state():
    rows = [["bR", ".", "."], [".", ".", "."], [".", ".", "wR"]]
    engine, board = make_engine(rows, long_rest_duration_ms=0)  # not testing resting here
    engine.request_move(2, 2, 0, 2)  # move up column 2, not yet capturing
    engine.wait(2000)
    engine.request_move(0, 2, 0, 0)  # capture bR
    engine.wait(2000)
    assert engine.scores() == {"w": 5, "b": 0}


def test_game_state_exposes_the_snapshot_the_view_reads_from():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    assert sig_rows(engine.game_state().board_rows()) == [[("w", "K"), None]]


# --- animation-layer accessors: now(), in_flight_leg() ---
#
# Exposed read-only for the UI's animation step (UI_PLAN.md Sec 5) -
# never called by anything inside GameEngine itself.

def test_now_starts_at_zero():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    assert engine.now() == 0


def test_now_reflects_elapsed_wait_time():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    engine.wait(250)
    engine.wait(17)
    assert engine.now() == 267


def test_in_flight_leg_returns_none_when_nothing_pending():
    rows = [["wK", "."]]
    engine, board = make_engine(rows)
    assert engine.in_flight_leg(board.get(0, 0)) is None


def test_in_flight_leg_returns_positions_and_timing_for_a_mid_leg_piece():
    rows = [["wR", ".", "."]]
    engine, board = make_engine(rows)
    piece = board.get(0, 0)
    engine.request_move(0, 0, 0, 1)

    current, target, started_at, complete_at = engine.in_flight_leg(piece)
    assert current == Position(0, 0)
    assert target == Position(0, 1)
    assert started_at == 0
    assert complete_at == 1000


def test_in_flight_leg_returns_none_once_the_move_settles():
    rows = [["wR", ".", "."]]
    engine, board = make_engine(rows)
    piece = board.get(0, 0)
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    assert engine.in_flight_leg(piece) is None


def test_choose_promotion_is_a_no_op_after_game_over():
    rows = [["wR", ".", "bK"], [".", "wP", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
    engine.wait(2000)
    assert engine.is_game_over()

    engine.choose_promotion(1, 1, "Q")  # no-op: game is already over
    assert signature(board.get(1, 1)) == ("w", "P")


def test_jump_is_a_no_op_while_paused():
    rows = [["wR", ".", "bK"], [".", "wK", "."]]
    engine, board = make_engine(rows)
    engine.request_move(0, 0, 0, 2)
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

    engine.request_move(2, 2, 2, 0)
    assert motion.has_pending_move_from(Position(2, 2))