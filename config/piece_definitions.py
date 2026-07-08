"""Maps each piece letter to the movement patterns that define its legal
destinations. This is the file to edit - not engine or movement code -
when adding a new piece type or changing how one moves.

Most entries are a flat list of (pattern, requirement) pairs. A piece
whose movement depends on color (currently only the pawn) instead maps
to a dict keyed by "w"/"b" - MovementRules checks for this automatically.
"""

from domain.movement.patterns import StepPattern, SlidePattern
from domain.movement.requirement import ANY, MOVE_ONLY, CAPTURE_ONLY

_ORTHOGONAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAGONAL_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_KING_OFFSETS = _ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS
_KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1), (2, -1), (2, 1),
    (-1, -2), (-1, 2), (1, -2), (1, 2),
]

# ASSUMPTION: row index decreases going "up" the board - so white pawns
# move toward row 0, black pawns move toward higher row indices. This is
# a text-layout convention, not a chess rule, and nothing in the fixture
# format confirms it. If a VPL test expects the opposite, only these four
# offset lists need to flip - nothing else in this file or movement_rules.py.
_WHITE_PAWN_FORWARD = [(-1, 0)]
_WHITE_PAWN_CAPTURES = [(-1, -1), (-1, 1)]
_BLACK_PAWN_FORWARD = [(1, 0)]
_BLACK_PAWN_CAPTURES = [(1, -1), (1, 1)]

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
        ],
        "b": [
            (StepPattern(_BLACK_PAWN_FORWARD), MOVE_ONLY),
            (StepPattern(_BLACK_PAWN_CAPTURES), CAPTURE_ONLY),
        ],
    },
}