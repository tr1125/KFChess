"""Game clock abstraction.

The game does not run in wall-clock time - it only advances when a
'wait' command is processed. ManualClock is the sole implementation for
now. If a future mode needs real time (e.g. a live multiplayer server),
it can add a WallClock implementing the same two methods (now, advance)
without GameEngine changing at all.
"""


class ManualClock:
    def __init__(self):
        self._now_ms = 0

    def now(self):
        return self._now_ms

    def advance(self, ms):
        self._now_ms += ms