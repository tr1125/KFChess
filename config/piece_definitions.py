"""Maps each piece letter to the movement patterns that define its legal
destinations. This is the file to edit - not engine or movement code -
when adding a new piece type or changing how one moves.

Most entries are a flat list of (pattern, requirement) pairs. A piece
whose movement depends on color (currently only the pawn) instead maps
to a dict keyed by "w"/"b" - MovementRules checks for this automatically.
"""

from domain.movement.patterns import StepPattern, SlidePattern, PawnDoubleStepPattern
from domain.movement.requirement import ANY, MOVE_ONLY, CAPTURE_ONLY
from domain.promotion_rule import PromotionRule
from domain.piece_token import (
    KING_TYPE,
    QUEEN_TYPE,
    ROOK_TYPE,
    BISHOP_TYPE,
    KNIGHT_TYPE,
    PAWN_TYPE,
)

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

# Standard chess piece values, used for score display. The king's value
# is never actually awarded - capturing it ends the game first - but 0
# keeps the lookup total for every piece type.
PIECE_VALUES = {
    KING_TYPE: 0,
    QUEEN_TYPE: 9,
    ROOK_TYPE: 5,
    BISHOP_TYPE: 3,
    KNIGHT_TYPE: 3,
    PAWN_TYPE: 1,
}

# Every piece type in `choices` a promotion may become. Kept separate
# from PROMOTION_RULES below so multiple rules can share it.
_STANDARD_PROMOTION_CHOICES = (QUEEN_TYPE, ROOK_TYPE, BISHOP_TYPE, KNIGHT_TYPE)

# Which piece becomes eligible to promote, on which rank, and what it
# may become. To change the trigger (e.g. a knight promoting on the 4th
# rank instead) add/edit an entry here - PromotionRules and MoveResolver
# never hardcode a piece type or rank, so no other file needs to change.
# `rank` may be a fixed row index or a callable(board) -> row index for
# ranks defined relative to board size, exactly like the pawn start-row
# lambdas above.
PROMOTION_RULES = [
    PromotionRule(PAWN_TYPE, "w", 0, _STANDARD_PROMOTION_CHOICES),
    PromotionRule(PAWN_TYPE, "b", lambda board: board.height - 1, _STANDARD_PROMOTION_CHOICES),
]

PIECE_MOVEMENT_PATTERNS = {
    KING_TYPE: [(StepPattern(_KING_OFFSETS), ANY)],
    QUEEN_TYPE: [(SlidePattern(_ORTHOGONAL_DIRECTIONS + _DIAGONAL_DIRECTIONS), ANY)],
    ROOK_TYPE: [(SlidePattern(_ORTHOGONAL_DIRECTIONS), ANY)],
    BISHOP_TYPE: [(SlidePattern(_DIAGONAL_DIRECTIONS), ANY)],
    KNIGHT_TYPE: [(StepPattern(_KNIGHT_OFFSETS), ANY)],
    PAWN_TYPE: {
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