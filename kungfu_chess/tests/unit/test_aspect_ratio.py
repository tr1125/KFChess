import numpy as np
import pytest

from kungfu_chess.driver.aspect_ratio import (
    LETTERBOX_COLOR,
    canvas_to_native,
    centering_offset,
    compose_letterboxed,
    fit_size,
)


def test_fit_size_matches_native_when_available_equals_native():
    assert fit_size((822, 828), (822, 828)) == (822, 828)


def test_fit_size_scales_up_uniformly_when_available_matches_ratio():
    assert fit_size((822, 828), (1644, 1656)) == (1644, 1656)


def test_fit_size_is_width_constrained_when_available_is_wider_than_native_ratio():
    # Width doubled, height unchanged - board's own ratio means height is the binding constraint.
    assert fit_size((822, 828), (1644, 828)) == (822, 828)


def test_fit_size_is_height_constrained_when_available_is_taller_than_native_ratio():
    assert fit_size((822, 828), (822, 1656)) == (822, 828)


def test_fit_size_downscales_preserving_ratio():
    assert fit_size((800, 600), (100, 100)) == (100, 75)


def test_fit_size_falls_back_to_native_when_available_is_degenerate():
    assert fit_size((822, 828), (0, 0)) == (822, 828)


@pytest.mark.parametrize(
    "native_size,available_size",
    [
        ((822, 828), (400, 900)),
        ((822, 828), (2000, 300)),
        ((400, 300), (150, 500)),
        ((1, 1), (7, 13)),
        ((16, 9), (1000, 1000)),
        ((103, 206), (250, 60)),
    ],
)
def test_fit_size_preserves_ratio_and_fits_within_bounds(native_size, available_size):
    native_w, native_h = native_size
    available_w, available_h = available_size

    fit_w, fit_h = fit_size(native_size, available_size)

    assert 1 <= fit_w <= available_w
    assert 1 <= fit_h <= available_h

    native_ratio = native_w / native_h
    fit_ratio = fit_w / fit_h
    assert fit_ratio == pytest.approx(native_ratio, rel=0.02)

    # "Largest that fits": at least one dimension should be pinned to the
    # available bound (the non-binding one is what gets letterboxed).
    assert fit_w == available_w or fit_h == available_h


def test_centering_offset_centers_evenly():
    assert centering_offset((100, 100), (80, 60)) == (10, 20)


def test_centering_offset_floors_odd_remainders():
    assert centering_offset((101, 101), (80, 60)) == (10, 20)


def test_canvas_to_native_top_left_of_content_maps_to_native_origin():
    assert canvas_to_native(50, 20, native_size=(822, 828), content_size=(822, 828), offset=(50, 20)) == (0, 0)


def test_canvas_to_native_scales_within_content_area():
    # content is a 2x downscale of native; a click at content-local (10, 10) should map to native (20, 20).
    assert canvas_to_native(10, 10, native_size=(200, 200), content_size=(100, 100), offset=(0, 0)) == (20, 20)


def test_canvas_to_native_returns_none_for_click_in_left_letterbox_bar():
    assert canvas_to_native(5, 20, native_size=(822, 828), content_size=(822, 828), offset=(50, 20)) is None


def test_canvas_to_native_returns_none_for_click_in_bottom_letterbox_bar():
    # content occupies y in [20, 848); a click at y=900 is past the bottom edge.
    assert canvas_to_native(60, 900, native_size=(822, 828), content_size=(822, 828), offset=(50, 20)) is None


def test_canvas_to_native_returns_none_for_degenerate_content_size():
    assert canvas_to_native(10, 10, native_size=(822, 828), content_size=(0, 0), offset=(0, 0)) is None


def test_canvas_to_native_round_trip_within_rounding_tolerance():
    native_size = (822, 828)
    available_size = (600, 900)  # height-constrained, pillarboxed left/right
    content_size = fit_size(native_size, available_size)
    offset = centering_offset(available_size, content_size)

    for native_target in [(0, 0), (100, 200), (411, 414), (821, 827)]:
        nx, ny = native_target
        content_w, content_h = content_size
        native_w, native_h = native_size
        canvas_x = offset[0] + round(nx * content_w / native_w)
        canvas_y = offset[1] + round(ny * content_h / native_h)

        recovered = canvas_to_native(canvas_x, canvas_y, native_size, content_size, offset)

        assert recovered is not None
        assert abs(recovered[0] - nx) <= 1
        assert abs(recovered[1] - ny) <= 1


def test_compose_letterboxed_canvas_has_available_shape():
    frame = np.full((828, 822, 3), 200, dtype=np.uint8)
    canvas, content_size, offset = compose_letterboxed(frame, (600, 900))

    assert canvas.shape == (900, 600, 3)
    assert content_size == fit_size((822, 828), (600, 900))
    assert offset == centering_offset((600, 900), content_size)


def test_compose_letterboxed_fills_bars_with_letterbox_color():
    frame = np.full((828, 822, 3), 200, dtype=np.uint8)
    canvas, content_size, offset = compose_letterboxed(frame, (600, 900))

    # native (822x828) is nearly square while available (600x900) is tall and
    # narrow, so width is the binding constraint - bars land top/bottom.
    _, offset_y = offset
    assert offset_y > 0
    assert tuple(canvas[0, 0]) == LETTERBOX_COLOR
    assert tuple(canvas[-1, 0]) == LETTERBOX_COLOR


def test_compose_letterboxed_places_content_at_computed_offset():
    frame = np.full((828, 822, 3), 200, dtype=np.uint8)
    canvas, content_size, offset = compose_letterboxed(frame, (600, 900))

    content_w, content_h = content_size
    offset_x, offset_y = offset
    center_x, center_y = offset_x + content_w // 2, offset_y + content_h // 2
    assert tuple(canvas[center_y, center_x]) == (200, 200, 200)


def test_compose_letterboxed_no_bars_when_ratio_already_matches():
    frame = np.full((828, 822, 3), 200, dtype=np.uint8)
    canvas, content_size, offset = compose_letterboxed(frame, (822, 828))

    assert content_size == (822, 828)
    assert offset == (0, 0)