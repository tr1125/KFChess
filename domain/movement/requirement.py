"""Occupancy requirements a pattern's destination may need to satisfy.

Most pieces can land on an empty square or capture an enemy piece -
that's ANY (still subject to the universal "never capture your own
color" rule enforced by MovementRules). The pawn is the first piece
whose quiet move and its capture are two genuinely different patterns:
MOVE_ONLY (must be empty - no forward captures) and CAPTURE_ONLY (must
hold an enemy piece - no diagonal moves into empty squares).
"""

ANY = "any"
MOVE_ONLY = "move_only"
CAPTURE_ONLY = "capture_only"