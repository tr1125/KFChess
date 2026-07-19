"""The Piece entity every other layer shares instead of a bare string
token, and the piece-type/color constants used throughout.
"""

import itertools
from dataclasses import dataclass, field
from enum import Enum, auto

KING_TYPE = "K"
QUEEN_TYPE = "Q"
ROOK_TYPE = "R"
BISHOP_TYPE = "B"
KNIGHT_TYPE = "N"
PAWN_TYPE = "P"

WHITE = "w"
BLACK = "b"

_id_counter = itertools.count(1)


class PieceState(Enum):
    IDLE = auto()  # not currently in transit
    MOVING = auto()  # has a pending (in-flight) move - see MotionTracker
    AIRBORNE = auto()  # airborne mid-jump - captures whatever lands on its cell
    LONG_REST = auto() # has been moving and is now resting for a long time (see MotionTracker)
    SHORT_REST = auto() # has been jumping and is now resting for a short time (see MotionTracker)
    CAPTURED = auto()  # has been eaten by an enemy piece

@dataclass(eq=False)
class Piece:
    """A single piece on the board. `id` is a runtime identity (not
    persisted through the text format - reparsing a board mints fresh
    ids), used so two same-kind-same-color pieces are never confused
    with each other (see RealTimeArbiter). `cell` is written only by
    Board, in the same method that moves the piece on the grid, so the
    two can never drift apart. `state` is written only by MotionTracker,
    as a side effect of scheduling/settling a move or jump.

    Deliberately `eq=False`: identity equality is what every caller
    actually wants (RealTimeArbiter asks "is this the same piece still
    here", not "is there a piece here with the same fields") - the
    dataclass-generated value equality would compare `cell`/`state` too
    and give the wrong answer for that question.
    """

    color: str
    kind: str
    cell: object = None  # Position
    state: PieceState = field(default=PieceState.IDLE)
    id: int = field(default_factory=lambda: next(_id_counter))

    def __str__(self):
        return f"{self.color}{self.kind}"

    def notation_prefix(self, origin_file, is_capture):
        """The SAN move prefix for this piece: pawns are identified by
        their origin file only on captures (and never by a letter), while
        every other piece is identified by its kind letter, plus an "x"
        on captures either way.
        """
        if self.kind == PAWN_TYPE:
            return f"{origin_file}x" if is_capture else ""
        return f"{self.kind}x" if is_capture else self.kind
