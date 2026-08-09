"""Consumes renderer layout data (CellView instances, ultimately derived
from a GameState snapshot) and produces an actual OpenCV image: the board
background composited with one sprite per occupied cell.

render_frame's now_ms/in_flight_leg params are optional (default None) and
gate animation as a single unit (UI_PLAN.md Sec 5/Sec 10 item 6): when
now_ms is None, rendering is exactly the Step 3 static behavior - always
the piece's current-state folder's frame "1", at its current board cell -
via _static_sprite_path, which never touches SpriteRegistry (see its own
docstring for why that separation matters). When now_ms is given,
_animated_sprite_path picks a time-based frame via animation_clock, and
_piece_position_px additionally glides a MOVING piece between its
in-flight leg's two cells if in_flight_leg is also given.

Never imports engine/model/rules/realtime - only reads `.color`, `.kind`,
`.state.name`, `.state_entered_at` off whatever object CellView.piece
carries, matching renderer.py's own untyped `piece: object` field (see
UI_PLAN.md Sec 9 boundary discipline). in_flight_leg is accepted as a
plain callable (piece -> 4-tuple | None), not a Controller/GameEngine
type, for the same reason - see driver/game_loop.py, the only place that
actually supplies it.
"""

import os

import cv2
import numpy as np

from kungfu_chess.config.selection_config import load_selection_config
from kungfu_chess.config.sprite_state_mapping import folder_for_state_name
from kungfu_chess.view.animation_clock import frame_index
from kungfu_chess.view.renderer import BoardRenderer
from kungfu_chess.view.sprite_paths import sprite_path
from kungfu_chess.view.sprite_registry import SpriteRegistry


