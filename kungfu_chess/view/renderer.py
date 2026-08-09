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
    def __init__(self, cell_size_px, margin_left_px=0, margin_top_px=0, flipped=False):
        self._cell_size_px = cell_size_px
        self._margin_left_px = margin_left_px
        self._margin_top_px = margin_top_px
        self._flipped = flipped

    @property
    def cell_size_px(self):
        return self._cell_size_px

    def pixel_position(self, row, col, board_height=None, board_width=None):
        """(x_px, y_px) for the top-left corner of an arbitrary board
        cell - not necessarily one currently occupied. Exposed so the
        animation layer (UI_PLAN.md Sec 5) can compute glide endpoints
        for a piece's in-flight leg using exactly the same geometry as
        render() itself, rather than re-deriving it.

        `board_height`/`board_width` are only consulted when this
        renderer was constructed with flipped=True (the networked Black
        client's per-color orientation - KFChess_Server_Plan.md Sec 0/
        Stage 2): `row`/`col` are given in logical (unflipped) board
        space and are mirrored to display space here before the usual
        margin/cell-size math, so callers never need to flip coordinates
        themselves. Unused (and safely omittable) when flipped=False.
        """
        if self._flipped:
            row = board_height - 1 - row
            col = board_width - 1 - col
        return self._margin_left_px + col * self._cell_size_px, self._margin_top_px + row * self._cell_size_px

    def render(self, game_state):
        """Return a list[CellView], one per board cell, describing what
        piece occupies it (if any) and where it belongs in pixel space.
        `CellView.row`/`.col` stay logical (unflipped) - only the pixel
        placement changes when this renderer is flipped - so click
        mapping and piece identity are unaffected by orientation.
        """
        board_height = game_state.board_height()
        board_width = game_state.board_width()
        cells = []
        for row_index, row in enumerate(game_state.board_rows()):
            for col_index, piece in enumerate(row):
                x_px, y_px = self.pixel_position(row_index, col_index, board_height, board_width)
                cells.append(
                    CellView(
                        row=row_index,
                        col=col_index,
                        piece=piece,
                        x_px=x_px,
                        y_px=y_px,
                        size_px=self._cell_size_px,
                    )
                )
        return cells
