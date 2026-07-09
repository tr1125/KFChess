"""Direct unit tests for MoveScheduler and JumpScheduler. These exercise
the scheduling boundary conditions (exactly-due timing, opposing-color
detection) at the class level rather than only indirectly through
test_main.py's end-to-end command scenarios.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.move_scheduler import MoveScheduler
from engine.jump_scheduler import JumpScheduler


# --- MoveScheduler ---

def test_has_pending_from_true_for_scheduled_source():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    assert scheduler.has_pending_from(0, 0)


def test_has_pending_from_false_for_other_cell():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    assert not scheduler.has_pending_from(1, 1)
    assert not scheduler.has_pending_from(5, 5)


def test_has_opposing_color_in_flight_true_for_different_color():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    assert scheduler.has_opposing_color_in_flight("b")


def test_has_opposing_color_in_flight_false_for_same_color():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    assert not scheduler.has_opposing_color_in_flight("w")


def test_has_opposing_color_in_flight_false_when_nothing_pending():
    scheduler = MoveScheduler()
    assert not scheduler.has_opposing_color_in_flight("w")
    assert not scheduler.has_opposing_color_in_flight("b")


def test_take_due_returns_move_exactly_at_completion_time():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    due = scheduler.take_due(100)
    assert len(due) == 1
    assert (due[0].from_row, due[0].from_col, due[0].to_row, due[0].to_col) == (0, 0, 1, 1)


def test_take_due_excludes_move_before_completion_time():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    assert scheduler.take_due(99) == []
    assert scheduler.has_pending_from(0, 0)  # still pending, not consumed


def test_take_due_removes_returned_moves_from_pending():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    scheduler.take_due(100)
    assert not scheduler.has_pending_from(0, 0)


def test_take_due_only_consumes_due_moves_leaving_others_pending():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    scheduler.schedule(2, 2, 3, 3, complete_at_ms=200, mover_token="bP")
    due = scheduler.take_due(100)
    assert len(due) == 1
    assert not scheduler.has_pending_from(0, 0)
    assert scheduler.has_pending_from(2, 2)


def test_clear_removes_all_pending_moves():
    scheduler = MoveScheduler()
    scheduler.schedule(0, 0, 1, 1, complete_at_ms=100, mover_token="wP")
    scheduler.clear()
    assert not scheduler.has_pending_from(0, 0)
    assert scheduler.take_due(100) == []


# --- JumpScheduler ---

def test_is_airborne_true_for_scheduled_cell():
    scheduler = JumpScheduler()
    scheduler.schedule(0, 0, token="wN", land_at_ms=100)
    assert scheduler.is_airborne(0, 0)


def test_is_airborne_false_for_other_cell():
    scheduler = JumpScheduler()
    scheduler.schedule(0, 0, token="wN", land_at_ms=100)
    assert not scheduler.is_airborne(1, 1)


def test_land_due_lands_jump_exactly_at_window_end():
    scheduler = JumpScheduler()
    scheduler.schedule(0, 0, token="wN", land_at_ms=100)
    scheduler.land_due(100)
    assert not scheduler.is_airborne(0, 0)


def test_land_due_keeps_jump_airborne_before_window_end():
    scheduler = JumpScheduler()
    scheduler.schedule(0, 0, token="wN", land_at_ms=100)
    scheduler.land_due(99)
    assert scheduler.is_airborne(0, 0)


def test_clear_removes_all_airborne_jumps():
    scheduler = JumpScheduler()
    scheduler.schedule(0, 0, token="wN", land_at_ms=100)
    scheduler.clear()
    assert not scheduler.is_airborne(0, 0)
