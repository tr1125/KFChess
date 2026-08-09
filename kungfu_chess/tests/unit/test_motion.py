from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.realtime.motion import ManualClock, MotionTracker


def make_piece(color="w", kind="P"):
    return Piece(color=color, kind=kind)


# --- ManualClock ---

def test_clock_starts_at_zero():
    assert ManualClock().now() == 0


def test_clock_advance_accumulates():
    clock = ManualClock()
    clock.advance(100)
    clock.advance(50)
    assert clock.now() == 150


# --- MotionTracker: moves (single-leg path) ---

def test_schedule_move_sets_current_position_and_leg_target():
    tracker = MotionTracker()
    piece = make_piece()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    assert tracker.has_pending_move_from(Position(0, 0))
    current, target, started_at, complete_at = tracker.in_flight_leg(piece)
    assert current == Position(0, 0)
    assert target == Position(1, 1)
    assert started_at == 0
    assert complete_at == 100


def test_schedule_move_with_multi_leg_path_only_schedules_the_first_leg():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2), Position(0, 3)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    current, target, started_at, complete_at = tracker.in_flight_leg(piece)
    assert current == Position(0, 0)
    assert target == Position(0, 1)  # only the first leg, not the final destination
    assert started_at == 0
    assert complete_at == 1000


def test_schedule_move_scales_leg_duration_by_the_legs_own_chebyshev_distance():
    """A StepPattern leg (e.g. a knight's L-shape) has no intermediate
    cells to check, so it's scheduled as a single leg - but that leg still
    spans a Chebyshev distance of 2, and must take 2x as long as a
    1-cell leg at the same per_cell_ms rate (see motion.py module
    docstring - getting this wrong once silently halved knight duration).
    """
    tracker = MotionTracker()
    piece = make_piece(kind="N")
    tracker.schedule_move(Position(2, 2), [Position(0, 1)], piece, per_cell_ms=1000, now_ms=0)
    _, _, started_at, complete_at = tracker.in_flight_leg(piece)
    assert started_at == 0
    assert complete_at == 2000


def test_schedule_move_returns_the_scheduled_pending_move():
    tracker = MotionTracker()
    piece = make_piece()
    move = tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    assert move.current_position == Position(0, 0)
    assert move.leg_target == Position(1, 1)
    assert move.leg_started_at_ms == 0
    assert move.complete_at_ms == 100
    assert move.piece is piece


def test_has_pending_move_from_false_for_other_cell():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(), per_cell_ms=100, now_ms=0)
    assert not tracker.has_pending_move_from(Position(1, 1))
    assert not tracker.has_pending_move_from(Position(5, 5))


def test_tracker_holds_concurrent_pending_moves_for_both_colors_independently():
    """Moves aren't serialized by color (UI_PLAN.md Sec 2 / GameState's
    "not strictly alternating" design) - MotionTracker has no color
    concept gating scheduling at all, so pieces of both colors can be
    genuinely in flight at the same time, each tracked independently."""
    tracker = MotionTracker()
    white = make_piece(color="w")
    black = make_piece(color="b")
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], white, per_cell_ms=100, now_ms=0)
    tracker.schedule_move(Position(5, 5), [Position(6, 6)], black, per_cell_ms=100, now_ms=0)

    white_current, white_target, _, _ = tracker.in_flight_leg(white)
    black_current, black_target, _, _ = tracker.in_flight_leg(black)
    assert (white_current, white_target) == (Position(0, 0), Position(1, 1))
    assert (black_current, black_target) == (Position(5, 5), Position(6, 6))


def test_take_due_moves_returns_move_exactly_at_completion_time():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(), per_cell_ms=100, now_ms=0)
    due = tracker.take_due_moves(100)
    assert len(due) == 1
    assert due[0].current_position == Position(0, 0)
    assert due[0].leg_target == Position(1, 1)
    assert due[0].steps_completed == 0


def test_take_due_moves_excludes_move_before_completion_time():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(), per_cell_ms=100, now_ms=0)
    assert tracker.take_due_moves(99) == []
    assert tracker.has_pending_move_from(Position(0, 0))  # still pending, not consumed


def test_take_due_moves_removes_returned_moves_from_pending():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(), per_cell_ms=100, now_ms=0)
    tracker.take_due_moves(100)
    assert not tracker.has_pending_move_from(Position(0, 0))


def test_take_due_moves_only_consumes_due_moves_leaving_others_pending():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(color="w"), per_cell_ms=100, now_ms=0)
    tracker.schedule_move(Position(2, 2), [Position(3, 3)], make_piece(color="b"), per_cell_ms=200, now_ms=0)
    due = tracker.take_due_moves(100)
    assert len(due) == 1
    assert not tracker.has_pending_move_from(Position(0, 0))
    assert tracker.has_pending_move_from(Position(2, 2))


