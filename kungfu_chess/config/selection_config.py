"""Selected-piece square highlight color/thickness config, loaded from an
external JSON file - same load pattern as promotion_menu_config.py.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SELECTION_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "selection_config.json"


@dataclass(frozen=True)
class SelectionConfig:
    color: tuple  # BGR, matching every other *_color field in this package
    thickness: int


def parse_selection_config(data):
    return SelectionConfig(
        color=tuple(data["color"]),
        thickness=data["thickness"],
    )


def load_selection_config(path=DEFAULT_SELECTION_CONFIG_PATH):
    with open(path, encoding="utf-8") as config_file:
        return parse_selection_config(json.load(config_file))