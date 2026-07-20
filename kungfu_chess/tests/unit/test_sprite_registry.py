import os

from kungfu_chess.config.sprite_state_mapping import parse_sprite_state_mapping
from kungfu_chess.view.sprite_registry import SpriteRegistry, SpriteSet


def make_sprite_state_mapping():
    return parse_sprite_state_mapping(
        {
            "mapping": [
                {"state": "IDLE", "folder": "idle"},
                {"state": "MOVING", "folder": "move"},
                {"state": "AIRBORNE", "folder": "jump"},
                {"state": "LONG_REST", "folder": "long_rest"},
                {"state": "SHORT_REST", "folder": "short_rest"},
                {"state": "CAPTURED", "folder": None},
            ]
        }
    )


class FakeFilesystem:
    """No real files touched - frame counts and config.json contents are
    supplied up front, keyed by the exact directory/file path SpriteRegistry
    is expected to ask for. Records every call so tests can assert on
    memoization.
    """

    def __init__(self, frame_counts, configs):
        self._frame_counts = frame_counts  # {sprites_dir_path: count}
        self._configs = configs  # {config_json_path: dict}
        self.listdir_calls = []
        self.read_config_calls = []

    def listdir(self, path):
        self.listdir_calls.append(path)
        count = self._frame_counts[path]
        return [f"{i}.png" for i in range(1, count + 1)]

    def read_config(self, path):
        self.read_config_calls.append(path)
        return self._configs[path]


def idle_state_dir(assets_pieces_dir="assets/pieces", color="w", kind="P"):
    return os.path.join(assets_pieces_dir, f"{color}{kind}", "states", "idle")


def make_registry(frame_counts, configs, assets_pieces_dir="assets/pieces", mapping=None):
    fs = FakeFilesystem(frame_counts, configs)
    registry = SpriteRegistry(
        mapping if mapping is not None else make_sprite_state_mapping(),
        assets_pieces_dir,
        listdir=fs.listdir,
        read_config=fs.read_config,
    )
    return registry, fs


# --- unmapped state (e.g. CAPTURED) ---

def test_get_returns_none_for_a_state_with_no_mapped_folder():
    registry, fs = make_registry(frame_counts={}, configs={})

    result = registry.get("w", "Q", "CAPTURED")

    assert result is None
    assert fs.listdir_calls == []
    assert fs.read_config_calls == []


def test_get_returns_none_for_a_state_name_absent_from_the_mapping():
    registry, fs = make_registry(frame_counts={}, configs={})

    assert registry.get("w", "Q", "SOME_UNKNOWN_STATE") is None


# --- resolving a mapped state ---

def test_get_builds_frame_paths_in_order():
    state_dir = idle_state_dir()
    sprites_dir = os.path.join(state_dir, "sprites")
    config_path = os.path.join(state_dir, "config.json")
    registry, fs = make_registry(
        frame_counts={sprites_dir: 3},
        configs={config_path: {"graphics": {"frames_per_sec": 4, "is_loop": True}}},
    )

    sprite_set = registry.get("w", "P", "IDLE")

    assert sprite_set.frame_paths == (
        os.path.join(state_dir, "sprites", "1.png"),
        os.path.join(state_dir, "sprites", "2.png"),
        os.path.join(state_dir, "sprites", "3.png"),
    )


def test_get_reads_frames_per_sec_and_is_loop_from_config():
    state_dir = idle_state_dir(color="b", kind="N")
    sprites_dir = os.path.join(state_dir, "sprites")
    config_path = os.path.join(state_dir, "config.json")
    registry, fs = make_registry(
        frame_counts={sprites_dir: 1},
        configs={config_path: {"graphics": {"frames_per_sec": 10, "is_loop": False}}},
    )

    sprite_set = registry.get("b", "N", "IDLE")

    assert sprite_set.frames_per_sec == 10
    assert sprite_set.is_loop is False


def test_sprite_set_num_frames_matches_the_number_of_frame_paths():
    sprite_set = SpriteSet(frame_paths=("a.png", "b.png"), frames_per_sec=8, is_loop=True)
    assert sprite_set.num_frames == 2


def test_get_reads_the_config_and_sprites_dir_for_the_mapped_folder_not_the_state_name():
    # state "MOVING" maps to folder "move", not "moving" - paths must
    # reflect the mapped folder name.
    move_dir = os.path.join("assets/pieces", "wR", "states", "move")
    sprites_dir = os.path.join(move_dir, "sprites")
    config_path = os.path.join(move_dir, "config.json")
    registry, fs = make_registry(
        frame_counts={sprites_dir: 2},
        configs={config_path: {"graphics": {"frames_per_sec": 8, "is_loop": True}}},
    )

    registry.get("w", "R", "MOVING")

    assert fs.listdir_calls == [sprites_dir]
    assert fs.read_config_calls == [config_path]


# --- memoization ---

def test_get_memoizes_so_the_filesystem_is_only_consulted_once_per_key():
    state_dir = idle_state_dir()
    sprites_dir = os.path.join(state_dir, "sprites")
    config_path = os.path.join(state_dir, "config.json")
    registry, fs = make_registry(
        frame_counts={sprites_dir: 1},
        configs={config_path: {"graphics": {"frames_per_sec": 4, "is_loop": True}}},
    )

    first = registry.get("w", "P", "IDLE")
    second = registry.get("w", "P", "IDLE")

    assert first is second
    assert fs.listdir_calls == [sprites_dir]
    assert fs.read_config_calls == [config_path]


def test_get_does_not_share_cache_across_different_state_names():
    state_dir = idle_state_dir()
    move_dir = os.path.join("assets/pieces", "wP", "states", "move")
    registry, fs = make_registry(
        frame_counts={
            os.path.join(state_dir, "sprites"): 1,
            os.path.join(move_dir, "sprites"): 1,
        },
        configs={
            os.path.join(state_dir, "config.json"): {"graphics": {"frames_per_sec": 4, "is_loop": True}},
            os.path.join(move_dir, "config.json"): {"graphics": {"frames_per_sec": 8, "is_loop": True}},
        },
    )

    idle_set = registry.get("w", "P", "IDLE")
    move_set = registry.get("w", "P", "MOVING")

    assert idle_set.frames_per_sec == 4
    assert move_set.frames_per_sec == 8
    assert len(fs.listdir_calls) == 2


def test_get_does_not_share_cache_across_different_pieces():
    white_dir = idle_state_dir(color="w", kind="P")
    black_dir = idle_state_dir(color="b", kind="P")
    registry, fs = make_registry(
        frame_counts={
            os.path.join(white_dir, "sprites"): 1,
            os.path.join(black_dir, "sprites"): 1,
        },
        configs={
            os.path.join(white_dir, "config.json"): {"graphics": {"frames_per_sec": 4, "is_loop": True}},
            os.path.join(black_dir, "config.json"): {"graphics": {"frames_per_sec": 4, "is_loop": True}},
        },
    )

    registry.get("w", "P", "IDLE")
    registry.get("b", "P", "IDLE")

    assert len(fs.listdir_calls) == 2