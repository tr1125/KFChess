"""Maps each piece letter to the movement patterns that define its legal
destinations. This is the file to edit - not engine or movement code -
when adding a new piece type or changing how one moves.

Most entries are a flat list of (pattern, requirement) pairs. A piece
whose movement depends on color (currently only the pawn) instead maps
to a dict keyed by "w"/"b" - MovementRules checks for this automatically.
"""

from domain.movement.patterns import StepPattern, SlidePattern, PawnDoubleStepPattern
from domain.movement.requirement import ANY, MOVE_ONLY, CAPTURE_ONLY

_ORTHOGONAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAGONAL_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_KING_OFFSETS = _ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS
_KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1), (2, -1), (2, 1),
    (-1, -2), (-1, 2), (1, -2), (1, 2),
]

# White moves toward row 0, black moves toward higher row indices
# (confirmed convention - see movement_rules tests).
_WHITE_PAWN_FORWARD = [(-1, 0)]
_WHITE_PAWN_CAPTURES = [(-1, -1), (-1, 1)]
_BLACK_PAWN_FORWARD = [(1, 0)]
_BLACK_PAWN_CAPTURES = [(1, -1), (1, 1)]

# Start row for the two-square push: confirmed by VPL tests to be the
# board's literal edge row for each color - white on the last row
# (height - 1), black on row 0 - not one row in from the edge like real
# chess. A previous version used (height - 2) for white and a hardcoded
# 1 for black; both were wrong (VPL rejected a white pawn's double push
# from height-2 as "not start row", and accepted one from height-1).
_WHITE_PAWN_START_ROW = lambda board: board.height - 1
_BLACK_PAWN_START_ROW = lambda board: 0

PIECE_MOVEMENT_PATTERNS = {
    "K": [(StepPattern(_KING_OFFSETS), ANY)],
    "Q": [(SlidePattern(_ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS), ANY)],
    "R": [(SlidePattern(_ORTHOGONAL_DIRECTIONS), ANY)],
    "B": [(SlidePattern(_DIAGONAL_DIRECTIONS), ANY)],
    "N": [(StepPattern(_KNIGHT_OFFSETS), ANY)],
    "P": {
        "w": [
            (StepPattern(_WHITE_PAWN_FORWARD), MOVE_ONLY),
            (StepPattern(_WHITE_PAWN_CAPTURES), CAPTURE_ONLY),
            (PawnDoubleStepPattern((-1, 0), _WHITE_PAWN_START_ROW), MOVE_ONLY),
        ],
        "b": [
            (StepPattern(_BLACK_PAWN_FORWARD), MOVE_ONLY),
            (StepPattern(_BLACK_PAWN_CAPTURES), CAPTURE_ONLY),
            (PawnDoubleStepPattern((1, 0), _BLACK_PAWN_START_ROW), MOVE_ONLY),
        ],
    },
}