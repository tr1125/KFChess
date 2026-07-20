from kungfu_chess.view.animation_clock import frame_index


# --- elapsed = 0: always frame 0, loop or not ---

def test_frame_index_at_zero_elapsed_is_first_frame_when_looped():
    assert frame_index(elapsed_ms=0, frames_per_sec=8, num_frames=5, is_loop=True) == 0


def test_frame_index_at_zero_elapsed_is_first_frame_when_not_looped():
    assert frame_index(elapsed_ms=0, frames_per_sec=10, num_frames=5, is_loop=False) == 0


# --- looped: wraps around via modulo ---

def test_frame_index_advances_partway_through_a_loop():
    # elapsed 375ms at 8fps -> raw index int(0.375 * 8) = 3
    assert frame_index(elapsed_ms=375, frames_per_sec=8, num_frames=5, is_loop=True) == 3


def test_frame_index_wraps_around_past_the_end_when_looped():
    # elapsed 700ms at 10fps -> raw index 7, wraps to 7 % 5 = 2
    assert frame_index(elapsed_ms=700, frames_per_sec=10, num_frames=5, is_loop=True) == 2


def test_frame_index_at_an_exact_frame_boundary():
    # elapsed 125ms at 8fps -> raw index int(1.0) = 1 exactly
    assert frame_index(elapsed_ms=125, frames_per_sec=8, num_frames=5, is_loop=True) == 1


# --- non-looped: clamps to the last frame instead of wrapping ---

def test_frame_index_partway_through_a_non_looped_sequence_is_not_yet_clamped():
    # elapsed 250ms at 10fps -> raw index 2, well within 5 frames
    assert frame_index(elapsed_ms=250, frames_per_sec=10, num_frames=5, is_loop=False) == 2


def test_frame_index_past_the_end_of_a_non_looped_sequence_holds_the_last_frame():
    # elapsed 1000ms at 10fps -> raw index 10, clamped to num_frames - 1 = 4
    assert frame_index(elapsed_ms=1000, frames_per_sec=10, num_frames=5, is_loop=False) == 4


def test_frame_index_far_past_the_end_of_a_non_looped_sequence_stays_clamped():
    assert frame_index(elapsed_ms=60000, frames_per_sec=10, num_frames=5, is_loop=False) == 4