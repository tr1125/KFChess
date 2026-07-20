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
    state_entered_at: int = field(default=0)  # clock ms when `state` last changed - see MotionTracker
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


def passes_as_empty(occupant, mover_color):
    """Whether `occupant` should be treated as empty for a mover of
    `mover_color`: either the cell truly is empty, or `occupant` is an
    enemy piece currently AIRBORNE. A piece jumps in place - it never
    relocates - but while it's mid-jump its own cell is *logically*
    vacated for every other mover's path/occupancy checks (real-time
    collision only happens at the jump's own landing instant - see
    RealTimeArbiter and GameEngine._land_due_jumps). The board itself is
    never touched by this - `occupant` still physically sits on the grid
    for rendering the whole time.

    Deliberately color-asymmetric: a piece's own airborne teammate is
    NOT covered by this - it's an ordinary friendly occupant, blocking
    like any other (no plausible way for two same-color pieces to want
    the same cell, so this is never relaxed for friendlies).
    """
    return occupant is None or (
        occupant.color != mover_color and occupant.state == PieceState.AIRBORNE
    )
