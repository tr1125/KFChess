"""Manual, one-shot visual check: renders one static frame of a standard
starting position and pops a real window so a human can eyeball pixel
alignment before animation (Step 6) is added. Not part of the automated
test suite - see UI_PLAN.md Sec 10 item 3.

Usage:
    python scripts/render_static_board.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # the repo has no pyproject.toml/setup.py - not pip-installed

import cv2

from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.config.board_config import load_board_config
from kungfu_chess.config.sprite_state_mapping import load_sprite_state_mapping
from kungfu_chess.view.opencv_view import OpenCvView

ASSETS_PIECES_DIR = REPO_ROOT / "assets" / "pieces"
BOARD_IMAGE_PATH = REPO_ROOT / "assets" / "board.png"

STANDARD_START = [
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
]


def main():
    board = parse_board(STANDARD_START)
    engine = GameEngine(board, RuleEngine(default_piece_rules()))
    board_config = load_board_config()
    controller = Controller(
        engine,
        BoardMapper(board_config.cell_size_px, board_config.margin_left_px, board_config.margin_top_px),
    )
    view = OpenCvView(
        board_config,
        load_sprite_state_mapping(),
        assets_pieces_dir=str(ASSETS_PIECES_DIR),
        board_image_path=str(BOARD_IMAGE_PATH),
    )

    frame = view.render_frame(controller.game_state())

    cv2.imshow("KFChess - static rendering check", frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()