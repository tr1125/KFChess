from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.observers.move_log_observer import (
    PanelData,
    clamp_scroll_offset,
    snapshot_for_color,
    visible_slice,
)


def piece(token):
    return Piece(color=token[0], kind=token[1])


def empty_board(size=8):
    return Board([[None] * size for _ in range(size)])


# --- snapshot_for_color ---


def test_snapshot_for_color_delegates_to_scores_and_moves_for_color():
    state = GameState()
    state.record_capture("w", 9)
    state.record_move(empty_board(), piece("wP"), Position(6, 4), Position(4, 4))
    state.record_move(empty_board(), piece("bP"), Position(1, 3), Position(3, 3))

    data = snapshot_for_color(state, "w")

    assert data == PanelData(color="w", score=9, moves=["e4"])


def test_snapshot_for_color_for_a_player_with_no_activity_yet():
    state = GameState()
    data = snapshot_for_color(state, "b")
    assert data == PanelData(color="b", score=0, moves=[])


# --- clamp_scroll_offset ---


def test_clamp_scroll_offset_never_goes_negative():
    assert clamp_scroll_offset(-5, total_moves=10, viewport_lines=4) == 0


def test_clamp_scroll_offset_is_a_no_op_within_range():
    assert clamp_scroll_offset(3, total_moves=10, viewport_lines=4) == 3


def test_clamp_scroll_offset_caps_at_total_minus_viewport():
    assert clamp_scroll_offset(999, total_moves=10, viewport_lines=4) == 6


def test_clamp_scroll_offset_is_zero_when_everything_fits_in_the_viewport():
    assert clamp_scroll_offset(5, total_moves=3, viewport_lines=10) == 0


def test_clamp_scroll_offset_re_clamps_as_total_moves_grows():
    # Offset was valid against a shorter list; a longer list re-clamps it
    # to whatever the new max still allows, rather than leaving it stuck.
    offset = clamp_scroll_offset(0, total_moves=4, viewport_lines=4)  # 0, list fully fits
    assert offset == 0
    # List grows; same stored offset (0) is still valid (still shows latest).
    assert clamp_scroll_offset(offset, total_moves=20, viewport_lines=4) == 0
    # A large stored offset from before the list grew gets capped to the new range.
    assert clamp_scroll_offset(100, total_moves=20, viewport_lines=4) == 16


# --- visible_slice ---


def test_visible_slice_with_zero_offset_shows_the_most_recent_moves():
    moves = ["e4", "d5", "Nf3", "Nc6", "Bb5"]
    assert visible_slice(moves, scroll_offset=0, viewport_lines=3) == ["Nf3", "Nc6", "Bb5"]


def test_visible_slice_with_offset_reveals_older_moves():
    moves = ["e4", "d5", "Nf3", "Nc6", "Bb5"]
    assert visible_slice(moves, scroll_offset=2, viewport_lines=3) == ["e4", "d5", "Nf3"]


def test_visible_slice_when_everything_fits_returns_the_whole_list():
    moves = ["e4", "d5"]
    assert visible_slice(moves, scroll_offset=0, viewport_lines=10) == ["e4", "d5"]


def test_visible_slice_clamps_an_out_of_range_offset():
    moves = ["e4", "d5", "Nf3"]
    assert visible_slice(moves, scroll_offset=999, viewport_lines=2) == ["e4", "d5"]


def test_visible_slice_on_empty_move_list():
    assert visible_slice([], scroll_offset=0, viewport_lines=5) == []