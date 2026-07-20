"""Aspect-ratio locking for the resizable window (see UI_PLAN.md Sec 10
item 5 / driver's ownership of resize handling): the board's own native
width:height ratio (from board_config, via the rendered frame's own
shape - currently ~822:828) must never distort, regardless of what size
the user drags the window to.

fit_size/centering_offset/canvas_to_native are pure geometry, easily
unit-tested without a window. compose_letterboxed does the actual image
work (cv2.resize + numpy canvas) - it needs cv2/numpy but not a live
window, so it's still safely unit-testable with a synthetic frame.

board_mapper.py, renderer.py and opencv_view.py are untouched by this:
they keep rendering in native board pixel space exactly as before. This
module takes the already-rendered native frame and letterboxes it as a
pure post-processing step, translating clicks on the letterboxed canvas
back into that same native space before they ever reach Controller.
"""

import cv2
import numpy as np

LETTERBOX_COLOR = (0, 0, 0)


def fit_size(native_size, available_size):
    """Largest (w, h) that preserves native_size's aspect ratio and fits
    within available_size. Falls back to native_size unchanged if
    available_size is degenerate (e.g. queried before a window has ever
    been painted)."""
    native_w, native_h = native_size
    available_w, available_h = available_size
    if available_w <= 0 or available_h <= 0:
        return native_w, native_h

    scale = min(available_w / native_w, available_h / native_h)
    fit_w = max(1, min(available_w, round(native_w * scale)))
    fit_h = max(1, min(available_h, round(native_h * scale)))
    return fit_w, fit_h


def centering_offset(available_size, content_size):
    available_w, available_h = available_size
    content_w, content_h = content_size
    return (available_w - content_w) // 2, (available_h - content_h) // 2


def canvas_to_native(canvas_x, canvas_y, native_size, content_size, offset):
    """Translates a click on the letterboxed canvas back into native
    board pixel space. Returns None if the click landed in a letterbox
    bar (not on the board at all)."""
    offset_x, offset_y = offset
    content_w, content_h = content_size
    native_w, native_h = native_size

    local_x = canvas_x - offset_x
    local_y = canvas_y - offset_y
    if content_w <= 0 or content_h <= 0:
        return None
    if not (0 <= local_x < content_w and 0 <= local_y < content_h):
        return None

    native_x = round(local_x * native_w / content_w)
    native_y = round(local_y * native_h / content_h)
    return native_x, native_y


def compose_letterboxed(frame, available_size):
    """Resizes frame to the largest ratio-preserving size that fits
    available_size, and pastes it centered onto a LETTERBOX_COLOR canvas
    of exactly available_size. Returns (canvas, content_size, offset) -
    the latter two are what canvas_to_native needs for click translation.
    """
    native_h, native_w = frame.shape[0], frame.shape[1]
    content_w, content_h = fit_size((native_w, native_h), available_size)
    offset = centering_offset(available_size, (content_w, content_h))

    interpolation = cv2.INTER_AREA if content_w < native_w else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (content_w, content_h), interpolation=interpolation)

    available_w, available_h = available_size
    canvas = np.full((available_h, available_w, 3), LETTERBOX_COLOR, dtype=frame.dtype)
    offset_x, offset_y = offset
    canvas[offset_y:offset_y + content_h, offset_x:offset_x + content_w] = resized

    return canvas, (content_w, content_h), offset