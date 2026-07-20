"""Stateless, time-based frame selection for an animated piece (see
UI_PLAN.md Sec 5) - no per-piece threads or blocking loops. Each render
tick, for each piece, the caller computes elapsed_ms = now - state_entered_at
and calls frame_index() fresh; this module holds no state of its own
between calls, so it works for arbitrarily many independently-animating
pieces within a single non-blocking render loop.

Deliberately takes state_entered_at's elapsed time as its input, not a
per-leg elapsed time - a multi-cell move's walking animation must stay
continuous across leg boundaries (state stays MOVING, state_entered_at
does not reset per leg), even though the pixel-position glide computed
separately from in_flight_leg's leg_started_at_ms/complete_at_ms does
reset at every leg.

No guarding of negative elapsed_ms or num_frames <= 0: elapsed_ms is
always derived from the same monotonic engine clock that stamped
state_entered_at, so it can never go negative, and every SpriteSet is
built from a real sprites/ directory that always has at least one frame.
"""


def frame_index(elapsed_ms, frames_per_sec, num_frames, is_loop):
    """The 0-based index into an ordered frame sequence to show right
    now. Looped states (idle, move, rests) cycle forever; non-looped
    states (jump) hold their final frame once finished, rather than
    restarting or raising.
    """
    raw_index = int((elapsed_ms / 1000.0) * frames_per_sec)
    if is_loop:
        return raw_index % num_frames
    return min(raw_index, num_frames - 1)