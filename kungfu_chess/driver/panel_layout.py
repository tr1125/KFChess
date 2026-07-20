"""Panel-width/board-region composition for the resizable window (see
UI_PLAN.md Sec 11.3, composed with Sec 11.2's aspect-ratio lock): board
centered, one panel flanking each side, panel width staying close to
fixed while the board absorbs most of a resize - not three regions all
scaling together.

Mirrors aspect_ratio.py's own internal shape: panel_regions is pure
geometry, easily unit-tested without a window; compose_with_panels does
the actual cv2/numpy compositing work but stays testable with synthetic
frames, no live window needed. Reuses aspect_ratio.compose_letterboxed
unchanged for the board's own ratio lock - panel math is a distinct,
composable concern layered in front of it, not a change to it.
"""

import cv2

from kungfu_chess.driver.aspect_ratio import compose_letterboxed


def panel_regions(window_size, panel_width_px):
    """Reserves panel_width_px fixed on each side and gives the rest of
    the window's width to the board. Only shrinks both panel widths
    (symmetrically, floor-divided) if the window is too narrow to fit
    both at their configured width - panels never go negative, board
    width is kept at least 1 (so compose_letterboxed never falls back to
    its own "degenerate available size" native-size behavior, which
    would break the hconcat invariant below), and left_width +
    board_width + right_width always sums to exactly window_w.
    """
    window_w, window_h = window_size
    window_w = max(0, window_w)
    panel_width_px = max(0, panel_width_px)

    if window_w == 0:
        return 0, (0, window_h), 0

    max_panel_width_each = (window_w - 1) // 2  # leaves board_width >= 1
    effective_panel_width = min(panel_width_px, max_panel_width_each)
    left_width = effective_panel_width
    right_width = effective_panel_width
    board_width = window_w - left_width - right_width

    return left_width, (board_width, window_h), right_width


def compose_with_panels(board_frame, left_panel_frame, right_panel_frame, window_size, panel_width_px):
    """Letterboxes board_frame into just its reserved sub-region (via
    the existing, unmodified compose_letterboxed), then concatenates the
    already-rendered left/right panel frames on either side to produce
    one canvas of exactly window_size. left_panel_frame/right_panel_frame
    must already be rendered at the widths panel_regions(window_size,
    panel_width_px) reports (and at window's height) - see
    driver/game_loop.py, which renders them via SidePanelView's
    width_px override for exactly this reason.

    Returns (canvas, board_content_size, board_offset, left_width) -
    the latter three are what show()/`_on_mouse` need for click routing:
    board_offset/board_content_size for the existing canvas_to_native
    board-local translation, left_width to shift a canvas-space click
    into that board-local space first.
    """
    left_width, board_available_size, right_width = panel_regions(window_size, panel_width_px)
    board_canvas, board_content_size, board_offset = compose_letterboxed(board_frame, board_available_size)

    canvas = cv2.hconcat([left_panel_frame, board_canvas, right_panel_frame])

    return canvas, board_content_size, board_offset, left_width