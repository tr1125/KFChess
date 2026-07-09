"""A single promotion trigger: a piece of a given color reaching a given
rank becomes eligible to promote into one of `choices`. This is the
building block PROMOTION_RULES in config/piece_definitions.py is made
from - adding a new trigger (a different piece, a different rank, a
different set of choices) means adding an entry there, never touching
engine or resolver code.

`rank` may be a fixed row index, or a callable(board) -> row index for
ranks defined relative to board size (e.g. "the far edge row").
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionRule:
    piece_type: str
    color: str
    rank: object  # int, or callable(board) -> int
    choices: tuple

    def rank_for(self, board):
        return self.rank(board) if callable(self.rank) else self.rank