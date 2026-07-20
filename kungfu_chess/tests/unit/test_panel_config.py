from kungfu_chess.config.panel_config import (
    PanelConfig,
    load_panel_config,
    parse_panel_config,
)


def test_parse_panel_config_reads_all_fields():
    data = {
        "panel_width_px": 200,
        "line_height_px": 20,
        "font_scale": 0.6,
        "font_thickness": 2,
        "text_color": [255, 255, 255],
        "background_color": [0, 0, 0],
        "padding_px": 5,
        "labels": {"w": "White", "b": "Black"},
    }
    config = parse_panel_config(data)
    assert config == PanelConfig(
        panel_width_px=200,
        line_height_px=20,
        font_scale=0.6,
        font_thickness=2,
        text_color=(255, 255, 255),
        background_color=(0, 0, 0),
        padding_px=5,
        labels={"w": "White", "b": "Black"},
    )


def test_load_panel_config_reads_json_file_from_disk(tmp_path):
    config_path = tmp_path / "panel_config.json"
    config_path.write_text(
        """
        {
          "panel_width_px": 300,
          "line_height_px": 30,
          "font_scale": 0.7,
          "font_thickness": 1,
          "text_color": [10, 20, 30],
          "background_color": [40, 50, 60],
          "padding_px": 12,
          "labels": {"w": "White", "b": "Black"}
        }
        """,
        encoding="utf-8",
    )
    config = load_panel_config(config_path)
    assert config == PanelConfig(
        panel_width_px=300,
        line_height_px=30,
        font_scale=0.7,
        font_thickness=1,
        text_color=(10, 20, 30),
        background_color=(40, 50, 60),
        padding_px=12,
        labels={"w": "White", "b": "Black"},
    )


def test_load_panel_config_default_path_matches_recommended_values():
    config = load_panel_config()
    assert config == PanelConfig(
        panel_width_px=240,
        line_height_px=24,
        font_scale=0.5,
        font_thickness=1,
        text_color=(255, 255, 255),
        background_color=(30, 30, 30),
        padding_px=10,
        labels={"w": "White", "b": "Black"},
    )