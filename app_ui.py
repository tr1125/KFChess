"""KFChess networked UI entry point (see KFChess_Server_Plan.md Stage 2) -
connects to a KFChess server over WebSockets and plays as the given color.
There is no offline/local mode: this always talks to a server, even a
`localhost` one during dev (see the plan's Sec 0).

Usage:
    python app_ui.py --color white
    python app_ui.py --color black --host localhost --port 8765

Click a piece, then click a destination to request a move (empty square
or an enemy piece). Click the same square again to jump in place. Press
'q' or Esc to quit.
"""

import argparse
import getpass
import time
from pathlib import Path

from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.config.board_config import load_board_config
from kungfu_chess.config.panel_config import load_panel_config
from kungfu_chess.config.promotion_menu_config import load_promotion_menu_config
from kungfu_chess.config.selection_config import load_selection_config
from kungfu_chess.config.sprite_state_mapping import load_sprite_state_mapping
from kungfu_chess.net.remote_engine import RemoteEngine
from kungfu_chess.net.ws_client import WsClient
from kungfu_chess.view.opencv_view import OpenCvView
from kungfu_chess.view.promotion_menu_view import PromotionMenuView
from kungfu_chess.view.renderer import BoardRenderer
from kungfu_chess.view.side_panel_view import SidePanelView
from kungfu_chess.driver.time_source import WallClock
from kungfu_chess.driver.game_loop import GameLoop, PanelSet, PromotionMenuSet

from server import config as server_config
from server import protocol

REPO_ROOT = Path(__file__).resolve().parent
ASSETS_PIECES_DIR = REPO_ROOT / "assets" / "pieces"
BOARD_IMAGE_PATH = REPO_ROOT / "assets" / "board.png"
WINDOW_NAME = "KFChess"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--color", choices=["white", "black"], required=True)
    parser.add_argument("--host", default=server_config.WS_HOST)
    parser.add_argument("--port", type=int, default=server_config.WS_PORT)
    return parser.parse_args()


def wait_for_status(engine, *msg_types, poll_interval_s=0.05):
    """Block the calling thread until one of `msg_types` has been
    recorded in engine.status - used only during the pre-game handshake,
    before the cv2 window (and GameLoop's own per-tick draining) exists.
    """
    while not any(msg_type in engine.status for msg_type in msg_types):
        engine.wait(0)
        time.sleep(poll_interval_s)


def main():
    args = parse_args()
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    ws_client = WsClient(f"ws://{args.host}:{args.port}")
    ws_client.send(protocol.MSG_LOGIN, {"username": username, "password": password})
    engine = RemoteEngine(ws_client.send, ws_client.incoming)

    wait_for_status(engine, protocol.MSG_LOGIN_OK, protocol.MSG_LOGIN_ERROR)
    if protocol.MSG_LOGIN_ERROR in engine.status:
        print(f"Login failed: {engine.status[protocol.MSG_LOGIN_ERROR]['reason']}")
        return
    player_rating = engine.status[protocol.MSG_LOGIN_OK]["rating"]
    print(f"Logged in as {username} (rating {player_rating})")

    print("Waiting for opponent...")
    wait_for_status(engine, protocol.MSG_GAME_STARTED)
    print("Game started!")

    flipped = args.color == "black"
    board_config = load_board_config()
    controller = Controller(
        engine,
        BoardMapper(board_config.cell_size_px, board_config.margin_left_px, board_config.margin_top_px),
        flipped=flipped,
    )
    view = OpenCvView(
        board_config,
        load_sprite_state_mapping(),
        assets_pieces_dir=str(ASSETS_PIECES_DIR),
        board_image_path=str(BOARD_IMAGE_PATH),
        selection_config=load_selection_config(),
        flipped=flipped,
    )
    panel_config = load_panel_config()
    own_color = "w" if args.color == "white" else "b"
    panels = PanelSet(
        left_view=SidePanelView(panel_config),
        right_view=SidePanelView(panel_config),
        left_color="w",  # arbitrary/cosmetic - see UI_PLAN.md Sec 11.3
        right_color="b",
        panel_config=panel_config,
        ratings={own_color: player_rating},  # only our own rating is known - see Stage 3
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
            flipped=flipped,
        ),
    )
    loop = GameLoop(controller, view, WallClock(), panels=panels, promotion_menu=promotion_menu)
    loop.run(WINDOW_NAME, on_click=controller.click)


if __name__ == "__main__":
    main()