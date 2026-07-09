"""Tracks pieces awaiting a promotion choice from the user.

Same philosophy as MoveScheduler/JumpScheduler: only scheduling
questions here - what's pending, and what choices are legal for it - no
opinion on how a choice gets made or applied to the board. That belongs
to GameEngine, the one place user input turns into board changes.
"""

from dataclasses import dataclass


@dataclass
class PendingPromotion:
    row: int
    col: int
    color: str
    choices: tuple


class PromotionScheduler:
    def __init__(self):
        self._pending = []

    def schedule(self, row, col, color, choices):
        self._pending.append(PendingPromotion(row, col, color, choices))

    def get(self, row, col):
        """Return the pending promotion at (row, col) without removing it, or None."""
        for pending in self._pending:
            if pending.row == row and pending.col == col:
                return pending
        return None

    def take(self, row, col):
        """Remove and return the pending promotion at (row, col), or None."""
        pending = self.get(row, col)
        if pending is not None:
            self._pending.remove(pending)
        return pending

    def has_any(self):
        return len(self._pending) > 0

    def pending(self):
        return list(self._pending)

    def clear(self):
        self._pending = []