def test_take_due_moves_does_not_touch_piece_state():
    """Unlike the old atomic model, a due leg can end several different
    ways (continue, stop, capture) - only the caller (via
    RealTimeArbiter's classification) decides, so taking a due leg off
    the pending list leaves piece.state untouched.
    """
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    tracker.take_due_moves(100)
    assert piece.state == PieceState.MOVING


def test_clear_moves_removes_all_pending_moves():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], make_piece(), per_cell_ms=100, now_ms=0)
    tracker.clear_moves(now_ms=100)
    assert not tracker.has_pending_move_from(Position(0, 0))
    assert tracker.take_due_moves(100) == []


# --- MotionTracker: schedule_next_leg (continuing a multi-leg move) ---

def test_schedule_next_leg_returns_the_scheduled_pending_move():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(1000)[0]
    next_move = tracker.schedule_next_leg(due_move, per_cell_ms=1000)
    assert next_move.current_position == Position(0, 1)
    assert next_move.leg_target == Position(0, 2)
    assert next_move.leg_started_at_ms == 1000
    assert next_move.complete_at_ms == 2000
    assert next_move.piece is piece


def test_schedule_next_leg_advances_current_position_and_target():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(1000)[0]
    tracker.schedule_next_leg(due_move, per_cell_ms=1000)

    current, target, started_at, complete_at = tracker.in_flight_leg(piece)
    assert current == Position(0, 1)  # the leg that just completed
    assert target == Position(0, 2)  # the next cell in the path
    assert started_at == 1000
    assert complete_at == 2000


def test_schedule_next_leg_chains_from_the_completed_legs_own_due_time():
    """The next leg's due time is anchored to the schedule already in
    progress (complete_at_ms + per_cell_ms), not to whenever `wait()`
    happened to process it - otherwise a single big `wait()` call
    spanning several legs' worth of time would only ever advance one leg.
    """
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(2999)[0]  # processed well after its own due time (1000)
    tracker.schedule_next_leg(due_move, per_cell_ms=1000)
    _, _, started_at, complete_at = tracker.in_flight_leg(piece)
    assert started_at == 1000  # chained from the completed leg's own due time, not 2999
    assert complete_at == 2000  # chained from 1000 + 1000, not 2999 + 1000


def test_schedule_next_leg_scales_leg_duration_by_the_legs_own_chebyshev_distance():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(2, 2)]  # second leg spans a Chebyshev distance of 2
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(1000)[0]
    tracker.schedule_next_leg(due_move, per_cell_ms=1000)
    _, _, started_at, complete_at = tracker.in_flight_leg(piece)
    assert started_at == 1000
    assert complete_at == 3000  # 1000 (leg start) + 2 * 1000 (2-cell span)


def test_schedule_next_leg_increments_steps_completed():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(1000)[0]
    assert due_move.steps_completed == 0
    tracker.schedule_next_leg(due_move, per_cell_ms=1000)
    next_due = tracker.take_due_moves(2000)[0]
    assert next_due.steps_completed == 1


def test_schedule_next_leg_leaves_piece_state_as_moving():
    tracker = MotionTracker()
    piece = make_piece()
    path = [Position(0, 1), Position(0, 2)]
    tracker.schedule_move(Position(0, 0), path, piece, per_cell_ms=1000, now_ms=0)
    due_move = tracker.take_due_moves(1000)[0]
    tracker.schedule_next_leg(due_move, per_cell_ms=1000)
    assert piece.state == PieceState.MOVING


# --- MotionTracker: in_flight_leg ---

def test_in_flight_leg_returns_none_when_piece_is_not_mid_leg():
    tracker = MotionTracker()
    assert tracker.in_flight_leg(make_piece()) is None


def test_in_flight_leg_returns_none_after_leg_is_taken_as_due():
    tracker = MotionTracker()
    piece = make_piece()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    tracker.take_due_moves(100)
    assert tracker.in_flight_leg(piece) is None


# --- MotionTracker: mark_idle ---

def test_mark_idle_sets_state_and_timestamp():
    piece = make_piece()
    piece.state = PieceState.MOVING
    tracker = MotionTracker()
    tracker.mark_idle(piece, now_ms=250)
    assert piece.state == PieceState.IDLE
    assert piece.state_entered_at == 250


# --- MotionTracker: piece.state side effects ---

def test_schedule_move_marks_the_piece_moving():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    assert piece.state == PieceState.MOVING


