import os

import numpy as np
import pytest

from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.config.board_config import BoardConfig
from kungfu_chess.config.sprite_state_mapping import parse_sprite_state_mapping
from kungfu_chess.view.opencv_view import OpenCvView, SpriteCache, alpha_composite, sprite_path, _imread_unicode_safe
from kungfu_chess.view.sprite_registry import SpriteSet


def board_from(rows):
    return Board([[None if cell == "." else Piece(color=cell[0], kind=cell[1]) for cell in row] for row in rows])


def make_game_state(rows):
    board = board_from(rows)
    state = GameState()
    state.attach_board(board)
    return state, board


def make_board_config(cell_size_px=2, margin_left_px=0, margin_top_px=0):
    return BoardConfig(
        image_width_px=100,
        image_height_px=100,
        margin_left_px=margin_left_px,
        margin_top_px=margin_top_px,
        cell_size_px=cell_size_px,
        cell_size_meters=1.0,
    )


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


# --- sprite_path ---


def test_sprite_path_builds_expected_path():
    path = sprite_path("assets/pieces", "w", "P", "idle")
    assert path == os.path.join("assets/pieces", "wP", "states", "idle", "sprites", "1.png")


def test_sprite_path_respects_custom_frame_filename():
    path = sprite_path("assets/pieces", "b", "K", "move", frame_filename="2.png")
    assert path == os.path.join("assets/pieces", "bK", "states", "move", "sprites", "2.png")


# --- alpha_composite ---


def test_alpha_composite_fully_opaque_sprite_overwrites_background():
    background = np.full((2, 2, 3), fill_value=100, dtype=np.uint8)
    sprite = np.zeros((2, 2, 4), dtype=np.uint8)
    sprite[:, :, :3] = 200
    sprite[:, :, 3] = 255

    result = alpha_composite(background, sprite, 0, 0)

    assert (result == 200).all()


def test_alpha_composite_fully_transparent_sprite_leaves_background_unchanged():
    background = np.full((2, 2, 3), fill_value=100, dtype=np.uint8)
    sprite = np.zeros((2, 2, 4), dtype=np.uint8)
    sprite[:, :, 3] = 0

    result = alpha_composite(background, sprite, 0, 0)

    assert (result == 100).all()


def test_alpha_composite_blends_partial_alpha():
    background = np.full((1, 1, 3), fill_value=0, dtype=np.uint8)
    sprite = np.array([[[255, 255, 255, 128]]], dtype=np.uint8)

    result = alpha_composite(background, sprite, 0, 0)

    assert result[0, 0, 0] == pytest.approx(128, abs=2)


def test_alpha_composite_anchors_sprite_at_given_pixel_offset():
    background = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite = np.full((2, 2, 4), fill_value=255, dtype=np.uint8)

    result = alpha_composite(background, sprite, 2, 1)

    assert (result[1:3, 2:4] == 255).all()
    assert (result[0, :] == 0).all()
    assert (result[:, 0] == 0).all()


def test_alpha_composite_clips_sprite_extending_beyond_background_bounds():
    background = np.zeros((2, 2, 3), dtype=np.uint8)
    sprite = np.full((4, 4, 4), fill_value=255, dtype=np.uint8)

    result = alpha_composite(background, sprite, -1, -1)

    assert result.shape == (2, 2, 3)
    assert (result == 255).all()


def test_alpha_composite_sprite_entirely_outside_background_leaves_it_unchanged():
    background = np.full((2, 2, 3), fill_value=42, dtype=np.uint8)
    sprite = np.full((2, 2, 4), fill_value=255, dtype=np.uint8)

    result = alpha_composite(background, sprite, 10, 10)

    assert (result == 42).all()


# --- _imread_unicode_safe ---


def test_imread_unicode_safe_returns_none_for_a_missing_file(tmp_path):
    assert _imread_unicode_safe(str(tmp_path / "does_not_exist.png"), 0) is None


def test_imread_unicode_safe_returns_none_for_an_empty_file(tmp_path):
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")

    assert _imread_unicode_safe(str(empty_file), 0) is None


# --- SpriteCache ---


def test_sprite_cache_loads_and_caches_by_path():
    calls = []

    def fake_imread(path, flags):
        calls.append(path)
        return np.zeros((1, 1, 4), dtype=np.uint8)

    cache = SpriteCache(imread=fake_imread)
    first = cache.get("some/path.png")
    second = cache.get("some/path.png")

    assert first is second
    assert calls == ["some/path.png"]


def test_sprite_cache_raises_when_image_missing():
    cache = SpriteCache(imread=lambda path, flags: None)
    with pytest.raises(FileNotFoundError):
        cache.get("missing.png")


# --- OpenCvView ---


class RecordingSpriteCache:
    def __init__(self, sprite):
        self._sprite = sprite
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        return self._sprite


