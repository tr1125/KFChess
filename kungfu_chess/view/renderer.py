"""Pure transform from a GameState snapshot into drawable layout data
(per-cell pixel rects and pieces). No image I/O, no pixel colors - that
is image_view's job. BoardRenderer only knows geometry: which cell goes
where in pixel space, at the configured cell size.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CellView:
    row: int
    col: int
    piece: object  # Piece | None
    x_px: int
    y_px: int
    size_px: int


class BoardRenderer:
    def __init__(self, cell_size_px):
        self._cell_size_px = cell_size_px

    def render(self, game_state):
        """Return a list[CellView], one per board cell, describing what
        piece occupies it (if any) and where it belongs in pixel space.
        """
        cells = []
        for row_index, row in enumerate(game_state.board_rows()):
            for col_index, piece in enumerate(row):
                cells.append(
                    CellView(
                        row=row_index,
                        col=col_index,
                        piece=piece,
                        x_px=col_index * self._cell_size_px,
                        y_px=row_index * self._cell_size_px,
                        size_px=self._cell_size_px,
                    )
                )
        return cells
