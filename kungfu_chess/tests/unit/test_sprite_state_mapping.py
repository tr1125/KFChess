from kungfu_chess.config.sprite_state_mapping import (
    SpriteStateEntry,
    SpriteStateMapping,
    folder_for_state_name,
    load_sprite_state_mapping,
    parse_sprite_state_mapping,
)
from kungfu_chess.model.piece import PieceState


def test_parse_sprite_state_mapping_builds_entries_from_data():
    data = {
        "mapping": [
            {"state": "IDLE", "folder": "idle"},
            {"state": "CAPTURED", "folder": None},
        ]
    }
    mapping = parse_sprite_state_mapping(data)
    assert mapping == SpriteStateMapping(
        entries=(
            SpriteStateEntry(state_name="IDLE", folder_name="idle"),
            SpriteStateEntry(state_name="CAPTURED", folder_name=None),
        )
    )


def test_folder_for_state_name_returns_mapped_folder():
    mapping = load_sprite_state_mapping()
    assert folder_for_state_name(mapping, "IDLE") == "idle"
    assert folder_for_state_name(mapping, "MOVING") == "move"
    assert folder_for_state_name(mapping, "AIRBORNE") == "jump"
    assert folder_for_state_name(mapping, "LONG_REST") == "long_rest"
    assert folder_for_state_name(mapping, "SHORT_REST") == "short_rest"


def test_folder_for_state_name_returns_none_for_captured():
    mapping = load_sprite_state_mapping()
    assert folder_for_state_name(mapping, "CAPTURED") is None


def test_folder_for_state_name_returns_none_for_unknown_state_name():
    mapping = load_sprite_state_mapping()
    assert folder_for_state_name(mapping, "BOGUS") is None


def test_load_sprite_state_mapping_reads_json_file_from_disk(tmp_path):
    mapping_path = tmp_path / "sprite_state_mapping.json"
    mapping_path.write_text(
        """
        {
          "mapping": [
            {"state": "IDLE", "folder": "idle"}
          ]
        }
        """,
        encoding="utf-8",
    )
    mapping = load_sprite_state_mapping(mapping_path)
    assert mapping == SpriteStateMapping(
        entries=(SpriteStateEntry(state_name="IDLE", folder_name="idle"),)
    )


def test_load_sprite_state_mapping_default_path_matches_recommended_table():
    mapping = load_sprite_state_mapping()
    assert mapping == SpriteStateMapping(
        entries=(
            SpriteStateEntry(state_name="IDLE", folder_name="idle"),
            SpriteStateEntry(state_name="MOVING", folder_name="move"),
            SpriteStateEntry(state_name="AIRBORNE", folder_name="jump"),
            SpriteStateEntry(state_name="LONG_REST", folder_name="long_rest"),
            SpriteStateEntry(state_name="SHORT_REST", folder_name="short_rest"),
            SpriteStateEntry(state_name="CAPTURED", folder_name=None),
        )
    )


def test_load_sprite_state_mapping_default_path_covers_every_piece_state():
    mapping = load_sprite_state_mapping()
    mapped_state_names = {entry.state_name for entry in mapping.entries}
    assert mapped_state_names == set(PieceState.__members__)