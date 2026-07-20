import numpy as np

from kungfu_chess.driver.promotion_menu_layout import composite_menu, menu_origin


def make_frame(height, width, fill_value):
    return np.full((height, width, 3), fill_value, dtype=np.uint8)


# --- menu_origin ---


def test_menu_origin_centers_horizontally_over_the_square():
    x, y = menu_origin(
        square_x_px=100, square_y_px=200, cell_size_px=50,
        menu_w_px=30, menu_h_px=20, board_w_px=1000, board_h_px=1000,
    )
    # square center = 100 + 25 = 125; menu centered there = 125 - 15 = 110
    assert x == 110


def test_menu_origin_places_menu_directly_above_the_square_by_default():
    x, y = menu_origin(
        square_x_px=100, square_y_px=200, cell_size_px=50,
        menu_w_px=30, menu_h_px=20, board_w_px=1000, board_h_px=1000,
    )
    assert y == 200 - 20


def test_menu_origin_flips_below_the_square_when_no_room_above():
    x, y = menu_origin(
        square_x_px=100, square_y_px=5, cell_size_px=50,
        menu_w_px=30, menu_h_px=20, board_w_px=1000, board_h_px=1000,
    )
    assert y == 5 + 50  # below the square instead


def test_menu_origin_clamps_horizontally_to_stay_on_board():
    x, y = menu_origin(
        square_x_px=0, square_y_px=200, cell_size_px=50,
        menu_w_px=200, menu_h_px=20, board_w_px=100, board_h_px=1000,
    )
    assert x == 0  # would go negative otherwise - clamped to the left edge
    assert x + 200 <= 100 or x == 0  # menu wider than the board - best effort


def test_menu_origin_clamps_vertically_to_stay_on_board():
    x, y = menu_origin(
        square_x_px=100, square_y_px=990, cell_size_px=50,
        menu_w_px=30, menu_h_px=20, board_w_px=1000, board_h_px=1000,
    )
    assert y <= 1000 - 20


# --- composite_menu ---


def test_composite_menu_pastes_menu_frame_at_given_origin():
    board_frame = make_frame(100, 100, 0)
    menu_frame = make_frame(10, 20, 255)

    result = composite_menu(board_frame, menu_frame, x_px=5, y_px=10)

    assert (result[10:20, 5:25] == 255).all()
    assert (result[0:10, 0:100] == 0).all()  # untouched region above the paste


def test_composite_menu_clips_when_menu_would_overflow_the_board():
    board_frame = make_frame(20, 20, 0)
    menu_frame = make_frame(10, 10, 255)

    result = composite_menu(board_frame, menu_frame, x_px=15, y_px=15)

    assert result.shape == (20, 20, 3)  # no crash, no shape change
    assert (result[15:20, 15:20] == 255).all()


def test_composite_menu_is_a_no_op_when_origin_is_entirely_off_board():
    board_frame = make_frame(20, 20, 7)
    menu_frame = make_frame(10, 10, 255)

    result = composite_menu(board_frame, menu_frame, x_px=25, y_px=25)

    assert (result == 7).all()