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


# --- MotionTracker: moves ---

def test_has_pending_move_from_true_for_scheduled_source():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    assert tracker.has_pending_move_from(Position(0, 0))


def test_has_pending_move_from_false_for_other_cell():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    assert not tracker.has_pending_move_from(Position(1, 1))
    assert not tracker.has_pending_move_from(Position(5, 5))


def test_has_opposing_color_in_flight_true_for_different_color():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece(color="w"))
    assert tracker.has_opposing_color_in_flight("b")


def test_has_opposing_color_in_flight_false_for_same_color():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece(color="w"))
    assert not tracker.has_opposing_color_in_flight("w")


def test_has_opposing_color_in_flight_false_when_nothing_pending():
    tracker = MotionTracker()
    assert not tracker.has_opposing_color_in_flight("w")


def test_take_due_moves_returns_move_exactly_at_completion_time():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    due = tracker.take_due_moves(100)
    assert len(due) == 1
    assert due[0].from_position == Position(0, 0)
    assert due[0].to_position == Position(1, 1)


def test_take_due_moves_excludes_move_before_completion_time():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    assert tracker.take_due_moves(99) == []
    assert tracker.has_pending_move_from(Position(0, 0))  # still pending, not consumed


def test_take_due_moves_removes_returned_moves_from_pending():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    tracker.take_due_moves(100)
    assert not tracker.has_pending_move_from(Position(0, 0))


def test_take_due_moves_only_consumes_due_moves_leaving_others_pending():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece(color="w"))
    tracker.schedule_move(Position(2, 2), Position(3, 3), complete_at_ms=200, piece=make_piece(color="b"))
    due = tracker.take_due_moves(100)
    assert len(due) == 1
    assert not tracker.has_pending_move_from(Position(0, 0))
    assert tracker.has_pending_move_from(Position(2, 2))


def test_clear_moves_removes_all_pending_moves():
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=make_piece())
    tracker.clear_moves()
    assert not tracker.has_pending_move_from(Position(0, 0))
    assert tracker.take_due_moves(100) == []


# --- MotionTracker: piece.state side effects ---

def test_schedule_move_marks_the_piece_moving():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=piece)
    assert piece.state == PieceState.MOVING


def test_take_due_moves_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=piece)
    tracker.take_due_moves(100)
    assert piece.state == PieceState.IDLE


def test_clear_moves_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_move(Position(0, 0), Position(1, 1), complete_at_ms=100, piece=piece)
    tracker.clear_moves()
    assert piece.state == PieceState.IDLE


def test_schedule_jump_marks_the_piece_capturing():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100)
    assert piece.state == PieceState.CAPTURES


def test_land_due_jumps_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100)
    tracker.land_due_jumps(100)
    assert piece.state == PieceState.IDLE


def test_clear_jumps_resets_the_piece_to_idle():
    piece = make_piece()
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=piece, land_at_ms=100)
    tracker.clear_jumps()
    assert piece.state == PieceState.IDLE


# --- MotionTracker: jumps ---

def test_is_airborne_true_for_scheduled_position():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100)
    assert tracker.is_airborne(Position(0, 0))


def test_is_airborne_false_for_other_position():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100)
    assert not tracker.is_airborne(Position(1, 1))


def test_land_due_jumps_lands_jump_exactly_at_window_end():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100)
    tracker.land_due_jumps(100)
    assert not tracker.is_airborne(Position(0, 0))


def test_land_due_jumps_keeps_jump_airborne_before_window_end():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100)
    tracker.land_due_jumps(99)
    assert tracker.is_airborne(Position(0, 0))


def test_clear_jumps_removes_all_airborne_jumps():
    tracker = MotionTracker()
    tracker.schedule_jump(Position(0, 0), piece=make_piece(kind="N"), land_at_ms=100)
    tracker.clear_jumps()
    assert not tracker.is_airborne(Position(0, 0))
