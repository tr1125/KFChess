"""Game constants.

Kept here instead of as literals inside engine/board code, so a future
change (e.g. move duration depending on piece type or distance) only
touches this file and whatever loads it - not the logic that uses it.
"""

CELL_SIZE_PX = 100

# Duration is per cell of distance traveled - confirmed by a VPL test
# where a 2-cell rook move took exactly 2000ms to settle, not 1000ms.
# distance = Chebyshev distance (max of row/col delta), which matches
# straight and diagonal sliding moves exactly.
#
# ASSUMPTION still open: knight distance under this same Chebyshev
# formula gives 2 (e.g. offset (2,1) -> max(2,1)=2), i.e. 2000ms for a
# knight hop. No test data confirms or denies this yet - a knight isn't
# a sliding piece, so "distance" is a less natural concept for it. If a
# test disagrees, this is the one formula (in engine/game_engine.py) to
# revisit for knight-specific handling.
MOVE_DURATION_PER_CELL_MS = 1000

# A jump keeps the piece on its own cell but makes it "airborne" for this
# long. If an enemy's move lands on that cell during the window, the
# airborne piece captures the arriving enemy instead of being captured.
JUMP_DURATION_MS = 1000