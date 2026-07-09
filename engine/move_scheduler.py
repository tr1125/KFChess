"""Tracks pending moves and reports which ones are due.

MoveScheduler only knows "a move was requested, here's when it
completes" and "what's ready to settle now" - it has no opinion about
what settling should *do* (capture rules, cancellations, promotion).
That resolution logic belongs to GameEngine, which asks this class only
scheduling questions.
"""

from dataclasses import dataclass

from domain.piece_token import color_of


@dataclass
class PendingMove:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    complete_at_ms: int
    mover_token: str  # captured at scheduling time, not re-read from the board later


class MoveScheduler:
    def __init__(self):
        self._pending = []

    def schedule(self, from_row, from_col, to_row, to_col, complete_at_ms, mover_token):
        self._pending.append(
            PendingMove(from_row, from_col, to_row, to_col, complete_at_ms, mover_token)
        )

    def has_pending_from(self, row, col):
        return any(
            move.from_row == row and move.from_col == col for move in self._pending
        )

    def has_opposing_color_in_flight(self, color):
        return any(color_of(move.mover_token) != color for move in self._pending)

    def take_due(self, now_ms):
        """Remove and return every move whose time has come; the rest stay pending."""
        due = [move for move in self._pending if move.complete_at_ms <= now_ms]
        self._pending = [move for move in self._pending if move.complete_at_ms > now_ms]
        return due

    def clear(self):
        self._pending = []