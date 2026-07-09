"""Tracks each color's cumulative score from captured pieces, using the
standard chess piece values from config/piece_definitions.py. A capture
credits its value to whichever color did the capturing - the mover's
color for a normal capture, the airborne defender's color for a mid-air
capture (see MoveResolver, the only caller of record_capture).
"""

from config.piece_definitions import PIECE_VALUES
from domain.piece_token import type_of


class ScoreTracker:
    def __init__(self):
        self._scores = {"w": 0, "b": 0}

    def record_capture(self, capturing_color, captured_token):
        self._scores[capturing_color] += PIECE_VALUES[type_of(captured_token)]

    def scores(self):
        return dict(self._scores)