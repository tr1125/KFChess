"""Movement legality checking.

MovementRules doesn't know what a king or a rook is - it only knows how
to ask whichever patterns are configured for a piece type whether a
destination is among the legal ones. Teaching it about a new piece type
means editing config/piece_definitions.py, never this file.

The "can't capture your own color" rule lives here, once, applied the
same way to every piece type - rather than duplicated inside each
pattern - because it isn't about a piece's shape, it's a single rule
that governs all of them equally.
"""

from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of, type_of


class MovementRules:
    def __init__(self, patterns_by_piece_type):
        self._patterns_by_piece_type = patterns_by_piece_type

    def is_legal(self, mover_token, board, from_row, from_col, to_row, to_col):
        piece_type = type_of(mover_token)
        mover_color = color_of(mover_token)
        patterns = self._patterns_by_piece_type.get(piece_type, [])

        for pattern in patterns:
            if (to_row, to_col) not in pattern.destinations(board, from_row, from_col):
                continue

            target_token = board.get(to_row, to_col)
            if target_token != EMPTY_TOKEN and color_of(target_token) == mover_color:
                continue  # destination holds a friendly piece - illegal

            return True

        return False