"""Promotion-choice menu sizing/drawing config, loaded from an external
JSON file - same load pattern as panel_config.py.

`choice_order` fixes a single left-to-right rendering order for option
icons, independent of whatever order a given pending promotion's
`choices` tuple happens to arrive in (see rules/piece_rules.py's
PromotionRule) - this keeps a piece_type's on-screen column stable
across pieces/rules, and lets a click's x-offset be inverted back to a
piece_type using this same order (see view/promotion_menu_view.py's
option_bounds and driver/game_loop.py's click routing). A rule offering
fewer choices than `choice_order` lists (e.g. a custom rule with only
("Q", "R")) still lays out correctly - only the intersection is rendered,
in `choice_order`'s sequence.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROMOTION_MENU_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "promotion_menu_config.json"


@dataclass(frozen=True)
class PromotionMenuConfig:
    icon_size_px: int
    spacing_px: int
    padding_px: int
    background_color: tuple
    border_color: tuple
    border_thickness: int
    text_color: tuple
    font_scale: float
    font_thickness: int
    choice_order: tuple


def parse_promotion_menu_config(data):
    return PromotionMenuConfig(
        icon_size_px=data["icon_size_px"],
        spacing_px=data["spacing_px"],
        padding_px=data["padding_px"],
        background_color=tuple(data["background_color"]),
        border_color=tuple(data["border_color"]),
        border_thickness=data["border_thickness"],
        text_color=tuple(data["text_color"]),
        font_scale=data["font_scale"],
        font_thickness=data["font_thickness"],
        choice_order=tuple(data["choice_order"]),
    )


def load_promotion_menu_config(path=DEFAULT_PROMOTION_MENU_CONFIG_PATH):
    with open(path, encoding="utf-8") as config_file:
        return parse_promotion_menu_config(json.load(config_file))