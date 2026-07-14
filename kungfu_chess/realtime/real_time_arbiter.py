"""Decides what happens when a due move collides with real-time state:
the mover vanished before the move came due, the destination is
friendly-occupied, an airborne defender is waiting there, or none of
that applies and the move is clear to settle.

RealTimeArbiter only classifies - it never mutates the board or game
state itself. Applying the consequences of a classification (recording
history/score, moving pieces) is the rules layer's job, orchestrated by
the engine.
"""

from dataclasses import dataclass
from enum import Enum, auto


class CollisionKind(Enum):
    MOVER_GONE = auto()  # the mover itself is no longer at its source cell
    FRIENDLY_CANCEL = auto()  # destination is occupied by the mover's own color
    AIRBORNE_CAPTURE = auto()  # destination holds an airborne enemy defender
    CLEAR = auto()  # nothing in the way; safe to settle as a normal move


@dataclass(frozen=True)
class CollisionOutcome:
    kind: CollisionKind
    move: object  # the PendingMove this outcome was classified from
    defender_piece: object = None  # set only for AIRBORNE_CAPTURE


class RealTimeArbiter:
    def classify(self, board, motion, move):
        current_piece = board.get(move.from_position.row, move.from_position.col)
        if current_piece is not move.piece:
            # The mover itself is gone - nothing to move.
            return CollisionOutcome(CollisionKind.MOVER_GONE, move)

        target_piece = board.get(move.to_position.row, move.to_position.col)

        if target_piece is not None and target_piece.color == move.piece.color:
            # Destination is friendly-occupied - cancel silently.
            return CollisionOutcome(CollisionKind.FRIENDLY_CANCEL, move)

        if target_piece is not None and motion.is_airborne(move.to_position):
            # The defender is airborne and the arriver is an enemy (the
            # friendly case was already handled above): the airborne
            # piece captures the arriver instead of being captured.
            return CollisionOutcome(
                CollisionKind.AIRBORNE_CAPTURE, move, defender_piece=target_piece
            )

        return CollisionOutcome(CollisionKind.CLEAR, move)