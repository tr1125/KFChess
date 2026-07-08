"""Generic movement pattern primitives.

These two building blocks are all a piece's movement is made from.
Adding a new piece - standard or a user-defined custom one later - means
adding a config entry that composes these; it never means writing a new
pattern class or touching engine code.
"""

from domain.board import EMPTY_TOKEN


class StepPattern:
    """A single fixed offset hop (e.g. a king's one square, a knight's
    L-shape). Exactly one candidate destination per offset. There is no
    "path" to block for a single hop - that's why a knight jumps over
    blockers - so this pattern never looks at occupancy, only bounds.
    """

    def __init__(self, offsets):
        self._offsets = offsets  # list of (delta_row, delta_col)

    def destinations(self, board, row, col):
        results = []
        for delta_row, delta_col in self._offsets:
            target_row, target_col = row + delta_row, col + delta_col
            if board.in_bounds(target_row, target_col):
                results.append((target_row, target_col))
        return results


class SlidePattern:
    """Repeated movement along a direction until the board edge OR until
    an occupied cell is reached. The occupied cell itself is included as
    a candidate (a capture may be legal there); nothing past it is,
    since another piece is in the way. Whether landing on that occupied
    cell is *actually* legal (same color = no) is decided by
    MovementRules, not here - this class only knows geometry + occupancy,
    not whose piece is whose.
    """

    def __init__(self, directions):
        self._directions = directions  # list of (delta_row, delta_col)

    def destinations(self, board, row, col):
        results = []
        for delta_row, delta_col in self._directions:
            target_row, target_col = row + delta_row, col + delta_col
            while board.in_bounds(target_row, target_col):
                results.append((target_row, target_col))
                if board.get(target_row, target_col) != EMPTY_TOKEN:
                    break  # path blocked beyond this cell
                target_row += delta_row
                target_col += delta_col
        return results