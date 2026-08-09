from kungfu_chess.config.panel_config import PanelConfig
from kungfu_chess.observers.move_log_observer import PanelData
from kungfu_chess.view.side_panel_view import SidePanelView
import kungfu_chess.view.side_panel_view as side_panel_view_module


def make_panel_config(panel_width_px=100, line_height_px=10, padding_px=2):
    return PanelConfig(
        panel_width_px=panel_width_px,
        line_height_px=line_height_px,
        font_scale=0.5,
        font_thickness=1,
        text_color=(255, 255, 255),
        background_color=(20, 20, 20),
        padding_px=padding_px,
        labels={"w": "White", "b": "Black"},
    )


def make_recording_put_text(monkeypatch):
    """Records (text, org) for every draw call instead of actually
    rasterizing text, so tests can assert exactly which lines were drawn
    (and in what order) without resorting to OCR on pixel output.
    """
    calls = []

    def fake_put_text(img, text, org, *args, **kwargs):
        calls.append((text, org))

    monkeypatch.setattr(side_panel_view_module.cv2, "putText", fake_put_text)
    return calls


def test_render_frame_returns_canvas_of_exact_shape(monkeypatch):
    make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config(panel_width_px=120))
    panel_data = PanelData(color="w", score=0, moves=[])

    frame = view.render_frame(panel_data, height_px=200)

    assert frame.shape == (200, 120, 3)


def test_render_frame_draws_header_with_label_and_score(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config())
    panel_data = PanelData(color="w", score=7, moves=[])

    view.render_frame(panel_data, height_px=200)

    assert calls[0][0] == "White: 7"


def test_render_frame_appends_rating_to_the_header_when_set(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config())
    panel_data = PanelData(color="w", score=7, moves=[], rating=1350)

    view.render_frame(panel_data, height_px=200)

    assert calls[0][0] == "White: 7  (rating 1350)"


def test_render_frame_header_unchanged_when_rating_is_none(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config())
    panel_data = PanelData(color="w", score=7, moves=[], rating=None)

    view.render_frame(panel_data, height_px=200)

    assert calls[0][0] == "White: 7"


def test_render_frame_draws_most_recent_moves_when_unscrolled(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    config = make_panel_config(line_height_px=10, padding_px=0)
    view = SidePanelView(config)
    moves = [f"m{i}" for i in range(20)]
    panel_data = PanelData(color="w", score=0, moves=moves)

    # header (line 1) + a blank gap line + exactly 3 move lines worth of height.
    view.render_frame(panel_data, height_px=10 * 2 + 10 * 3, scroll_offset=0)

    drawn_moves = [text for text, _org in calls[1:]]
    assert drawn_moves == moves[-3:]


def test_render_frame_scroll_offset_reveals_older_moves_not_a_hard_truncation(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    config = make_panel_config(line_height_px=10, padding_px=0)
    view = SidePanelView(config)
    moves = [f"m{i}" for i in range(20)]
    panel_data = PanelData(color="w", score=0, moves=moves)

    view.render_frame(panel_data, height_px=10 * 2 + 10 * 3, scroll_offset=5)

    drawn_moves = [text for text, _org in calls[1:]]
    assert drawn_moves == moves[12:15]
    assert drawn_moves != moves[-3:]  # confirms this genuinely differs from the unscrolled view


def test_render_frame_out_of_range_scroll_offset_does_not_crash(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config())
    panel_data = PanelData(color="b", score=3, moves=["e4", "d5"])

    frame = view.render_frame(panel_data, height_px=200, scroll_offset=99999)

    assert frame.shape[2] == 3
    drawn_moves = [text for text, _org in calls[1:]]
    assert drawn_moves == ["e4", "d5"]


def test_render_frame_empty_moves_and_zero_score_does_not_crash(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config())
    panel_data = PanelData(color="w", score=0, moves=[])

    frame = view.render_frame(panel_data, height_px=200)

    assert frame.shape[2] == 3
    assert calls[0][0] == "White: 0"
    assert len(calls) == 1  # header only, no move lines


def test_render_frame_width_px_overrides_configured_panel_width(monkeypatch):
    make_recording_put_text(monkeypatch)
    view = SidePanelView(make_panel_config(panel_width_px=240))
    panel_data = PanelData(color="w", score=0, moves=[])

    frame = view.render_frame(panel_data, height_px=100, width_px=60)

    assert frame.shape == (100, 60, 3)


def test_render_frame_uses_color_as_fallback_label_when_unmapped(monkeypatch):
    calls = make_recording_put_text(monkeypatch)
    config = PanelConfig(
        panel_width_px=100, line_height_px=10, font_scale=0.5, font_thickness=1,
        text_color=(255, 255, 255), background_color=(0, 0, 0), padding_px=2, labels={},
    )
    view = SidePanelView(config)
    panel_data = PanelData(color="w", score=1, moves=[])

    view.render_frame(panel_data, height_px=200)

    assert calls[0][0] == "w: 1"