from kungfu_chess.model.position import Position
from kungfu_chess.input.board_mapper import BoardMapper


def test_cell_at_top_left_pixel():
    mapper = BoardMapper(cell_size_px=100)
    assert mapper.cell_at(0, 0) == Position(0, 0)


def test_cell_at_maps_pixels_within_a_cell_to_the_same_cell():
    mapper = BoardMapper(cell_size_px=100)
    assert mapper.cell_at(50, 50) == Position(0, 0)
    assert mapper.cell_at(99, 99) == Position(0, 0)


def test_cell_at_second_row_and_column():
    mapper = BoardMapper(cell_size_px=100)
    assert mapper.cell_at(150, 250) == Position(2, 1)


def test_cell_at_respects_configured_cell_size():
    mapper = BoardMapper(cell_size_px=50)
    assert mapper.cell_at(120, 60) == Position(1, 2)


def test_cell_at_negative_pixels_maps_to_negative_cell():
    mapper = BoardMapper(cell_size_px=100)
    assert mapper.cell_at(-10, -10) == Position(-1, -1)