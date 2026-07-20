"""Turns a PromotionMenuData snapshot into an actual OpenCV image: a
small left-to-right strip of Q/R/B/N option boxes. Pure pixel-drawing,
no interaction state of its own - which piece's menu is open, and
whether it should still be showing at all, lives on GameLoop (see
driver/game_loop.py), the same split side_panel_view.py already has
from its scroll_offset.

option_bounds/menu_size_px are exposed as plain module-level functions
(not private to the class) because driver/game_loop.py's click routing
needs the exact same per-icon geometry to invert a click's x-offset back
into a piece_type - re-deriving it separately there would risk the two
falling out of sync. This mirrors how observers/move_log_observer.py's
clamp_scroll_offset/visible_slice are shared, pure functions consumed by
both a view (side_panel_view.py) and the driver (game_loop.py).

Never imports engine/model/rules - only reads `.color`/`.choices` off
whatever PromotionMenuData it's handed, matching the same boundary
discipline side_panel_view.py follows for PanelData.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class PromotionMenuData:
    color: str
    choices: tuple  # whatever subset of choice_order this piece's rule allows


def ordered_choices(choices, config):
    """`choices` filtered down to config.choice_order's subset that's
    actually offered, in that fixed left-to-right order - so layout
    position is deterministic regardless of the order `choices` itself
    arrives in (see rules/piece_rules.py's PromotionRule.choices)."""
    return [piece_type for piece_type in config.choice_order if piece_type in choices]


def option_bounds(num_choices, config):
    """List of (x0_px, x1_px), one per option slot in left-to-right
    order, local to the menu's own canvas - each icon_size_px wide,
    separated by spacing_px, with padding_px framing the first/last."""
    bounds = []
    x = config.padding_px
    for _ in range(num_choices):
        bounds.append((x, x + config.icon_size_px))
        x += config.icon_size_px + config.spacing_px
    return bounds


def menu_size_px(num_choices, config):
    """(width_px, height_px) of the canvas render_frame will return for
    `num_choices` options - 0 choices still yields a valid (empty-strip)
    size rather than a degenerate one, so callers never need to special-case
    it."""
    height_px = config.icon_size_px + 2 * config.padding_px
    if num_choices == 0:
        return 2 * config.padding_px, height_px
    last_x0, last_x1 = option_bounds(num_choices, config)[-1]
    return last_x1 + config.padding_px, height_px


class PromotionMenuView:
    def __init__(self, config):
        self._config = config

    def render_frame(self, menu_data):
        """Return a numpy BGR array sized exactly menu_size_px(...) for
        this menu_data's choice count: background, an outer border, and
        one bordered box per option with its piece-type letter drawn
        inside. Never opens a window - the caller composites this onto
        the board frame (see driver/promotion_menu_layout.py)."""
        config = self._config
        choices = ordered_choices(menu_data.choices, config)
        width_px, height_px = menu_size_px(len(choices), config)
        canvas = np.full((height_px, width_px, 3), config.background_color, dtype=np.uint8)
        cv2.rectangle(canvas, (0, 0), (width_px - 1, height_px - 1), config.border_color, config.border_thickness)

        for piece_type, (x0, x1) in zip(choices, option_bounds(len(choices), config)):
            self._draw_option(canvas, piece_type, x0, x1)

        return canvas

    def _draw_option(self, canvas, piece_type, x0, x1):
        config = self._config
        y0 = config.padding_px
        y1 = y0 + config.icon_size_px
        cv2.rectangle(canvas, (x0, y0), (x1, y1), config.border_color, config.border_thickness)

        text_size, _baseline = cv2.getTextSize(
            piece_type, cv2.FONT_HERSHEY_SIMPLEX, config.font_scale, config.font_thickness
        )
        text_w, text_h = text_size
        text_origin = (x0 + (config.icon_size_px - text_w) // 2, y0 + (config.icon_size_px + text_h) // 2)
        cv2.putText(
            canvas,
            piece_type,
            text_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            config.font_scale,
            config.text_color,
            config.font_thickness,
            cv2.LINE_AA,
        )