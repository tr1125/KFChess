from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.game_state import GameState
from kungfu_chess.view.renderer import BoardRenderer, CellView


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def make_game_state(rows):
    board = board_from(rows)
    state = GameState()
    state.attach_board(board)
    return state, board


def test_render_yields_one_cell_view_per_board_cell():
    state, _ = make_game_state([["wK", "."], [".", "bK"]])
    cells = BoardRenderer(cell_size_px=100).render(state)
    assert len(cells) == 4


def test_render_preserves_row_col_and_piece():
    state, board = make_game_state([["wK", "."], [".", "bK"]])
    cells = BoardRenderer(cell_size_px=100).render(state)
    assert CellView(row=0, col=0, piece=board.get(0, 0), x_px=0, y_px=0, size_px=100) in cells
    assert CellView(row=1, col=1, piece=board.get(1, 1), x_px=100, y_px=100, size_px=100) in cells


def test_render_computes_pixel_rect_from_cell_size():
    state, _ = make_game_state([[".", ".", "."]])
    cells = BoardRenderer(cell_size_px=50).render(state)
    assert cells[2].x_px == 100
    assert cells[2].y_px == 0
    assert cells[2].size_px == 50


def test_render_reflects_current_board_state_not_a_stale_snapshot():
    board = board_from([["wR", "."]])
    state = GameState()
    state.attach_board(board)
    board.apply_move(0, 0, 0, 1)
    cells = BoardRenderer(cell_size_px=100).render(state)
    pieces = {(cell.row, cell.col): cell.piece for cell in cells}
    assert pieces[(0, 0)] is None
    assert pieces[(0, 1)] is board.get(0, 1)


def test_render_empty_board_yields_no_cells():
    state, _ = make_game_state([])
    assert BoardRenderer(cell_size_px=100).render(state) == []


def test_render_offsets_pixel_rects_by_configured_margin():
    state, _ = make_game_state([["wK", "."], [".", "bK"]])
    cells = BoardRenderer(cell_size_px=100, margin_left_px=20, margin_top_px=10).render(state)
    pixels = {(cell.row, cell.col): (cell.x_px, cell.y_px) for cell in cells}
    assert pixels[(0, 0)] == (20, 10)
    assert pixels[(0, 1)] == (120, 10)
    assert pixels[(1, 0)] == (20, 110)


# --- pixel_position ---


def test_pixel_position_matches_render_for_an_occupied_cell():
    state, _ = make_game_state([["wK", "."], [".", "bK"]])
    renderer = BoardRenderer(cell_size_px=100, margin_left_px=20, margin_top_px=10)
    cells = renderer.render(state)
    target = next(cell for cell in cells if (cell.row, cell.col) == (1, 1))

    assert renderer.pixel_position(1, 1) == (target.x_px, target.y_px)


def test_pixel_position_works_for_a_cell_with_no_piece_and_off_the_current_board():
    renderer = BoardRenderer(cell_size_px=50, margin_left_px=5, margin_top_px=0)
    assert renderer.pixel_position(0, 3) == (155, 0)


def test_cell_size_px_exposes_the_configured_cell_size():
    renderer = BoardRenderer(cell_size_px=77, margin_left_px=5, margin_top_px=0)
    assert renderer.cell_size_px == 77


# --- flipped orientation (networked Black client) ---

def test_pixel_position_mirrors_row_and_col_when_flipped():
    renderer = BoardRenderer(cell_size_px=100, flipped=True)
    # Logical (0, 0) on a 2x2 board is the bottom-right in display space.
    assert renderer.pixel_position(0, 0, board_height=2, board_width=2) == (100, 100)
    assert renderer.pixel_position(1, 1, board_height=2, board_width=2) == (0, 0)


def test_render_places_logical_row_0_at_the_bottom_when_flipped():
    state, board = make_game_state([["wK", "."], [".", "bK"]])
    cells = BoardRenderer(cell_size_px=100, flipped=True).render(state)
    pixels = {(cell.row, cell.col): (cell.x_px, cell.y_px) for cell in cells}
    assert pixels[(0, 0)] == (100, 100)  # logical top-left drawn bottom-right
    assert pixels[(1, 1)] == (0, 0)  # logical bottom-right drawn top-left


def test_render_keeps_cellview_row_col_logical_even_when_flipped():
    state, board = make_game_state([["wK", "."], [".", "bK"]])
    cells = BoardRenderer(cell_size_px=100, flipped=True).render(state)
    pieces = {(cell.row, cell.col): cell.piece for cell in cells}
    assert pieces[(0, 0)] is board.get(0, 0)
    assert pieces[(1, 1)] is board.get(1, 1)


def test_pixel_position_unflipped_ignores_board_dimensions():
    renderer = BoardRenderer(cell_size_px=100)
    assert renderer.pixel_position(1, 1) == (100, 100)
