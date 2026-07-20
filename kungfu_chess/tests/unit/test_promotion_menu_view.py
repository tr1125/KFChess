from kungfu_chess.config.promotion_menu_config import PromotionMenuConfig
from kungfu_chess.view.promotion_menu_view import (
    PromotionMenuData,
    PromotionMenuView,
    menu_size_px,
    option_bounds,
    ordered_choices,
)
import kungfu_chess.view.promotion_menu_view as promotion_menu_view_module


def make_config(icon_size_px=20, spacing_px=2, padding_px=3, choice_order=("Q", "R", "B", "N")):
    return PromotionMenuConfig(
        icon_size_px=icon_size_px,
        spacing_px=spacing_px,
        padding_px=padding_px,
        background_color=(20, 20, 20),
        border_color=(255, 255, 255),
        border_thickness=1,
        text_color=(255, 255, 255),
        font_scale=0.5,
        font_thickness=1,
        choice_order=choice_order,
    )


# --- ordered_choices ---


def test_ordered_choices_follows_configured_order_regardless_of_input_order():
    config = make_config(choice_order=("Q", "R", "B", "N"))
    assert ordered_choices(("N", "Q", "B"), config) == ["Q", "B", "N"]


def test_ordered_choices_handles_a_rule_with_fewer_options():
    config = make_config(choice_order=("Q", "R", "B", "N"))
    assert ordered_choices(("R", "Q"), config) == ["Q", "R"]


# --- option_bounds / menu_size_px ---


def test_option_bounds_lays_out_slots_left_to_right_with_padding_and_spacing():
    config = make_config(icon_size_px=10, spacing_px=2, padding_px=3)
    assert option_bounds(3, config) == [(3, 13), (15, 25), (27, 37)]


def test_option_bounds_empty_for_zero_choices():
    config = make_config()
    assert option_bounds(0, config) == []


def test_menu_size_px_matches_the_last_option_bound_plus_padding():
    config = make_config(icon_size_px=10, spacing_px=2, padding_px=3)
    width, height = menu_size_px(3, config)
    assert width == 37 + 3  # last bound's x1 (37) + trailing padding
    assert height == 10 + 2 * 3  # icon_size_px + padding on top and bottom


def test_menu_size_px_does_not_crash_for_zero_choices():
    config = make_config(icon_size_px=10, padding_px=3)
    width, height = menu_size_px(0, config)
    assert width == 6
    assert height == 16


# --- PromotionMenuView.render_frame ---


def make_recording_draw_calls(monkeypatch):
    """Records rectangle/text draw calls instead of actually rasterizing,
    matching test_side_panel_view.py's fake-cv2.putText convention."""
    rectangles = []
    texts = []

    def fake_rectangle(img, pt1, pt2, color, thickness):
        rectangles.append((pt1, pt2, color, thickness))

    def fake_put_text(img, text, org, *args, **kwargs):
        texts.append((text, org))

    monkeypatch.setattr(promotion_menu_view_module.cv2, "rectangle", fake_rectangle)
    monkeypatch.setattr(promotion_menu_view_module.cv2, "putText", fake_put_text)
    return rectangles, texts


def test_render_frame_returns_canvas_of_exact_shape(monkeypatch):
    make_recording_draw_calls(monkeypatch)
    config = make_config(icon_size_px=20, spacing_px=2, padding_px=3)
    view = PromotionMenuView(config)

    frame = view.render_frame(PromotionMenuData(color="w", choices=("Q", "R", "B", "N")))

    assert frame.shape == menu_size_px(4, config)[::-1] + (3,)


def test_render_frame_draws_one_option_box_per_choice_in_configured_order(monkeypatch):
    rectangles, texts = make_recording_draw_calls(monkeypatch)
    config = make_config(choice_order=("Q", "R", "B", "N"))
    view = PromotionMenuView(config)

    view.render_frame(PromotionMenuData(color="w", choices=("N", "Q")))

    drawn_letters = [text for text, _org in texts]
    assert drawn_letters == ["Q", "N"]
    # one outer-border rectangle + one box per option
    assert len(rectangles) == 1 + 2


def test_render_frame_empty_choices_draws_only_the_outer_border(monkeypatch):
    rectangles, texts = make_recording_draw_calls(monkeypatch)
    view = PromotionMenuView(make_config())

    frame = view.render_frame(PromotionMenuData(color="b", choices=()))

    assert frame.shape[2] == 3
    assert texts == []
    assert len(rectangles) == 1