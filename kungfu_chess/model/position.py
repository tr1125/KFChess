"""Coordinate/position value type and the pure-geometry helpers that were
previously inlined inside board/piece/history code (square naming,
Chebyshev distance).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    row: int
    col: int


def square_name(position, board_height):
    """Algebraic-notation square name (e.g. "e4") for a position on a
    board of the given height. File letters run left-to-right from 'a';
    rank numbers count up from the bottom row.
    """
    file_letter = chr(ord("a") + position.col)
    rank_number = board_height - position.row
    return f"{file_letter}{rank_number}"


def parse_square_name(square, board_height):
    """Inverse of square_name(): "e4" on a board of the given height ->
    Position(row, col). Used to decode wire-protocol square names (see
    KFChess_Server_Plan.md's wire protocol reference) back into board
    coordinates.
    """
    file_letter, rank_digits = square[0], square[1:]
    col = ord(file_letter) - ord("a")
    row = board_height - int(rank_digits)
    return Position(row, col)


def chebyshev_distance(from_position, to_position):
    """max(row delta, col delta): the number of cells a king (or a
    sliding piece moving in a straight or diagonal line) must cross to
    get from one position to the other.
    """
    row_distance = abs(to_position.row - from_position.row)
    col_distance = abs(to_position.col - from_position.col)
    return max(row_distance, col_distance)