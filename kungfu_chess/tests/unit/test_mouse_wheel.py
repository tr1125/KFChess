from kungfu_chess.driver.mouse_wheel import wheel_delta_from_flags


def flags_with_wheel_delta(raw_delta):
    """Builds a synthetic cv2 mouse-callback `flags` int carrying
    raw_delta in its signed high 16 bits, matching the documented Win32
    WM_MOUSEWHEEL encoding this module decodes.
    """
    return (raw_delta & 0xFFFF) << 16


def test_positive_delta_decodes_to_plus_one():
    assert wheel_delta_from_flags(flags_with_wheel_delta(120)) == 1


def test_negative_delta_decodes_to_minus_one():
    assert wheel_delta_from_flags(flags_with_wheel_delta(-120)) == -1


def test_zero_delta_decodes_to_zero():
    assert wheel_delta_from_flags(flags_with_wheel_delta(0)) == 0


def test_large_positive_delta_still_normalizes_to_plus_one():
    assert wheel_delta_from_flags(flags_with_wheel_delta(240)) == 1


def test_large_negative_delta_still_normalizes_to_minus_one():
    assert wheel_delta_from_flags(flags_with_wheel_delta(-240)) == -1


def test_small_fractional_style_delta_still_decodes_by_sign():
    # A backend reporting a smaller-magnitude notch (e.g. some touchpads)
    # should still normalize to a single line step, not be dropped.
    assert wheel_delta_from_flags(flags_with_wheel_delta(1)) == 1
    assert wheel_delta_from_flags(flags_with_wheel_delta(-1)) == -1


def test_low_bits_of_flags_do_not_affect_the_decoded_delta():
    # The low 16 bits carry modifier-key/button state (ctrl, shift, etc.)
    # on a real cv2 callback - decoding must ignore them entirely.
    base = flags_with_wheel_delta(120)
    assert wheel_delta_from_flags(base | 0x00FF) == 1
    assert wheel_delta_from_flags(base | 0xFFFF) == 1