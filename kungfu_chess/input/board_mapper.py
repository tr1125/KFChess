"""Maps raw pixel coordinates to board cell positions. The one place that
knows about cell size in pixels.
"""

from kungfu_chess.model.position import Position


class BoardMapper:
    def __init__(self, cell_size_px):
        self._cell_size_px = cell_size_px

    def cell_at(self, x_px, y_px):
        return Position(y_px // self._cell_size_px, x_px // self._cell_size_px)