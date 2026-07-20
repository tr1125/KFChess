"""Positions an already-rendered promotion-menu frame (see
view/promotion_menu_view.py) over its promoted piece's board square, and
pastes it into the board frame.

Mirrors panel_layout.py's own split: menu_origin is pure geometry,
easily unit-tested without a window; composite_menu does the actual
numpy paste, testable with synthetic frames, no live window needed.
Runs entirely in board-native pixel space (see renderer.py's
BoardRenderer.pixel_position) - before compose_letterboxed/
compose_with_panels ever touch the frame - so the click-hit-testing
bounds driver/game_loop.py records for this menu line up directly with
the same native space canvas_to_native already produces.
"""


def menu_origin(square_x_px, square_y_px, cell_size_px, menu_w_px, menu_h_px, board_w_px, board_h_px):
    """(x_px, y_px) top-left corner for a menu_w_px x menu_h_px menu
    frame, centered horizontally over the square at (square_x_px,
    square_y_px) (top-left corner, size cell_size_px - see
    BoardRenderer.pixel_position/cell_size_px). Placed above the square
    by default, flipped below it if there's no room above (e.g. a
    promotion on the board's top row) - either way clamped to stay
    entirely within [0, board_w_px) x [0, board_h_px), the same
    best-effort clamping spirit as canvas_to_native's letterbox
    handling, just along different axes.
    """
    center_x = square_x_px + cell_size_px // 2
    x_px = center_x - menu_w_px // 2
    x_px = max(0, min(x_px, board_w_px - menu_w_px))

    y_px = square_y_px - menu_h_px  # default: directly above the square
    if y_px < 0:
        y_px = square_y_px + cell_size_px  # no room above - flip below instead
    y_px = max(0, min(y_px, board_h_px - menu_h_px))

    return x_px, y_px


def composite_menu(board_frame, menu_frame, x_px, y_px):
    """Pastes menu_frame onto board_frame at (x_px, y_px), mutating and
    returning board_frame. Clips to whatever of menu_frame actually
    falls within board_frame's bounds - defensive only, since
    menu_origin already keeps a menu fully on-board in the ordinary
    case; this just avoids a shape-mismatch crash on a pathological
    board narrower than the menu itself.
    """
    board_h, board_w = board_frame.shape[0], board_frame.shape[1]
    menu_h, menu_w = menu_frame.shape[0], menu_frame.shape[1]

    paste_w = min(menu_w, board_w - x_px)
    paste_h = min(menu_h, board_h - y_px)
    if paste_w <= 0 or paste_h <= 0:
        return board_frame

    board_frame[y_px:y_px + paste_h, x_px:x_px + paste_w] = menu_frame[:paste_h, :paste_w]
    return board_frame