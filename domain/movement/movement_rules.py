"""Movement legality checking.

MovementRules doesn't know what a king or a rook is - it only knows how
to ask whichever patterns are configured for a piece type whether a
destination is among the legal ones, and whether that destination's
occupancy satisfies what the pattern requires. Teaching it about a new
piece type - or a color-dependent one, like the pawn - means editing
config/piece_definitions.py, never this file.
"""

from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of, type_of
from domain.movement.requirement import ANY, MOVE_ONLY, CAPTURE_ONLY


class MovementRules:
    def __init__(self, patterns_by_piece_type):
        self._patterns_by_piece_type = patterns_by_piece_type

    def is_legal(self, mover_token, board, from_row, from_col, to_row, to_col):
        piece_type = type_of(mover_token)
        mover_color = color_of(mover_token)
        patterns = self._patterns_for(piece_type, mover_color)

        for pattern, requirement in patterns:
            if (to_row, to_col) not in pattern.destinations(board, from_row, from_col):
                continue

            target_token = board.get(to_row, to_col)
            if self._satisfies_requirement(requirement, target_token, mover_color):
                return True

        return False

    def _patterns_for(self, piece_type, mover_color):
        entry = self._patterns_by_piece_type.get(piece_type, [])
        if isinstance(entry, dict):
            # Color-dependent movement (e.g. pawns move opposite directions).
            return entry.get(mover_color, [])
        return entry

    @staticmethod
    def _satisfies_requirement(requirement, target_token, mover_color):
        is_empty = target_token == EMPTY_TOKEN
        if requirement == MOVE_ONLY:
            return is_empty
        if requirement == CAPTURE_ONLY:
            return not is_empty and color_of(target_token) != mover_color
        # ANY: empty is fine, capturing an enemy is fine, own color is not.
        return is_empty or color_of(target_token) != mover_color