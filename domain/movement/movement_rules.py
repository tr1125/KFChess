"""Movement legality checking.

MovementRules doesn't know what a king or a rook is - it only knows how
to ask whichever patterns are configured for a piece type whether a
destination is among the legal ones. Teaching it about a new piece type
means editing config/piece_definitions.py, never this file.
"""


class MovementRules:
    def __init__(self, patterns_by_piece_type):
        self._patterns_by_piece_type = patterns_by_piece_type

    def is_legal(self, piece_type, board, from_row, from_col, to_row, to_col):
        patterns = self._patterns_by_piece_type.get(piece_type, [])
        for pattern in patterns:
            if (to_row, to_col) in pattern.destinations(board, from_row, from_col):
                return True
        return False