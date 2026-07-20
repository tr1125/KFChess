from kungfu_chess.config.promotion_menu_config import (
    PromotionMenuConfig,
    load_promotion_menu_config,
    parse_promotion_menu_config,
)


def test_parse_promotion_menu_config_reads_all_fields():
    data = {
        "icon_size_px": 40,
        "spacing_px": 5,
        "padding_px": 8,
        "background_color": [10, 20, 30],
        "border_color": [200, 200, 200],
        "border_thickness": 2,
        "text_color": [255, 255, 255],
        "font_scale": 0.8,
        "font_thickness": 1,
        "choice_order": ["Q", "R", "B", "N"],
    }
    config = parse_promotion_menu_config(data)
    assert config == PromotionMenuConfig(
        icon_size_px=40,
        spacing_px=5,
        padding_px=8,
        background_color=(10, 20, 30),
        border_color=(200, 200, 200),
        border_thickness=2,
        text_color=(255, 255, 255),
        font_scale=0.8,
        font_thickness=1,
        choice_order=("Q", "R", "B", "N"),
    )


def test_load_promotion_menu_config_reads_json_file_from_disk(tmp_path):
    config_path = tmp_path / "promotion_menu_config.json"
    config_path.write_text(
        """
        {
          "icon_size_px": 50,
          "spacing_px": 6,
          "padding_px": 10,
          "background_color": [1, 2, 3],
          "border_color": [4, 5, 6],
          "border_thickness": 1,
          "text_color": [7, 8, 9],
          "font_scale": 0.7,
          "font_thickness": 2,
          "choice_order": ["Q", "R"]
        }
        """,
        encoding="utf-8",
    )
    config = load_promotion_menu_config(config_path)
    assert config == PromotionMenuConfig(
        icon_size_px=50,
        spacing_px=6,
        padding_px=10,
        background_color=(1, 2, 3),
        border_color=(4, 5, 6),
        border_thickness=1,
        text_color=(7, 8, 9),
        font_scale=0.7,
        font_thickness=2,
        choice_order=("Q", "R"),
    )


def test_load_promotion_menu_config_default_path_matches_recommended_values():
    config = load_promotion_menu_config()
    assert config == PromotionMenuConfig(
        icon_size_px=48,
        spacing_px=4,
        padding_px=6,
        background_color=(30, 30, 30),
        border_color=(255, 255, 255),
        border_thickness=1,
        text_color=(255, 255, 255),
        font_scale=0.9,
        font_thickness=2,
        choice_order=("Q", "R", "B", "N"),
    )