from kungfu_chess.config.selection_config import (
    SelectionConfig,
    load_selection_config,
    parse_selection_config,
)

#TODO: mocking test_config files especcially for the tests
def test_parse_selection_config_reads_all_fields():
    data = {"color": [10, 20, 30], "thickness": 2}
    config = parse_selection_config(data)
    assert config == SelectionConfig(color=(10, 20, 30), thickness=2)


def test_load_selection_config_reads_json_file_from_disk(tmp_path):
    config_path = tmp_path / "selection_config.json"
    config_path.write_text(
        """
        {
          "color": [1, 2, 3],
          "thickness": 4
        }
        """,
        encoding="utf-8",
    )
    config = load_selection_config(config_path)
    assert config == SelectionConfig(color=(1, 2, 3), thickness=4)


def test_load_selection_config_default_path_matches_recommended_values():
    config = load_selection_config()
    assert config == SelectionConfig(color=(61, 175, 217), thickness=2)