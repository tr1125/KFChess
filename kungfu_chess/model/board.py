"""Minimal grid-of-pieces board representation: storage and low-level
mutation primitives only, no rules, timing, or I/O. That keeps it
swappable later (e.g. for a binary representation) without touching
rules, engine, or io code.

Cells hold a Piece or None - EMPTY_TOKEN below is not used internally
(it is the text I/O marker for an empty cell; see io/board_parser.py
and io/board_printer.py, the only other files that know it).
"""

from kungfu_chess.model.position import Position

EMPTY_TOKEN = "."


class Board:
    def __init__(self, rows):
        """rows: list of list[Piece | None], already validated by the caller."""
        self._rows = [list(row) for row in rows]

    @property
    def height(self):
        return len(self._rows)

    @property
    def width(self):
        return len(self._rows[0]) if self._rows else 0

    def in_bounds(self, row, col):
        return 0 <= row < self.height and 0 <= col < self.width

    def get(self, row, col):
        return self._rows[row][col]

    def apply_move(self, from_row, from_col, to_row, to_col):
        """Move whatever piece is at (from_row, from_col) to (to_row, to_col),
        updating that piece's own `cell` to match.

        Overwrites whatever was at the destination - this is what makes a
        capture "just a move" instead of a special case.
        """
        piece = self._rows[from_row][from_col]
        self._rows[from_row][from_col] = None
        self._rows[to_row][to_col] = piece
        piece.cell = Position(to_row, to_col)

    def promote(self, row, col, kind):
        """Turn the piece at (row, col) into a different kind in place
        (pawn promotion) - same piece, same id, same cell.
        """
        self._rows[row][col].kind = kind

    def remove(self, row, col):
        """Clear a cell entirely (a piece that's gone, not moved anywhere)."""
        self._rows[row][col] = None

    def rows(self):
        """Return a defensive copy so callers can't mutate internal state."""
        return [list(row) for row in self._rows]