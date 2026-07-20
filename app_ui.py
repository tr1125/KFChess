"""KFChess UI entry point - two players sharing one machine, click through
moves/jumps on a real window, driven by a real wall-clock game loop
(see UI_PLAN.md Sec 10 item 5). Replaces the old scripts/interactive_board.py
prototype, whose clock was tied to cv2.waitKey's own fixed-tick timing.

Usage:
    python app_ui.py

Click a piece, then click a destination to request a move (empty square
or an enemy piece). Click the same square again to jump in place. Press
'q' or Esc to quit.
"""

from pathlib import Path

from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.config.board_config import load_board_config
from kungfu_chess.config.panel_config import load_panel_config
from kungfu_chess.config.promotion_menu_config import load_promotion_menu_config
from kungfu_chess.config.sprite_state_mapping import load_sprite_state_mapping
from kungfu_chess.view.opencv_view import OpenCvView
from kungfu_chess.view.promotion_menu_view import PromotionMenuView
from kungfu_chess.view.renderer import BoardRenderer
from kungfu_chess.view.side_panel_view import SidePanelView
from kungfu_chess.driver.time_source import WallClock
from kungfu_chess.driver.game_loop import GameLoop, PanelSet, PromotionMenuSet

REPO_ROOT = Path(__file__).resolve().parent
ASSETS_PIECES_DIR = REPO_ROOT / "assets" / "pieces"
BOARD_IMAGE_PATH = REPO_ROOT / "assets" / "board.png"
WINDOW_NAME = "KFChess"

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
    panel_config = load_panel_config()
    panels = PanelSet(
        left_view=SidePanelView(panel_config),
        right_view=SidePanelView(panel_config),
        left_color="w",  # arbitrary/cosmetic - see UI_PLAN.md Sec 11.3
        right_color="b",
        panel_config=panel_config,
    )
    promotion_menu_config = load_promotion_menu_config()
    promotion_menu = PromotionMenuSet(
        view=PromotionMenuView(promotion_menu_config),
        config=promotion_menu_config,
        # A second BoardRenderer instance, independent of the one OpenCvView
        # owns internally - stateless/pure, so instantiating it twice from
        # the same board_config is harmless (see driver/game_loop.py).
        board_renderer=BoardRenderer(
            cell_size_px=board_config.cell_size_px,
            margin_left_px=board_config.margin_left_px,
            margin_top_px=board_config.margin_top_px,
        ),
    )
    loop = GameLoop(controller, view, WallClock(), panels=panels, promotion_menu=promotion_menu)
    loop.run(WINDOW_NAME, on_click=controller.click)


if __name__ == "__main__":
    main()