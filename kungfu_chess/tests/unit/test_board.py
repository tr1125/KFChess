from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position


def make_board():
    white_rook = Piece(color="w", kind="R", cell=Position(0, 0))
    black_king = Piece(color="b", kind="K", cell=Position(2, 2))
    rows = [
        [white_rook, None, None],
        [None, None, None],
        [None, None, black_king],
    ]
    return Board(rows)


def _signature(piece):
    """None for an empty cell, else (color, kind) - Piece deliberately has
    no value equality (see test_piece.py), so tests compare this instead.
    """
    return None if piece is None else (piece.color, piece.kind)


def test_height_and_width():
    board = make_board()
    assert board.height == 3
    assert board.width == 3


def test_height_and_width_of_empty_board():
    board = Board([])
    assert board.height == 0
    assert board.width == 0


def test_in_bounds_true_for_valid_cell():
    assert make_board().in_bounds(0, 0)
    assert make_board().in_bounds(2, 2)


def test_in_bounds_false_for_negative_or_out_of_range():
    board = make_board()
    assert not board.in_bounds(-1, 0)
    assert not board.in_bounds(0, -1)
    assert not board.in_bounds(3, 0)
    assert not board.in_bounds(0, 3)


def test_get_returns_piece_at_cell():
    board = make_board()
    assert _signature(board.get(0, 0)) == ("w", "R")
    assert board.get(1, 1) is None


def test_apply_move_relocates_piece_and_empties_source():
    board = make_board()
    mover = board.get(0, 0)
    board.apply_move(0, 0, 1, 1)
    assert board.get(0, 0) is None
    assert board.get(1, 1) is mover
    assert mover.cell == Position(1, 1)


def test_apply_move_overwrites_destination_capture_is_just_a_move():
    rook = Piece(color="w", kind="R", cell=Position(0, 0))
    knight = Piece(color="b", kind="N", cell=Position(0, 1))
    board = Board([[rook, knight]])
    board.apply_move(0, 0, 0, 1)
    assert board.get(0, 0) is None
    assert board.get(0, 1) is rook


def test_promote_changes_kind_in_place():
    board = make_board()
    original = board.get(0, 0)
    board.promote(0, 0, "Q")
    assert board.get(0, 0) is original
    assert board.get(0, 0).kind == "Q"
    assert board.get(0, 0).color == "w"


def test_remove_clears_cell():
    board = make_board()
    board.remove(0, 0)
    assert board.get(0, 0) is None


def test_rows_returns_a_defensive_copy():
    board = make_board()
    snapshot = board.rows()
    snapshot[0][0] = None
    assert _signature(board.get(0, 0)) == ("w", "R")


def test_rows_reflects_current_state():
    board = make_board()
    board.apply_move(0, 0, 1, 1)
    assert [[_signature(piece) for piece in row] for row in board.rows()] == [
        [None, None, None],
        [None, ("w", "R"), None],
        [None, None, ("b", "K")],
    ]
