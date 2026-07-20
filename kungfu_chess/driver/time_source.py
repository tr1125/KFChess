"""Abstract time-source contract for the driver loop, and its local
implementation.

The engine's own clock (ManualClock, see realtime/motion.py) only
advances when something calls wait(ms) - it has no notion of real time.
The driver layer is what supplies that: each frame it measures elapsed
real time and turns it into a wait(ms) call. Any TimeSource just needs
a now_ms() method (duck-typed, matching the ManualClock/WallClock
contract already documented in motion.py - no formal ABC, consistent
with how the rest of the codebase does strategy-style interfaces, e.g.
StepPattern/SlidePattern in rules/piece_rules.py).

WallClock is the only implementation for now, backed by time.time() -
measured independently every frame so the game clock never freezes
because of a render hiccup (window resize, GC pause, etc.). A future
networked/synced clock can implement the same now_ms() method without
game_loop.py changing at all.
"""

import time


class WallClock:
    def now_ms(self):
        return time.time() * 1000.0