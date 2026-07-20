"""Board image sizing/margin config, loaded from an external JSON file
rather than measured from the image at runtime (see UI_PLAN.md Sec 6).
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BOARD_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "board_config.json"


@dataclass(frozen=True)
class BoardConfig:
    image_width_px: int
    image_height_px: int
    margin_left_px: int
    margin_top_px: int
    cell_size_px: int
    cell_size_meters: float


def parse_board_config(data):
    return BoardConfig(
        image_width_px=data["image_width_px"],
        image_height_px=data["image_height_px"],
        margin_left_px=data["margin_left_px"],
        margin_top_px=data["margin_top_px"],
        cell_size_px=data["cell_size_px"],
        cell_size_meters=data["cell_size_meters"],
    )


def load_board_config(path=DEFAULT_BOARD_CONFIG_PATH):
    with open(path, encoding="utf-8") as config_file:
        return parse_board_config(json.load(config_file))


def px_per_meter(board_config):
    return board_config.cell_size_px / board_config.cell_size_meters
