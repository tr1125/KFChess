"""Score/move-list side-panel sizing and drawing config, loaded from an
external JSON file - same load pattern as board_config.py (see
UI_PLAN.md Sec 11.3). No "max visible moves" field: how many move-list
lines fit is a viewport size derived at render time from the panel's
actual rendered height and line_height_px, not a data-truncation cap -
the full move list stays reachable by scrolling (see
observers/move_log_observer.py).
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PANEL_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "panel_config.json"


@dataclass(frozen=True)
class PanelConfig:
    panel_width_px: int
    line_height_px: int
    font_scale: float
    font_thickness: int
    text_color: tuple
    background_color: tuple
    padding_px: int
    labels: dict  # color ("w"/"b") -> display label ("White"/"Black")


def parse_panel_config(data):
    return PanelConfig(
        panel_width_px=data["panel_width_px"],
        line_height_px=data["line_height_px"],
        font_scale=data["font_scale"],
        font_thickness=data["font_thickness"],
        text_color=tuple(data["text_color"]),
        background_color=tuple(data["background_color"]),
        padding_px=data["padding_px"],
        labels=dict(data["labels"]),
    )


def load_panel_config(path=DEFAULT_PANEL_CONFIG_PATH):
    with open(path, encoding="utf-8") as config_file:
        return parse_panel_config(json.load(config_file))
