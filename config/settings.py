"""Game constants.

Kept here instead of as literals inside engine/board code, so a future
change (e.g. move duration depending on piece type or distance) only
touches this file and whatever loads it - not the logic that uses it.
"""

CELL_SIZE_PX = 100

# ASSUMPTION: flat move duration regardless of piece type or distance.
# The only test data available (iteration 2 fixtures) shows a single-cell
# move settling within 1000ms of being requested; there is no test data
# yet that distinguishes "always 1000ms" from "1000ms per cell of
# distance" or "duration depends on piece type". If that turns out to be
# wrong, this is the only line that needs to change - GameEngine just
# asks a MoveTimingPolicy-like source for a duration, it doesn't compute one.
MOVE_DURATION_MS = 1000