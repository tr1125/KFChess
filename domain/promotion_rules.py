"""Promotion rule lookup, mirroring MovementRules: knows nothing about
what a queen or a "far rank" *is* - only which configured PromotionRule,
if any, matches a piece landing on a given row. Teaching it about a new
promotion trigger (a different piece, a different rank, a future custom
variant) means editing config/piece_definitions.py, never this file or
engine code.
"""

from domain.piece_token import color_of, type_of


class PromotionRules:
    def __init__(self, rules):
        self._rules = rules  # list of PromotionRule

    def trigger_for(self, token, to_row, board):
        """Return the PromotionRule matching this token's arrival at
        to_row, or None if this landing doesn't trigger a promotion.
        """
        piece_type = type_of(token)
        color = color_of(token)
        for rule in self._rules:
            if rule.piece_type == piece_type and rule.color == color and rule.rank_for(board) == to_row:
                return rule
        return None