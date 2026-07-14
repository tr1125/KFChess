from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.io.board_printer import to_canonical


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def test_to_canonical_renders_rows_space_separated():
    board = board_from([["wK", ".", ".", "bK"], [".", ".", ".", "."]])
    assert to_canonical(board) == "wK . . bK\n. . . ."


def test_to_canonical_has_no_trailing_newline():
    board = board_from([["wK"]])
    rendered = to_canonical(board)
    assert not rendered.endswith("\n")


def test_to_canonical_empty_board_renders_empty_string():
    board = Board([])
    assert to_canonical(board) == ""


def test_to_canonical_round_trips_through_parse_board():
    from kungfu_chess.io.board_parser import parse_board

    original_lines = ["wK . . bK", ". . . .", "wR . . bR"]
    board = parse_board(original_lines)
    assert to_canonical(board) == "\n".join(original_lines)
