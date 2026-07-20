"""Maps raw pixel coordinates to board cell positions. The one place that
knows about cell size in pixels.
"""

from kungfu_chess.model.position import Position


class BoardMapper:
    def __init__(self, cell_size_px, margin_left_px=0, margin_top_px=0):
        self._cell_size_px = cell_size_px
        self._margin_left_px = margin_left_px
        self._margin_top_px = margin_top_px

    def cell_at(self, x_px, y_px):
        row = (y_px - self._margin_top_px) // self._cell_size_px
        col = (x_px - self._margin_left_px) // self._cell_size_px
        return Position(row, col)