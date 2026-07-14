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
