"""Minimal board representation.

Holds the grid of tokens and its dimensions, and knows how to move a
token from one cell to another. Deliberately knows nothing about click
handling, timing, or I/O - that keeps it swappable later (e.g. for a
binary representation) without touching engine or parsing/printing code.
"""

EMPTY_TOKEN = "."


class Board:
    def __init__(self, rows):
        """rows: list of list[str] tokens, already validated by the caller."""
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
        """Move whatever token is at (from_row, from_col) to (to_row, to_col).

        Overwrites whatever was at the destination - this is what makes a
        capture "just a move" instead of a special case.
        """
        token = self._rows[from_row][from_col]
        self._rows[from_row][from_col] = EMPTY_TOKEN
        self._rows[to_row][to_col] = token

    def promote(self, row, col, token):
        """Replace the token at (row, col) with a new one (pawn promotion)."""
        self._rows[row][col] = token

    def rows(self):
        """Return a defensive copy so callers can't mutate internal state."""
        return [list(row) for row in self._rows]