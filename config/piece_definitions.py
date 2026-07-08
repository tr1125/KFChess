"""Maps each piece letter to the movement patterns that define its legal
destinations. This is the file to edit - not engine or movement code -
when adding a new piece type or changing how one moves.
"""

from domain.movement.patterns import StepPattern, SlidePattern

_ORTHOGONAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAGONAL_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_KING_OFFSETS = _ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS
_KNIGHT_OFFSETS = [
    (-2, -1), (-2, 1), (2, -1), (2, 1),
    (-1, -2), (-1, 2), (1, -2), (1, 2),
]

PIECE_MOVEMENT_PATTERNS = {
    "K": [StepPattern(_KING_OFFSETS)],
    "Q": [SlidePattern(_ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS)],
    "R": [SlidePattern(_ORTHOGONAL_DIRECTIONS)],
    "B": [SlidePattern(_DIAGONAL_DIRECTIONS)],
    "N": [StepPattern(_KNIGHT_OFFSETS)],
    # "P" (pawn) intentionally omitted - not part of this iteration's scope.
}