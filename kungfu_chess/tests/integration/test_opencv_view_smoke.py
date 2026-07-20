"""Real-asset smoke test for opencv_view: loads the actual board.png and
real sprite files through real (headless) cv2.imread/resize calls and
asserts nothing raises and the output looks like a sane image. No window
is opened - cv2.imshow/waitKey are exercised only by the manual
scripts/render_static_board.py script, never here.
"""

from pathlib import Path

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.game_state import GameState
from kungfu_chess.config.board_config import load_board_config
from kungfu_chess.config.sprite_state_mapping import load_sprite_state_mapping
from kungfu_chess.view.opencv_view import OpenCvView

REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS_PIECES_DIR = REPO_ROOT / "assets" / "pieces"
BOARD_IMAGE_PATH = REPO_ROOT / "assets" / "board.png"


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def make_game_state(rows):
    board = board_from(rows)
    state = GameState()
    state.attach_board(board)
    return state


def test_render_frame_produces_a_sane_image_from_real_assets():
    state = make_game_state(
        [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
        ]
    )
    view = OpenCvView(
        load_board_config(),
        load_sprite_state_mapping(),
        assets_pieces_dir=str(ASSETS_PIECES_DIR),
        board_image_path=str(BOARD_IMAGE_PATH),
    )

    frame = view.render_frame(state)

    assert frame.ndim == 3
    assert frame.shape[2] == 3
    assert frame.shape[0] > 0 and frame.shape[1] > 0