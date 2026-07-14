"""Consumes renderer layout data (CellView instances, ultimately derived
from a GameState snapshot) and produces an actual image: a PPM pixmap,
using only the standard library so the view layer needs no extra
dependency. Each cell is painted as a checkerboard square with a solid
colored block for its piece, if any - a minimal but genuine picture, not
a text dump.
"""

from kungfu_chess.model.piece import WHITE

LIGHT_SQUARE_COLOR = (240, 217, 181)
DARK_SQUARE_COLOR = (181, 136, 99)
WHITE_PIECE_COLOR = (255, 255, 255)
BLACK_PIECE_COLOR = (30, 30, 30)
PIECE_INSET_RATIO = 0.2


class ImageView:
    def render_ppm(self, cell_views):
        """Return the PPM (ASCII P3) bytes for the given cell layout."""
        if not cell_views:
            return b"P3\n0 0\n255\n"

        width_px = max(cell.x_px + cell.size_px for cell in cell_views)
        height_px = max(cell.y_px + cell.size_px for cell in cell_views)
        pixels = [[DARK_SQUARE_COLOR] * width_px for _ in range(height_px)]

        for cell in cell_views:
            self._paint_cell(pixels, cell)

        return self._to_ppm_bytes(pixels, width_px, height_px)

    def _paint_cell(self, pixels, cell):
        base_color = LIGHT_SQUARE_COLOR if (cell.row + cell.col) % 2 == 0 else DARK_SQUARE_COLOR
        self._fill_rect(pixels, cell.x_px, cell.y_px, cell.size_px, cell.size_px, base_color)

        if cell.piece is not None:
            piece_color = WHITE_PIECE_COLOR if cell.piece.color == WHITE else BLACK_PIECE_COLOR
            inset = int(cell.size_px * PIECE_INSET_RATIO)
            inset_size = cell.size_px - 2 * inset
            self._fill_rect(pixels, cell.x_px + inset, cell.y_px + inset, inset_size, inset_size, piece_color)

    @staticmethod
    def _fill_rect(pixels, x_px, y_px, width_px, height_px, color):
        for y in range(y_px, y_px + height_px):
            for x in range(x_px, x_px + width_px):
                pixels[y][x] = color

    @staticmethod
    def _to_ppm_bytes(pixels, width_px, height_px):
        lines = ["P3", f"{width_px} {height_px}", "255"]
        for row in pixels:
            lines.append(" ".join(f"{r} {g} {b}" for (r, g, b) in row))
        return ("\n".join(lines) + "\n").encode("ascii")