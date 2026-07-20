"""Explicit, data-driven mapping between sprite-asset folder names (on
disk under assets/pieces/<colorkind>/states/) and engine PieceState
names. Folder names are not 1:1 with state names (MOVE vs MOVING, JUMP
vs AIRBORNE), so this must not be a string-equality assumption (see
UI_PLAN.md Sec 5).

Keyed by the plain state *name string* (e.g. "MOVING"), not by the
PieceState enum itself, so this module never imports
kungfu_chess.model.piece - keeping it free of any engine/model
dependency (see UI_PLAN.md Sec 9 boundary discipline).
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPRITE_STATE_MAPPING_PATH = (
    Path(__file__).resolve().parent / "data" / "sprite_state_mapping.json"
)


@dataclass(frozen=True)
class SpriteStateEntry:
    state_name: str
    folder_name: object  # str | None


@dataclass(frozen=True)
class SpriteStateMapping:
    entries: tuple


def parse_sprite_state_mapping(data):
    entries = tuple(
        SpriteStateEntry(state_name=entry["state"], folder_name=entry["folder"])
        for entry in data["mapping"]
    )
    return SpriteStateMapping(entries=entries)


def load_sprite_state_mapping(path=DEFAULT_SPRITE_STATE_MAPPING_PATH):
    with open(path, encoding="utf-8") as mapping_file:
        return parse_sprite_state_mapping(json.load(mapping_file))


def folder_for_state_name(mapping, state_name):
    for entry in mapping.entries:
        if entry.state_name == state_name:
            return entry.folder_name
    return None
