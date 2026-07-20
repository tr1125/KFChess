"""Resolves, for a given piece color/kind/state, the ordered sprite frame
paths plus that state's animation timing (frames_per_sec, is_loop) - see
UI_PLAN.md Sec 5. Owns the folder-name<->PieceState mapping (via
config/sprite_state_mapping.py) so OpenCvView never has to resolve it
inline.

Pure metadata resolution only - loading actual pixel data stays
OpenCvView's SpriteCache's job, unchanged since Step 3; this module only
resolves paths, frame counts, and each state's config.json graphics
settings. next_state_when_finished (also present in each state's
config.json) is deliberately never read here - see UI_PLAN.md Sec 5:
state transitions are owned exclusively by the engine, this module only
reads graphics.* fields.

Memoized by (color, kind, state_name), so a state's config.json is
parsed and its sprites directory listed at most once per distinct
piece/state combination actually rendered, not once per frame.
"""

import json
import os
from dataclasses import dataclass

from kungfu_chess.config.sprite_state_mapping import folder_for_state_name
from kungfu_chess.view.sprite_paths import sprite_path


def _read_config_json(path):
    with open(path, encoding="utf-8") as config_file:
        return json.load(config_file)


@dataclass(frozen=True)
class SpriteSet:
    frame_paths: tuple  # str, ... - ordered, index 0 == "1.png"
    frames_per_sec: float
    is_loop: bool

    @property
    def num_frames(self):
        return len(self.frame_paths)


class SpriteRegistry:
    def __init__(self, sprite_state_mapping, assets_pieces_dir, listdir=os.listdir, read_config=_read_config_json):
        self._sprite_state_mapping = sprite_state_mapping
        self._assets_pieces_dir = assets_pieces_dir
        self._listdir = listdir
        self._read_config = read_config
        self._cache = {}

    def get(self, piece_color, piece_kind, state_name):
        """SpriteSet for this color/kind/state, or None if state_name has
        no mapped sprite folder (e.g. CAPTURED - see
        sprite_state_mapping.json).
        """
        key = (piece_color, piece_kind, state_name)
        if key not in self._cache:
            self._cache[key] = self._load(piece_color, piece_kind, state_name)
        return self._cache[key]

    def _load(self, piece_color, piece_kind, state_name):
        folder_name = folder_for_state_name(self._sprite_state_mapping, state_name)
        if folder_name is None:
            return None

        state_dir = os.path.join(self._assets_pieces_dir, f"{piece_color}{piece_kind}", "states", folder_name)
        config = self._read_config(os.path.join(state_dir, "config.json"))
        num_frames = len(self._listdir(os.path.join(state_dir, "sprites")))

        frame_paths = tuple(
            sprite_path(self._assets_pieces_dir, piece_color, piece_kind, folder_name, frame_filename=f"{i}.png")
            for i in range(1, num_frames + 1)
        )
        return SpriteSet(
            frame_paths=frame_paths,
            frames_per_sec=config["graphics"]["frames_per_sec"],
            is_loop=config["graphics"]["is_loop"],
        )