def make_view(board_config, sprite_state_mapping, sprite_cache, board_image, sprite_registry=None, flipped=False):
    return OpenCvView(
        board_config,
        sprite_state_mapping,
        assets_pieces_dir="assets/pieces",
        board_image_path="assets/board.png",
        sprite_cache=sprite_cache,
        sprite_registry=sprite_registry,
        board_image=board_image,
        flipped=flipped,
    )


def test_render_frame_returns_board_sized_canvas_for_empty_board():
    state, _ = make_game_state([[".", "."], [".", "."]])
    board_image = np.full((4, 4, 3), fill_value=50, dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.zeros((2, 2, 4), dtype=np.uint8))
    view = make_view(make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image)

    frame = view.render_frame(state)

    assert frame.shape == (4, 4, 3)
    assert sprite_cache.requested_paths == []
    assert (frame == 50).all()


def test_render_frame_composites_a_static_sprite_per_piece_at_its_cell():
    state, _ = make_game_state([["wP", "."], [".", "."]])
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite = np.full((2, 2, 4), fill_value=255, dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(sprite)
    view = make_view(make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image)

    frame = view.render_frame(state)

    expected_path = os.path.join("assets/pieces", "wP", "states", "idle", "sprites", "1.png")
    assert sprite_cache.requested_paths == [expected_path]
    assert (frame[0:2, 0:2] == 255).all()
    assert (frame[2:4, 2:4] == 0).all()


def test_render_frame_uses_the_pieces_current_state_folder():
    state, board = make_game_state([["bN", "."], [".", "."]])
    board.get(0, 0).state = PieceState.MOVING
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.zeros((2, 2, 4), dtype=np.uint8))
    view = make_view(make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image)

    view.render_frame(state)

    expected_path = os.path.join("assets/pieces", "bN", "states", "move", "sprites", "1.png")
    assert sprite_cache.requested_paths == [expected_path]


def test_render_frame_respects_configured_margin_offset():
    state, _ = make_game_state([["wK", "."], [".", "."]])
    board_image = np.zeros((6, 6, 3), dtype=np.uint8)
    sprite = np.full((2, 2, 4), fill_value=255, dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(sprite)
    view = make_view(
        make_board_config(cell_size_px=2, margin_left_px=1, margin_top_px=1),
        make_sprite_state_mapping(),
        sprite_cache,
        board_image,
    )

    frame = view.render_frame(state)

    assert (frame[1:3, 1:3] == 255).all()
    assert (frame[0, :] == 0).all()
    assert (frame[:, 0] == 0).all()


def test_render_frame_skips_a_state_with_no_mapped_folder():
    state, board = make_game_state([["wQ", "."], [".", "."]])
    board.get(0, 0).state = PieceState.CAPTURED
    board_image = np.full((4, 4, 3), fill_value=10, dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    view = make_view(make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image)

    frame = view.render_frame(state)

    assert sprite_cache.requested_paths == []
    assert (frame == 10).all()


def test_render_frame_does_not_mutate_the_cached_board_image():
    state, _ = make_game_state([["wP", "."], [".", "."]])
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    view = make_view(make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image)

    view.render_frame(state)

    assert (board_image == 0).all()


# --- animated rendering (now_ms/in_flight_leg) ---


class FakeSpriteRegistry:
    def __init__(self, sprite_sets):
        self._sprite_sets = sprite_sets  # {(color, kind, state_name): SpriteSet}
        self.requested = []

    def get(self, piece_color, piece_kind, state_name):
        self.requested.append((piece_color, piece_kind, state_name))
        return self._sprite_sets.get((piece_color, piece_kind, state_name))


def make_sprite_set(frame_paths, frames_per_sec=4, is_loop=True):
    return SpriteSet(frame_paths=tuple(frame_paths), frames_per_sec=frames_per_sec, is_loop=is_loop)


def test_render_frame_without_now_ms_never_touches_the_sprite_registry():
    """Regression guard for the deliberate split between
    _static_sprite_path and _animated_sprite_path (see module docstring):
    static rendering must stay fully independent of SpriteRegistry, even
    when one is injected.
    """
    state, _ = make_game_state([["wP", "."], [".", "."]])
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))

    class ExplodingRegistry:
        def get(self, *args, **kwargs):
            raise AssertionError("static rendering must never consult SpriteRegistry")

    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=ExplodingRegistry(),
    )

    frame = view.render_frame(state)  # now_ms omitted

    expected_path = os.path.join("assets/pieces", "wP", "states", "idle", "sprites", "1.png")
    assert sprite_cache.requested_paths == [expected_path]


def test_render_frame_with_now_ms_uses_animation_clock_to_pick_the_frame():
    state, _ = make_game_state([["wP", "."], [".", "."]])
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    sprite_set = make_sprite_set(["p0.png", "p1.png", "p2.png", "p3.png"], frames_per_sec=4, is_loop=True)
    registry = FakeSpriteRegistry({("w", "P", "IDLE"): sprite_set})
    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry,
    )

    view.render_frame(state, now_ms=250)  # elapsed 250ms at 4fps -> raw index int(0.25 * 4) = 1

    assert registry.requested == [("w", "P", "IDLE")]
    assert sprite_cache.requested_paths == ["p1.png"]


