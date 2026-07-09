"""Tracks which pieces are currently airborne (mid-jump).

Same philosophy as MoveScheduler: only scheduling questions here (is this
cell airborne, has the jump window elapsed) - not what an arrival during
the window should *do* (that's GameEngine's capture-in-air rule).
"""

from dataclasses import dataclass


@dataclass
class AirborneJump:
    row: int
    col: int
    token: str
    land_at_ms: int


class JumpScheduler:
    def __init__(self):
        self._airborne = []

    def schedule(self, row, col, token, land_at_ms):
        self._airborne.append(AirborneJump(row, col, token, land_at_ms))

    def is_airborne(self, row, col):
        return any(jump.row == row and jump.col == col for jump in self._airborne)

    def land_due(self, now_ms):
        """Drop every jump whose window has elapsed. No board change is
        needed here - the piece stayed on its cell the whole time, so
        simply no longer being tracked here *is* landing."""
        self._airborne = [jump for jump in self._airborne if jump.land_at_ms > now_ms]

    def clear(self):
        self._airborne = []