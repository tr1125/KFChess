import numpy as np

from kungfu_chess.driver.aspect_ratio import LETTERBOX_COLOR, compose_letterboxed, fit_size
from kungfu_chess.driver.panel_layout import compose_with_panels, panel_regions


# --- panel_regions ---


def test_panel_regions_reserves_fixed_width_when_window_is_wide_enough():
    left_width, board_available, right_width = panel_regions((300, 100), panel_width_px=50)

    assert left_width == 50
    assert right_width == 50
    assert board_available == (200, 100)


def test_panel_regions_board_absorbs_the_full_size_change_on_resize():
    # Same panel width, only the window (and therefore the board) grows.
    left_a, board_a, right_a = panel_regions((300, 100), panel_width_px=50)
    left_b, board_b, right_b = panel_regions((500, 100), panel_width_px=50)

    assert left_a == left_b == 50
    assert right_a == right_b == 50
    assert board_a == (200, 100)
    assert board_b == (400, 100)


def test_panel_regions_shrinks_panels_symmetrically_when_window_too_narrow():
    left_width, board_available, right_width = panel_regions((80, 100), panel_width_px=50)

    assert left_width == right_width == 39
    board_width, board_height = board_available
    assert board_width >= 1
    assert board_height == 100
    # Invariant: the three regions always sum to exactly the window width.
    assert left_width + board_width + right_width == 80


def test_panel_regions_never_shrinks_board_width_below_one():
    for window_w in range(1, 20):
        left_width, (board_width, _board_h), right_width = panel_regions((window_w, 10), panel_width_px=1000)
        assert board_width >= 1
        assert left_width + board_width + right_width == window_w


def test_panel_regions_degenerate_zero_width_window():
    left_width, board_available, right_width = panel_regions((0, 100), panel_width_px=50)

    assert left_width == 0
    assert right_width == 0
    assert board_available == (0, 100)


def test_panel_regions_clamps_negative_panel_width_to_zero():
    left_width, board_available, right_width = panel_regions((300, 100), panel_width_px=-10)

    assert left_width == 0
    assert right_width == 0
    assert board_available == (300, 100)


def test_panel_regions_zero_panel_width_gives_the_entire_window_to_the_board():
    left_width, board_available, right_width = panel_regions((300, 100), panel_width_px=0)

    assert left_width == 0
    assert right_width == 0
    assert board_available == (300, 100)


# --- compose_with_panels ---


def make_frame(height, width, fill_value):
    return np.full((height, width, 3), fill_value, dtype=np.uint8)


def test_compose_with_panels_canvas_matches_window_size():
    board_frame = make_frame(100, 100, 200)
    left_panel_frame = make_frame(100, 50, 111)
    right_panel_frame = make_frame(100, 50, 222)

    canvas, board_content_size, board_offset, left_width = compose_with_panels(
        board_frame, left_panel_frame, right_panel_frame, window_size=(300, 100), panel_width_px=50
    )

    assert canvas.shape == (100, 300, 3)
    assert left_width == 50
    assert board_content_size == fit_size((100, 100), (200, 100))
    assert board_offset == (50, 0)


def test_compose_with_panels_places_panels_and_board_at_expected_columns():
    board_frame = make_frame(100, 100, 200)
    left_panel_frame = make_frame(100, 50, 111)
    right_panel_frame = make_frame(100, 50, 222)

    canvas, _content_size, _offset, left_width = compose_with_panels(
        board_frame, left_panel_frame, right_panel_frame, window_size=(300, 100), panel_width_px=50
    )

    # Left panel occupies canvas columns [0, 50).
    assert (canvas[:, 0:50] == 111).all()
    # Right panel occupies the last 50 columns.
    assert (canvas[:, 250:300] == 222).all()
    # Board's own letterbox bars (its available width 200 vs square content
    # 100x100 pillarboxes 50px on each side) land at canvas columns
    # [50,100) and [200,250); actual board content lands at [100,200).
    assert tuple(canvas[0, 60]) == LETTERBOX_COLOR
    assert (canvas[:, 100:200] == 200).all()
    assert tuple(canvas[0, 210]) == LETTERBOX_COLOR
    assert left_width == 50


def test_compose_with_panels_matches_compose_letterboxed_for_the_board_sub_region():
    board_frame = make_frame(100, 100, 200)
    left_panel_frame = make_frame(100, 50, 111)
    right_panel_frame = make_frame(100, 50, 222)

    canvas, content_size, offset, left_width = compose_with_panels(
        board_frame, left_panel_frame, right_panel_frame, window_size=(300, 100), panel_width_px=50
    )

    expected_board_canvas, expected_content_size, expected_offset = compose_letterboxed(board_frame, (200, 100))

    assert content_size == expected_content_size
    assert offset == expected_offset
    assert (canvas[:, left_width:left_width + 200] == expected_board_canvas).all()