def _imread_unicode_safe(path, flags):
    """cv2.imread opens files via a plain C fopen() call, which mangles
    non-ASCII paths on Windows - a real problem here since the repo
    itself lives under a Unicode directory name. Reading the bytes
    through Python's own (Unicode-safe) file API and decoding them with
    cv2.imdecode sidesteps that entirely. Returns None on any failure
    (missing file or undecodable data), matching cv2.imread's contract.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def alpha_composite(background_bgr, sprite_bgra, x_px, y_px):
    """Alpha-blend sprite_bgra (H, W, 4 uint8) onto background_bgr (H, W, 3
    uint8) in place, anchored top-left at (x_px, y_px). Clips the sprite to
    whatever of it actually falls within the background's bounds.
    """
    sprite_height, sprite_width = sprite_bgra.shape[:2]
    bg_height, bg_width = background_bgr.shape[:2]

    dest_x0, dest_y0 = max(x_px, 0), max(y_px, 0)
    dest_x1, dest_y1 = min(x_px + sprite_width, bg_width), min(y_px + sprite_height, bg_height)
    if dest_x0 >= dest_x1 or dest_y0 >= dest_y1:
        return background_bgr

    src_x0, src_y0 = dest_x0 - x_px, dest_y0 - y_px
    src_x1, src_y1 = src_x0 + (dest_x1 - dest_x0), src_y0 + (dest_y1 - dest_y0)

    sprite_region = sprite_bgra[src_y0:src_y1, src_x0:src_x1]
    alpha = sprite_region[:, :, 3:4].astype(float) / 255.0
    background_region = background_bgr[dest_y0:dest_y1, dest_x0:dest_x1]
    background_region[:] = (
        sprite_region[:, :, :3].astype(float) * alpha + background_region.astype(float) * (1.0 - alpha)
    ).astype(background_bgr.dtype)

    return background_bgr


class SpriteCache:
    """Minimal private loader+memoizer: imread + cache by resolved path.
    Not the Step 6 sprite_registry - no fps/frame-index/loop parsing.
    """

    def __init__(self, imread=_imread_unicode_safe):
        self._imread = imread
        self._cache = {}

    def get(self, path):
        if path not in self._cache:
            image = self._imread(path, cv2.IMREAD_UNCHANGED)
            if image is None:
                raise FileNotFoundError(f"Could not load sprite image: {path}")
            self._cache[path] = image
        return self._cache[path]


class OpenCvView:
    def __init__(
        self,
        board_config,
        sprite_state_mapping,
        assets_pieces_dir,
        board_image_path,
        sprite_cache=None,
        sprite_registry=None,
        board_image=None,
        static_frame_filename="1.png",
        selection_config=None,
        flipped=False,
    ):
        self._sprite_state_mapping = sprite_state_mapping
        self._assets_pieces_dir = assets_pieces_dir
        self._board_image_path = board_image_path
        self._sprite_cache = sprite_cache if sprite_cache is not None else SpriteCache()
        self._sprite_registry = (
            sprite_registry if sprite_registry is not None else SpriteRegistry(sprite_state_mapping, assets_pieces_dir)
        )
        self._board_image = board_image
        self._static_frame_filename = static_frame_filename
        self._selection_config = selection_config if selection_config is not None else load_selection_config()
        self._renderer = BoardRenderer(
            cell_size_px=board_config.cell_size_px,
            margin_left_px=board_config.margin_left_px,
            margin_top_px=board_config.margin_top_px,
            flipped=flipped,
        )

    def render_frame(self, game_state, now_ms=None, in_flight_leg=None, selected=None):
        """Return a numpy BGR array: the board background composited with
        one sprite per occupied cell. Never opens a window - that is the
        caller's job (see scripts/render_static_board.py).

        now_ms/in_flight_leg default to None, which reproduces exactly
        the Step 3 static-only behavior (see module docstring) - the
        caller (driver/game_loop.py) is the only place that supplies
        them for a live, animated game.

        selected is an optional Position (row/col) of the currently
        selected piece's square - when given, its cell is outlined so the
        player can see what they've picked.
        """
        board_height, board_width = game_state.board_height(), game_state.board_width()
        canvas = self._load_board_image().copy()
        for cell in self._renderer.render(game_state):
            if cell.piece is None:
                continue
            self._draw_piece(canvas, cell, now_ms, in_flight_leg, board_height, board_width)
        if selected is not None:
            self._draw_selection(canvas, selected, board_height, board_width)
        return canvas

    def _draw_selection(self, canvas, selected, board_height, board_width):
        x_px, y_px = self._renderer.pixel_position(selected.row, selected.col, board_height, board_width)
        size_px = self._renderer.cell_size_px
        config = self._selection_config
        cv2.rectangle(canvas, (x_px, y_px), (x_px + size_px - 1, y_px + size_px - 1), config.color, config.thickness)

    def _load_board_image(self):
        if self._board_image is None:
            self._board_image = self._sprite_cache.get(self._board_image_path)[:, :, :3]
        return self._board_image

    def _draw_piece(self, canvas, cell, now_ms, in_flight_leg, board_height, board_width):
        piece = cell.piece
        path = self._static_sprite_path(piece) if now_ms is None else self._animated_sprite_path(piece, now_ms)
        if path is None:
            return

        sprite = self._sprite_cache.get(path)
        resized = cv2.resize(sprite, (cell.size_px, cell.size_px), interpolation=cv2.INTER_AREA)
        x_px, y_px = self._piece_position_px(cell, now_ms, in_flight_leg, board_height, board_width)
        alpha_composite(canvas, resized, x_px, y_px)

    def _static_sprite_path(self, piece):
        """Unchanged since Step 3 - deliberately never touches
        SpriteRegistry (see module docstring: this keeps every existing
        static-rendering test free of any real-filesystem dependency).
        """
        folder_name = folder_for_state_name(self._sprite_state_mapping, piece.state.name)
        if folder_name is None:
            return None
        return sprite_path(
            self._assets_pieces_dir, piece.color, piece.kind, folder_name, self._static_frame_filename
        )

    def _animated_sprite_path(self, piece, now_ms):
        sprite_set = self._sprite_registry.get(piece.color, piece.kind, piece.state.name)
        if sprite_set is None:
            return None
        elapsed_ms = now_ms - piece.state_entered_at
        index = frame_index(elapsed_ms, sprite_set.frames_per_sec, sprite_set.num_frames, sprite_set.is_loop)
        return sprite_set.frame_paths[index]

    def _piece_position_px(self, cell, now_ms, in_flight_leg, board_height, board_width):
        """A piece's pixel position is normally just its current board
        cell. It only glides between two cells while MOVING with an
        active in-flight leg - every other state (IDLE, LONG_REST,
        SHORT_REST, AIRBORNE, CAPTURED) falls through to the static cell
        position, because in_flight_leg(piece) is None for all of them
        by construction (MotionTracker.in_flight_leg only ever tracks
        pending moves - see realtime/motion.py) - no state-name check
        needed here.
        """
        if now_ms is None or in_flight_leg is None:
            return cell.x_px, cell.y_px

        leg = in_flight_leg(cell.piece)
        if leg is None:
            return cell.x_px, cell.y_px

        current_position, leg_target, leg_started_at_ms, complete_at_ms = leg
        progress = (now_ms - leg_started_at_ms) / (complete_at_ms - leg_started_at_ms)
        start_x, start_y = self._renderer.pixel_position(current_position.row, current_position.col, board_height, board_width)
        end_x, end_y = self._renderer.pixel_position(leg_target.row, leg_target.col, board_height, board_width)
        return (
            round(start_x + (end_x - start_x) * progress),
            round(start_y + (end_y - start_y) * progress),
        )