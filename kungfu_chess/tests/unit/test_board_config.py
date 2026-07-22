from kungfu_chess.config.board_config import (
    BoardConfig,
    load_board_config,
    parse_board_config,
    px_per_meter,
)


def test_parse_board_config_reads_all_fields():
    data = {
        "image_width_px": 800,
        "image_height_px": 600,
        "margin_left_px": 10,
        "margin_top_px": 20,
        "cell_size_px": 80,
        "cell_size_meters": 2.0,
    }
    config = parse_board_config(data)
    assert config == BoardConfig(
        image_width_px=800,
        image_height_px=600,
        margin_left_px=10,
        margin_top_px=20,
        cell_size_px=80,
        cell_size_meters=2.0,
    )


def test_px_per_meter_divides_cell_size_by_meters_per_cell():
    config = BoardConfig(
        image_width_px=0, image_height_px=0,
        margin_left_px=0, margin_top_px=0,
        cell_size_px=200, cell_size_meters=2,
    )
    assert px_per_meter(config) == 100


def test_px_per_meter_with_one_meter_per_cell_equals_cell_size_px():
    config = BoardConfig(
        image_width_px=0, image_height_px=0,
        margin_left_px=0, margin_top_px=0,
        cell_size_px=103, cell_size_meters=1,
    )
    assert px_per_meter(config) == 103


def test_load_board_config_reads_json_file_from_disk(tmp_path):
    config_path = tmp_path / "board_config.json"
    config_path.write_text(
        """
        {
          "image_width_px": 400,
          "image_height_px": 400,
          "margin_left_px": 5,
          "margin_top_px": 5,
          "cell_size_px": 50,
          "cell_size_meters": 1.0
        }
        """,
        encoding="utf-8",
    )
    config = load_board_config(config_path)
    assert config == BoardConfig(
        image_width_px=400,
        image_height_px=400,
        margin_left_px=5,
        margin_top_px=5,
        cell_size_px=50,
        cell_size_meters=1.0,
    )


def test_load_board_config_default_path_matches_recommended_values():
    config = load_board_config()
    assert config == BoardConfig(
        image_width_px=847,
        image_height_px=851,
        margin_left_px=47,
        margin_top_px=47,
        cell_size_px=94,
        cell_size_meters=1.0,
    )