def test_schedule_move_stamps_state_entered_at():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=42)
    assert piece.state_entered_at == 42


def test_clear_moves_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), [Position(1, 1)], piece, per_cell_ms=100, now_ms=0)
    tracker.clear_moves(now_ms=100)
    assert piece.state == PieceState.IDLE


def test_schedule_jump_marks_the_piece_airborne():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100, now_ms=0)
    assert piece.state == PieceState.AIRBORNE


def test_schedule_jump_stamps_state_entered_at():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100, now_ms=7)
    assert piece.state_entered_at == 7


def test_land_due_jumps_does_not_touch_piece_state():
    """Whether landing is a normal arrival or a mid-air capture is
    decided by the caller (GameEngine._land_due_jumps), depending on who
    (if anyone) now occupies the cell."""
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100, now_ms=0)
    tracker.land_due_jumps(100)
    assert piece.state == PieceState.AIRBORNE


def test_land_due_jumps_returns_the_landed_jump():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100, now_ms=0)
    landed = tracker.land_due_jumps(100)
    assert len(landed) == 1
    assert landed[0].piece is piece
    assert landed[0].position == Position(0, 0)


def test_clear_jumps_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100, now_ms=0)
    tracker.clear_jumps(now_ms=100)
    assert piece.state == PieceState.IDLE


# --- MotionTracker: jumps ---

def test_is_airborne_true_for_scheduled_position():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100, now_ms=0)
    assert tracker.is_airborne(Position(0, 0))


def test_is_airborne_false_for_other_position():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100, now_ms=0)
    assert not tracker.is_airborne(Position(1, 1))


def test_land_due_jumps_lands_jump_exactly_at_window_end():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100, now_ms=0)
    tracker.land_due_jumps(100)
    assert not tracker.is_airborne(Position(0, 0))


def test_land_due_jumps_keeps_jump_airborne_before_window_end():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100, now_ms=0)
    tracker.land_due_jumps(99)
    assert tracker.is_airborne(Position(0, 0))


def test_clear_jumps_removes_all_airborne_jumps():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100, now_ms=0)
    tracker.clear_jumps(now_ms=100)
    assert not tracker.is_airborne(Position(0, 0))


# --- MotionTracker: rests ---

def test_begin_rest_marks_the_piece_with_the_given_state():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    assert piece.state == PieceState.LONG_REST


def test_begin_rest_stamps_state_entered_at():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece, PieceState.LONG_REST, rest_over_ms=100, now_ms=17)
    assert piece.state_entered_at == 17


def test_wake_due_rests_returns_the_woken_pieces():
    piece_a = make_piece()
    piece_b = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece_a, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    tracker.begin_rest(piece_b, PieceState.SHORT_REST, rest_over_ms=200, now_ms=0)
    assert tracker.wake_due_rests(100) == [piece_a]
    assert tracker.wake_due_rests(200) == [piece_b]


def test_wake_due_rests_returns_an_empty_list_when_nothing_is_due():
    tracker = MotionTracker()
    tracker.begin_rest(make_piece(), PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    assert tracker.wake_due_rests(99) == []


def test_wake_due_rests_wakes_rest_exactly_at_expiry():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    tracker.wake_due_rests(100)
    assert piece.state == PieceState.IDLE


def test_wake_due_rests_keeps_piece_resting_before_expiry():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    tracker.wake_due_rests(99)
    assert piece.state == PieceState.LONG_REST


def test_wake_due_rests_only_wakes_due_rests_leaving_others_resting():
    piece_a = make_piece()
    piece_b = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece_a, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    tracker.begin_rest(piece_b, PieceState.SHORT_REST, rest_over_ms=200, now_ms=0)
    tracker.wake_due_rests(100)
    assert piece_a.state == PieceState.IDLE
    assert piece_b.state == PieceState.SHORT_REST


def test_clear_rests_resets_all_resting_pieces_to_idle():
    piece_a = make_piece()
    piece_b = make_piece()
    tracker = MotionTracker()
    tracker.begin_rest(piece_a, PieceState.LONG_REST, rest_over_ms=100, now_ms=0)
    tracker.begin_rest(piece_b, PieceState.SHORT_REST, rest_over_ms=200, now_ms=0)
    tracker.clear_rests(now_ms=1000)
    assert piece_a.state == PieceState.IDLE
    assert piece_b.state == PieceState.IDLE
    tracker.wake_due_rests(1000)  # no-op: nothing left to wake
    assert piece_a.state == PieceState.IDLE
    assert piece_b.state == PieceState.IDLE
