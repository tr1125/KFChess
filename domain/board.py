"""Minimal board representation.
 
Holds the parsed grid of tokens and its dimensions. Deliberately knows
nothing about pieces, rules, or I/O - that keeps it swappable later
(e.g. for a binary representation) without touching parsing/printing code.
"""
 
 
class Board:
    def __init__(self, rows):
        """rows: list of list[str] tokens, already validated by the caller."""
        self._rows = rows
 
    @property
    def height(self):
        return len(self._rows)
 
    @property
    def width(self):
        return len(self._rows[0]) if self._rows else 0
 
    def rows(self):
        """Return a defensive copy so callers can't mutate internal state."""
        return [list(row) for row in self._rows]
 