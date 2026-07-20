"""Decides what happens when a due move leg collides with real-time
state: the mover vanished before the leg came due, the leg's target cell
is friendly-occupied (stop), enemy-occupied and grounded (capture and
stop), or none of that applies and the leg is clear to advance (either
truly empty, or a safely-passable enemy piece currently airborne - see
passes_as_empty).

RealTimeArbiter only classifies - it never mutates the board or game
state itself. Applying the consequences of a classification (recording
history/score, moving pieces, continuing to the next leg) is the rules
layer's job, orchestrated by the engine.
"""
from dataclasses import dataclass
from enum import Enum, auto

from kungfu_chess.model.piece import passes_as_empty


class CollisionKind(Enum):
    MOVER_GONE = auto()  # the mover itself is no longer at its current leg position
    FRIENDLY_BLOCK = auto()  # leg target is occupied by the mover's own color - stop before entering it
    ENEMY_CAPTURE = auto()  # leg target holds a grounded enemy - capture it and stop there
    CLEAR = auto()  # nothing in the way (or a safely-passable airborne enemy) - advance normally


@dataclass(frozen=True)
class CollisionOutcome:
    kind: CollisionKind
    move: object  # the PendingMove this outcome was classified from


class RealTimeArbiter:
    def classify(self, board, move):
        current_piece = board.get(move.current_position.row, move.current_position.col)
        if current_piece is not move.piece:
            # The mover itself is gone - nothing to advance.
            return CollisionOutcome(CollisionKind.MOVER_GONE, move)

        target_piece = board.get(move.leg_target.row, move.leg_target.col)

        if target_piece is not None and target_piece.color == move.piece.color:
            # Leg target is friendly-occupied - stop before entering it.
            return CollisionOutcome(CollisionKind.FRIENDLY_BLOCK, move)

        if target_piece is not None and not passes_as_empty(target_piece, move.piece.color):
            # A grounded enemy - captured by advancing into its cell.
            return CollisionOutcome(CollisionKind.ENEMY_CAPTURE, move)

        # Either truly empty, or an enemy currently airborne: safe to
        # advance into (see passes_as_empty) - any real collision with an
        # airborne piece only happens at its own landing instant, not here.
        return CollisionOutcome(CollisionKind.CLEAR, move)
