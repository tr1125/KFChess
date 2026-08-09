"""Turns a PanelData snapshot (see observers/move_log_observer.py) into
an actual OpenCV image: player label, score, and a scrollable window of
that player's move list. Pure pixel-drawing, no scroll *state* and no
mouse handling of its own - `scroll_offset` is just an input, like
`panel_data` is (see UI_PLAN.md Sec 11.3; scroll state itself lives on
GameLoop, see driver/game_loop.py).

Never imports engine/model/rules - only reads `.color`, `.score`,
`.moves` off the PanelData it's handed, matching the same boundary
discipline opencv_view.py already follows for CellView/Piece.
"""

import cv2
import numpy as np

from kungfu_chess.observers.move_log_observer import clamp_scroll_offset, visible_slice


class SidePanelView:
    def __init__(self, panel_config):
        self._config = panel_config

    def render_frame(self, panel_data, height_px, scroll_offset=0, width_px=None):
        """Return a numpy BGR array of exactly (height_px, width_px, 3):
        the panel background, the player's label + score, and as many
        move-list lines as fit in the remaining height, windowed by
        scroll_offset. Never opens a window - the caller composes this
        alongside the board frame.

        width_px defaults to panel_config.panel_width_px but can be
        overridden - driver/panel_layout.py shrinks panel width below
        the configured target when the window becomes too narrow to fit
        both panels plus a usable board (see panel_regions), and needs
        the actual rendered panel frame to match that shrunk width
        exactly so it concatenates cleanly with the board frame.
        """
        config = self._config
        width_px = config.panel_width_px if width_px is None else width_px
        canvas = np.full((height_px, width_px, 3), config.background_color, dtype=np.uint8)

        label = config.labels.get(panel_data.color, panel_data.color)
        header_text = f"{label}: {panel_data.score}"
        if panel_data.rating is not None:
            header_text += f"  (rating {panel_data.rating})"
        header_y = config.padding_px + config.line_height_px
        self._draw_line(canvas, header_text, header_y)

        list_top_y = header_y + config.line_height_px
        available_height = max(0, height_px - list_top_y)
        viewport_lines = available_height // config.line_height_px
        offset = clamp_scroll_offset(scroll_offset, len(panel_data.moves), viewport_lines)
        moves = visible_slice(panel_data.moves, offset, viewport_lines)

        for index, move_text in enumerate(moves):
            line_y = list_top_y + (index + 1) * config.line_height_px
            if line_y > height_px:
                break
            self._draw_line(canvas, move_text, line_y)

        return canvas

    def _draw_line(self, canvas, text, baseline_y):
        config = self._config
        cv2.putText(
            canvas,
            text,
            (config.padding_px, baseline_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            config.font_scale,
            config.text_color,
            config.font_thickness,
            cv2.LINE_AA,
        )