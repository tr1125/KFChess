from kungfu_chess.model.position import Position, square_name, parse_square_name, chebyshev_distance


def test_position_equality_by_value():
    assert Position(1, 2) == Position(1, 2)
    assert Position(1, 2) != Position(2, 1)


def test_square_name_bottom_left_is_a1_on_8_row_board():
    assert square_name(Position(7, 0), board_height=8) == "a1"


def test_square_name_top_right_is_h8_on_8_row_board():
    assert square_name(Position(0, 7), board_height=8) == "h8"


def test_square_name_uses_board_height_not_a_fixed_8():
    assert square_name(Position(0, 0), board_height=4) == "a4"


def test_parse_square_name_bottom_left_is_a1_on_8_row_board():
    assert parse_square_name("a1", board_height=8) == Position(7, 0)


def test_parse_square_name_top_right_is_h8_on_8_row_board():
    assert parse_square_name("h8", board_height=8) == Position(0, 7)


def test_parse_square_name_uses_board_height_not_a_fixed_8():
    assert parse_square_name("a4", board_height=4) == Position(0, 0)


def test_parse_square_name_is_the_inverse_of_square_name():
    position = Position(3, 5)
    assert parse_square_name(square_name(position, board_height=8), board_height=8) == position


def test_chebyshev_distance_straight_line():
    assert chebyshev_distance(Position(0, 0), Position(0, 4)) == 4


def test_chebyshev_distance_diagonal_line():
    assert chebyshev_distance(Position(0, 0), Position(3, 3)) == 3


def test_chebyshev_distance_takes_the_larger_delta():
    assert chebyshev_distance(Position(0, 0), Position(2, 5)) == 5


def test_chebyshev_distance_is_symmetric():
    assert chebyshev_distance(Position(2, 5), Position(0, 0)) == 5


def test_chebyshev_distance_zero_for_same_position():
    assert chebyshev_distance(Position(3, 3), Position(3, 3)) == 0