def test_render_frame_with_now_ms_skips_a_state_with_no_mapped_folder():
    state, board = make_game_state([["wQ", "."], [".", "."]])
    board.get(0, 0).state = PieceState.CAPTURED
    board_image = np.full((4, 4, 3), fill_value=10, dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    registry = FakeSpriteRegistry({})  # CAPTURED has no mapped folder - registry.get returns None
    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry,
    )

    frame = view.render_frame(state, now_ms=100)

    assert sprite_cache.requested_paths == []
    assert (frame == 10).all()


def test_render_frame_glides_a_moving_piece_between_its_leg_cells():
    state, board = make_game_state([["wP", ".", "."]])
    board.get(0, 0).state = PieceState.MOVING
    board_image = np.zeros((2, 6, 3), dtype=np.uint8)  # 1 row x 3 cols at cell_size_px=2
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    sprite_set = make_sprite_set(["p0.png"], frames_per_sec=1, is_loop=True)
    registry = FakeSpriteRegistry({("w", "P", "MOVING"): sprite_set})

    def in_flight_leg(piece):
        return (Position(0, 0), Position(0, 1), 0, 1000)

    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry,
    )

    frame = view.render_frame(state, now_ms=500, in_flight_leg=in_flight_leg)

    # progress 0.5 between pixel_position(0,0)=(0,0) and pixel_position(0,1)=(2,0) -> (1, 0)
    assert (frame[0:2, 1:3] == 255).all()
    assert (frame[0:2, 0:1] == 0).all()
    assert (frame[0:2, 3:6] == 0).all()


def test_render_frame_glides_correctly_when_flipped():
    """Regression test: the flipped-orientation branch of
    BoardRenderer.pixel_position() needs board_height/board_width, and
    the glide-interpolation call site in _piece_position_px previously
    never passed them through (only render()/_draw_selection() did) -
    this would raise a TypeError the instant a flipped (Black) client
    tried to render a gliding piece, live.
    """
    state, board = make_game_state([["wP", ".", "."]])
    board.get(0, 0).state = PieceState.MOVING
    board_image = np.zeros((2, 6, 3), dtype=np.uint8)  # 1 row x 3 cols at cell_size_px=2
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    sprite_set = make_sprite_set(["p0.png"], frames_per_sec=1, is_loop=True)
    registry = FakeSpriteRegistry({("w", "P", "MOVING"): sprite_set})

    def in_flight_leg(piece):
        return (Position(0, 0), Position(0, 1), 0, 1000)

    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry, flipped=True,
    )

    frame = view.render_frame(state, now_ms=500, in_flight_leg=in_flight_leg)  # must not raise

    # Mirrored relative to the unflipped case above: logical col 0 glides
    # toward the board's right edge, not its left.
    assert (frame[0:2, 3:5] == 255).all()
    assert (frame[0:2, 0:3] == 0).all()


def test_render_frame_keeps_static_cell_position_for_a_resting_piece_even_with_in_flight_leg_supplied():
    state, board = make_game_state([["wP", "."], [".", "."]])
    board.get(0, 0).state = PieceState.LONG_REST
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    sprite_set = make_sprite_set(["p0.png"], frames_per_sec=1, is_loop=True)
    registry = FakeSpriteRegistry({("w", "P", "LONG_REST"): sprite_set})

    def in_flight_leg(piece):
        return None  # a resting piece is never mid-leg

    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry,
    )

    frame = view.render_frame(state, now_ms=100, in_flight_leg=in_flight_leg)

    assert (frame[0:2, 0:2] == 255).all()  # drawn at its actual cell, not glided anywhere


def test_render_frame_animates_frame_selection_without_glide_when_in_flight_leg_is_not_supplied():
    state, board = make_game_state([["wP", "."], [".", "."]])
    board.get(0, 0).state = PieceState.MOVING
    board_image = np.zeros((4, 4, 3), dtype=np.uint8)
    sprite_cache = RecordingSpriteCache(np.full((2, 2, 4), fill_value=255, dtype=np.uint8))
    sprite_set = make_sprite_set(["p0.png"], frames_per_sec=1, is_loop=True)
    registry = FakeSpriteRegistry({("w", "P", "MOVING"): sprite_set})

    view = make_view(
        make_board_config(cell_size_px=2), make_sprite_state_mapping(), sprite_cache, board_image,
        sprite_registry=registry,
    )

    frame = view.render_frame(state, now_ms=100)  # in_flight_leg omitted -> defaults to None

    assert sprite_cache.requested_paths == ["p0.png"]  # animated frame selection still happened
    assert (frame[0:2, 0:2] == 255).all()  # but drawn at its static cell, not glided