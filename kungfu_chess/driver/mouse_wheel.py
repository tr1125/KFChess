"""Decodes cv2's mouse-wheel callback `flags` into a single-line scroll
step for the panel move-list (see UI_PLAN.md Sec 11.3, driver/game_loop.py).

Pure integer math, no cv2 calls - cv2.EVENT_MOUSEWHEEL exists on this
repo's installed OpenCV build (5.0.0, confirmed via
`hasattr(cv2, "EVENT_MOUSEWHEEL")`) but that build has no
cv2.getMouseWheelDelta() helper, so the delta has to be decoded by hand:
per documented Win32 behavior, WM_MOUSEWHEEL's delta lives in the signed
high 16 bits of the event parameter cv2 passes through as `flags`.

IMPORTANT: the *sign* of the result below is asserted from that
documented Win32 encoding, not empirically confirmed by physically
turning a mouse wheel over a live window (not possible in the
environment this was written in) - see UI_PLAN.md Sec 11.3 / the
plan's Context section for the same discipline §11.1's click-scaling
bug was held to. Verify with a live window (temporarily print
wheel_delta_from_flags(flags) while scrolling, confirm scroll-up reveals
older moves as intended) before trusting this in production; if it's
backwards, flip the single comparison below - nothing else in the
panel/scroll pipeline needs to change.
"""


def wheel_delta_from_flags(flags):
    """Returns +1 (scroll up / away from the user), -1 (scroll down /
    toward the user), or 0 (no wheel motion this event) - normalized to
    a single line step rather than honoring the raw ~120-per-notch
    magnitude, so behavior stays consistent across devices/backends that
    report finer-grained deltas (e.g. touchpads).
    """
    raw = (flags >> 16) & 0xFFFF
    if raw >= 0x8000:
        raw -= 0x10000

    if raw > 0:
        return 1
    if raw < 0:
        return -1
    return 0