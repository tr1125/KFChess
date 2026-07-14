import pytest

from kungfu_chess.io.board_parser import parse_board, BoardFormatError
from kungfu_chess.model.position import Position


def _signature(piece):
    return None if piece is None else (piece.color, piece.kind)


def test_parse_rectangular_board():
    board = parse_board(["wK . . bK", ". . . .", "wR . . bR"])
    assert board.height == 3
    assert board.width == 4
    assert _signature(board.get(0, 0)) == ("w", "K")
    assert _signature(board.get(0, 3)) == ("b", "K")
    assert board.get(1, 1) is None


def test_parse_sets_each_piece_cell_to_its_position():
    board = parse_board(["wK . . bK"])
    assert board.get(0, 0).cell == Position(0, 0)
    assert board.get(0, 3).cell == Position(0, 3)


def test_parse_accepts_every_standard_piece_and_color():
    board = parse_board(["wK . bQ", ". wN .", "bP . wR"])
    assert _signature(board.get(0, 2)) == ("b", "Q")
    assert _signature(board.get(1, 1)) == ("w", "N")
    assert _signature(board.get(2, 0)) == ("b", "P")


def test_parse_empty_lines_yields_empty_board():
    board = parse_board([])
    assert board.height == 0
    assert board.width == 0


def test_reject_unknown_token():
    with pytest.raises(BoardFormatError) as exc_info:
        parse_board(["wK xZ", ". ."])
    assert exc_info.value.code == "UNKNOWN_TOKEN"


def test_reject_row_width_mismatch():
    with pytest.raises(BoardFormatError) as exc_info:
        parse_board(["wK . .", ". bK"])
    assert exc_info.value.code == "ROW_WIDTH_MISMATCH"


def test_reject_lowercase_piece_letter_as_unknown():
    with pytest.raises(BoardFormatError) as exc_info:
        parse_board(["wk ."])
    assert exc_info.value.code == "UNKNOWN_TOKEN"


def test_reject_unknown_color_prefix():
    with pytest.raises(BoardFormatError) as exc_info:
        parse_board(["xK ."])
    assert exc_info.value.code == "UNKNOWN_TOKEN"