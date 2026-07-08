"""Generic movement pattern primitives.

These two building blocks are all a piece's movement is made from.
Adding a new piece - standard or a user-defined custom one later - means
adding a config entry that composes these; it never means writing a new
pattern class or touching engine code.
"""


class StepPattern:
    """A single fixed offset hop (e.g. a king's one square, a knight's
    L-shape). Exactly one candidate destination per offset, regardless
    of what occupies it - the board is only consulted for bounds.
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
    """Repeated movement along a direction until the board edge.

    NOTE: this iteration's spec only asks for shape legality ("a rook
    moving diagonally is illegal"), not blocking by pieces in the way.
    Blocking is intentionally not implemented here - see
    config/piece_definitions.py for where to add it when it's needed.
    """

    def __init__(self, directions):
        self._directions = directions  # list of (delta_row, delta_col)

    def destinations(self, board, row, col):
        results = []
        for delta_row, delta_col in self._directions:
            target_row, target_col = row + delta_row, col + delta_col
            while board.in_bounds(target_row, target_col):
                results.append((target_row, target_col))
                target_row += delta_row
                target_col += delta_col
        return results