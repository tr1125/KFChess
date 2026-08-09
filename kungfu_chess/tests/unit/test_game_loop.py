import numpy as np

from kungfu_chess.config.panel_config import PanelConfig
from kungfu_chess.config.promotion_menu_config import PromotionMenuConfig
from kungfu_chess.driver.game_loop import GameLoop, OpenPromotionMenu, PanelSet, PromotionMenuSet
from kungfu_chess.model.game_state import PendingPromotion
from kungfu_chess.model.piece import Piece
from kungfu_chess.model.position import Position
from kungfu_chess.view.promotion_menu_view import PromotionMenuView
from kungfu_chess.view.renderer import BoardRenderer


class FakeTimeSource:
    def __init__(self, values):
        self._values = iter(values)

    def now_ms(self):
        return next(self._values)


class FakeController:
    def __init__(self, now_ms=42):
        self.wait_calls = []
        self._now_ms = now_ms

    def wait(self, ms):
        self.wait_calls.append(ms)

    def game_state(self):
        return "state"

    def now(self):
        return self._now_ms

    def in_flight_leg(self, piece):
        return None

    def selected(self):
        return None


class FakeView:
    def __init__(self):
        self.rendered_states = []
        self.render_calls = []  # (game_state, now_ms, in_flight_leg, selected)

    def render_frame(self, game_state, now_ms=None, in_flight_leg=None, selected=None):
        self.rendered_states.append(game_state)
        self.render_calls.append((game_state, now_ms, in_flight_leg, selected))
        return f"frame:{game_state}"


def test_first_tick_does_not_advance_the_engine():
    controller = FakeController()
    view = FakeView()
    loop = GameLoop(controller, view, FakeTimeSource([1000.0]))

    frame = loop.tick()

    assert controller.wait_calls == []
    assert frame == "frame:state"
    assert view.rendered_states == ["state"]


def test_tick_renders_with_the_controllers_current_now_and_in_flight_leg():
    controller = FakeController(now_ms=777)
    view = FakeView()
    loop = GameLoop(controller, view, FakeTimeSource([1000.0]))

    loop.tick()

    game_state, now_ms, in_flight_leg, _selected = view.render_calls[0]
    assert game_state == "state"
    assert now_ms == 777
    # Bound methods aren't singletons, so `is` never holds between two
    # separate attribute accesses - compare the underlying function and
    # instance instead to confirm it's genuinely controller.in_flight_leg,
    # not some other callable.
    assert in_flight_leg.__func__ is controller.in_flight_leg.__func__
    assert in_flight_leg.__self__ is controller


def test_second_tick_advances_by_elapsed_milliseconds():
    controller = FakeController()
    view = FakeView()
    loop = GameLoop(controller, view, FakeTimeSource([1000.0, 1250.0]))

    loop.tick()
    loop.tick()

    assert controller.wait_calls == [250]


def test_fractional_milliseconds_carry_across_ticks_without_drift():
    controller = FakeController()
    view = FakeView()
    # 16.6ms per tick, ten ticks after the seed tick: total elapsed 166.0ms.
    values = [0.0] + [16.6 * i for i in range(1, 11)]
    loop = GameLoop(controller, view, FakeTimeSource(values))

    loop.tick()  # seed, no wait call
    for _ in range(10):
        loop.tick()

    assert sum(controller.wait_calls) == 166


def test_zero_elapsed_time_does_not_call_wait():
    controller = FakeController()
    view = FakeView()
    loop = GameLoop(controller, view, FakeTimeSource([1000.0, 1000.0]))

    loop.tick()
    loop.tick()

    assert controller.wait_calls == []


class ArrayView:
    """Returns a real-shaped frame so run() can read native width/height,
    without needing an actual rendering pipeline."""

    def __init__(self, native_w, native_h):
        self._frame = np.zeros((native_h, native_w, 3), dtype=np.uint8)

    def render_frame(self, game_state, now_ms=None, in_flight_leg=None, selected=None):
        return self._frame


class FakeCv2:
    """Stands in for the cv2 module so run()'s window-wiring logic can be
    exercised without ever opening a real window - a live window itself is
    out of scope for unit tests, per the same manual-verification
    convention as the rest of driver/.

    getWindowImageRect() defaults to reporting whatever resizeWindow() was
    last called with (i.e. no letterbox bars, matching the native size run()
    resizes to at startup) unless window_image_rect is passed explicitly to
    simulate the user having resized to some other shape."""

    WINDOW_NORMAL = "WINDOW_NORMAL"
    EVENT_LBUTTONDOWN = "EVENT_LBUTTONDOWN"
    EVENT_MOUSEWHEEL = "EVENT_MOUSEWHEEL"

    def __init__(self, quit_key, window_image_rect=None):
        self.quit_key = quit_key
        self.mouse_callback = None
        self.resized_to = None
        self._window_image_rect_override = window_image_rect

    def namedWindow(self, name, flag):
        pass

    def resizeWindow(self, name, w, h):
        self.resized_to = (w, h)

    def setMouseCallback(self, name, callback):
        self.mouse_callback = callback

    def getWindowImageRect(self, name):
        if self._window_image_rect_override is not None:
            return self._window_image_rect_override
        w, h = self.resized_to
        return (0, 0, w, h)

    def imshow(self, name, frame):
        pass

    def waitKey(self, ms):
        return self.quit_key

    def destroyAllWindows(self):
        pass


def test_run_resizes_window_to_the_frames_native_size(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win")

    assert fake_cv2.resized_to == (200, 100)


def test_run_passes_clicks_through_unchanged_when_window_matches_native_size(monkeypatch):
    # No letterbox bars when the displayed size already matches native, so
    # the translation is an identity mapping.
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 100, 50, 0, None)

    assert recorded_clicks == [(100, 50)]


def test_run_translates_clicks_through_the_letterbox_offset_and_scale(monkeypatch):
    # native 200x100 (2:1) into an available 400x100 window: width is the
    # binding constraint, so the fit content stays 200x100 pillarboxed by
    # 100px bars on each side.
    fake_cv2 = FakeCv2(quit_key=ord("q"), window_image_rect=(0, 0, 400, 100))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # Canvas-space click at (150, 50) is 50px into the content area (which
    # starts at x=100) - should translate to native (50, 50).
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 150, 50, 0, None)

    assert recorded_clicks == [(50, 50)]


def test_run_drops_clicks_that_land_in_a_letterbox_bar(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"), window_image_rect=(0, 0, 400, 100))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # x=50 is inside the left letterbox bar (content starts at x=100).
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 50, 50, 0, None)

    assert recorded_clicks == []


def test_run_ignores_non_click_mouse_events(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    fake_cv2.mouse_callback("EVENT_MOUSEMOVE", 100, 50, 0, None)

    assert recorded_clicks == []


# --- panels (UI_PLAN.md Sec 11.3) ---


class FakePanelGameState:
    def __init__(self, scores, moves):
        self._scores = scores
        self._moves = moves  # dict: color -> list[str]

    def scores(self):
        return dict(self._scores)

    def moves_for_color(self, color):
        return list(self._moves.get(color, []))


class FakePanelController:
    def __init__(self, game_state):
        self._game_state = game_state
        self.wait_calls = []

    def wait(self, ms):
        self.wait_calls.append(ms)

    def game_state(self):
        return self._game_state

    def now(self):
        return 0

    def in_flight_leg(self, piece):
        return None

    def selected(self):
        return None


class FakePanelView:
    def __init__(self):
        self.calls = []  # (panel_data, height_px, scroll_offset, width_px)

    def render_frame(self, panel_data, height_px, scroll_offset=0, width_px=None):
        self.calls.append((panel_data, height_px, scroll_offset, width_px))
        width = width_px if width_px is not None else 1
        return np.zeros((height_px, width, 3), dtype=np.uint8)


def make_panel_config(panel_width_px=50, line_height_px=10):
    return PanelConfig(
        panel_width_px=panel_width_px,
        line_height_px=line_height_px,
        font_scale=0.5,
        font_thickness=1,
        text_color=(255, 255, 255),
        background_color=(0, 0, 0),
        padding_px=5,
        labels={"w": "White", "b": "Black"},
    )


def wheel_flags(raw_delta):
    return (raw_delta & 0xFFFF) << 16


def make_panel_loop(
    fake_cv2, moves=None, panel_width_px=50, line_height_px=10, native_w=200, native_h=100, ratings=None
):
    game_state = FakePanelGameState(
        scores={"w": 0, "b": 0}, moves=moves or {"w": [], "b": []}
    )
    controller = FakePanelController(game_state)
    left_view = FakePanelView()
    right_view = FakePanelView()
    panels = PanelSet(
        left_view=left_view,
        right_view=right_view,
        left_color="w",
        right_color="b",
        panel_config=make_panel_config(panel_width_px, line_height_px),
        ratings=ratings,
    )
    loop = GameLoop(controller, ArrayView(native_w=native_w, native_h=native_h), FakeTimeSource([0.0]), panels=panels)
    return loop, left_view, right_view


def test_run_widens_startup_window_by_both_panel_widths_when_panels_configured(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop, _left, _right = make_panel_loop(fake_cv2, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win")

    assert fake_cv2.resized_to == (200 + 2 * 50, 100)


def test_run_renders_each_panel_with_its_assigned_colors_data_and_computed_width(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    moves = {"w": ["e4", "Nf3"], "b": ["d5"]}
    loop, left_view, right_view = make_panel_loop(fake_cv2, moves=moves, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win")

    assert len(left_view.calls) == 1
    left_data, left_height, left_scroll, left_width = left_view.calls[0]
    assert left_data.color == "w"
    assert left_data.moves == ["e4", "Nf3"]
    assert left_height == 100
    assert left_scroll == 0
    assert left_width == 50

    right_data, _height, _scroll, right_width = right_view.calls[0]
    assert right_data.color == "b"
    assert right_data.moves == ["d5"]
    assert right_width == 50


def test_run_passes_each_side_its_own_rating_when_ratings_are_configured(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop, left_view, right_view = make_panel_loop(
        fake_cv2, ratings={"w": 1350, "b": 1200}, native_w=200, native_h=100
    )
    loop.run("win")

    left_data, _height, _scroll, _width = left_view.calls[0]
    right_data, _height, _scroll, _width = right_view.calls[0]
    assert left_data.rating == 1350
    assert right_data.rating == 1200


def test_run_leaves_rating_none_when_ratings_are_not_configured(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop, left_view, _right = make_panel_loop(fake_cv2, native_w=200, native_h=100)
    loop.run("win")

    left_data, _height, _scroll, _width = left_view.calls[0]
    assert left_data.rating is None


def test_run_drops_clicks_landing_on_the_left_panel(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, _left, _right = make_panel_loop(fake_cv2, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # Window is exactly native_w + 2*panel_width_px = 300 wide, so the left
    # panel spans canvas x in [0, 50).
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 20, 50, 0, None)

    assert recorded_clicks == []


def test_run_drops_clicks_landing_on_the_right_panel(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, _left, _right = make_panel_loop(fake_cv2, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # Right panel spans canvas x in [250, 300).
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 280, 50, 0, None)

    assert recorded_clicks == []


def test_run_board_clicks_still_translate_correctly_when_panels_configured(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, _left, _right = make_panel_loop(fake_cv2, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # Board region spans canvas x in [50, 250) with no letterbox bars (native
    # 200x100 fits board_available (200,100) exactly). A click at canvas
    # x=150 is board-local x=100, which maps 1:1 to native x=100.
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, 150, 50, 0, None)

    assert recorded_clicks == [(100, 50)]


def test_run_mouse_wheel_on_left_panel_increments_only_that_panels_scroll_offset(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    moves = {"w": [f"m{i}" for i in range(20)], "b": [f"m{i}" for i in range(20)]}
    loop, _left, _right = make_panel_loop(
        fake_cv2, moves=moves, panel_width_px=50, line_height_px=10, native_w=200, native_h=100
    )
    loop.run("win", on_click=lambda x, y: None)

    fake_cv2.mouse_callback(fake_cv2.EVENT_MOUSEWHEEL, 20, 50, wheel_flags(120), None)

    # Scroll state lives on GameLoop itself (see PanelSet's docstring) -
    # there is no other externally-observable hook for it, so this reaches
    # into that documented internal state directly.
    assert loop._scroll_offsets["left"] == 1
    assert loop._scroll_offsets["right"] == 0


def test_run_mouse_wheel_scroll_down_does_not_go_below_zero(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    moves = {"w": [f"m{i}" for i in range(20)], "b": []}
    loop, _left, _right = make_panel_loop(fake_cv2, moves=moves, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win", on_click=lambda x, y: None)

    fake_cv2.mouse_callback(fake_cv2.EVENT_MOUSEWHEEL, 20, 50, wheel_flags(-120), None)

    assert loop._scroll_offsets["left"] == 0


def test_run_mouse_wheel_over_the_board_is_a_no_op(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    moves = {"w": [f"m{i}" for i in range(20)], "b": [f"m{i}" for i in range(20)]}
    loop, _left, _right = make_panel_loop(fake_cv2, moves=moves, panel_width_px=50, native_w=200, native_h=100)
    loop.run("win", on_click=lambda x, y: None)

    fake_cv2.mouse_callback(fake_cv2.EVENT_MOUSEWHEEL, 150, 50, wheel_flags(120), None)

    assert loop._scroll_offsets == {"left": 0, "right": 0}


def test_run_mouse_wheel_is_a_no_op_when_panels_not_configured(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop = GameLoop(FakeController(), ArrayView(native_w=200, native_h=100), FakeTimeSource([0.0]))
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    # Should not raise even though there is no panel configuration at all.
    fake_cv2.mouse_callback(fake_cv2.EVENT_MOUSEWHEEL, 20, 50, wheel_flags(120), None)

    assert recorded_clicks == []


# --- promotion menu ---


class FakePromotionGameState:
    """`pending` is a list of real PendingPromotion instances (see
    model/game_state.py) - GameLoop reads game_state.pending_promotions()
    directly, the same raw GameState snapshot the view layer already
    reads (see renderer.py), which is a different method/shape than
    GameEngine.pending_promotions()'s sanitized row/col dicts."""

    def __init__(self, pending):
        self._pending = pending

    def pending_promotions(self):
        return list(self._pending)

    def board_height(self):
        # Unused by pixel_position() unless the BoardRenderer is flipped
        # (not the case in these tests) - present only to satisfy the
        # game_state interface GameLoop now calls unconditionally.
        return 0

    def board_width(self):
        return 0


def pending_promotion_for(piece, color=None, choices=("Q", "R", "B", "N")):
    return PendingPromotion(
        position=piece.cell, color=color if color is not None else piece.color, choices=choices, piece=piece
    )


class FakePromotionController:
    def __init__(self, game_state, moved_pieces=None):
        self._game_state = game_state
        self._moved_pieces = moved_pieces if moved_pieces is not None else set()
        self.wait_calls = []
        self.choose_promotion_calls = []

    def wait(self, ms):
        self.wait_calls.append(ms)

    def game_state(self):
        return self._game_state

    def now(self):
        return 0

    def in_flight_leg(self, piece):
        return None

    def selected(self):
        return None

    def has_moved_since_promotion(self, piece):
        return piece in self._moved_pieces

    def choose_promotion(self, row, col, piece_type):
        self.choose_promotion_calls.append((row, col, piece_type))


def make_promotion_menu_set(icon_size_px=10, spacing_px=2, padding_px=3, cell_size_px=20):
    config = PromotionMenuConfig(
        icon_size_px=icon_size_px,
        spacing_px=spacing_px,
        padding_px=padding_px,
        background_color=(20, 20, 20),
        border_color=(255, 255, 255),
        border_thickness=1,
        text_color=(255, 255, 255),
        font_scale=0.5,
        font_thickness=1,
        choice_order=("Q", "R", "B", "N"),
    )
    return PromotionMenuSet(
        view=PromotionMenuView(config),
        config=config,
        board_renderer=BoardRenderer(cell_size_px=cell_size_px),
    )


# --- lifecycle: _update_promotion_menus ---


def test_tick_opens_a_menu_for_a_newly_pending_promotion():
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state)
    loop = GameLoop(controller, ArrayView(100, 100), FakeTimeSource([0.0]), promotion_menu=make_promotion_menu_set())

    loop.tick()

    assert list(loop._open_promotion_menus.keys()) == [piece]
    assert loop._open_promotion_menus[piece] == OpenPromotionMenu("w", ("Q", "R", "B", "N"))


def test_tick_does_not_replace_an_already_tracked_menu():
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state)
    loop = GameLoop(
        controller, ArrayView(100, 100), FakeTimeSource([0.0, 1.0]), promotion_menu=make_promotion_menu_set()
    )

    loop.tick()
    tracked_menu = loop._open_promotion_menus[piece]
    loop.tick()

    assert loop._open_promotion_menus[piece] is tracked_menu  # same object, not replaced


def test_tick_does_not_open_a_menu_for_a_piece_that_has_already_moved_on():
    # A same-tick IDLE -> MOVING transition can coincide with a still-stale
    # pending entry (nothing clears pending_promotions() just because a
    # piece moved on - only a successful choose_promotion does).
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state, moved_pieces={piece})
    loop = GameLoop(controller, ArrayView(100, 100), FakeTimeSource([0.0]), promotion_menu=make_promotion_menu_set())

    loop.tick()

    assert loop._open_promotion_menus == {}


def test_tick_closes_the_menu_once_the_piece_has_moved():
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state)
    loop = GameLoop(controller, ArrayView(100, 100), FakeTimeSource([0.0, 1.0]), promotion_menu=make_promotion_menu_set())

    loop.tick()
    assert piece in loop._open_promotion_menus
    controller._moved_pieces.add(piece)  # simulate the piece moving on between ticks
    loop.tick()

    assert loop._open_promotion_menus == {}


def test_tick_never_reopens_a_menu_once_the_piece_has_settled_from_a_later_move():
    # Regression: a settled move always ends in LONG_REST - the exact
    # same state a freshly-promoted piece is in. Once the piece stops
    # being reported as "moved" (it's resting again from the new move),
    # the original stale pending entry (nothing clears it except a
    # successful choose_promotion) must not be allowed to reopen the
    # menu a second time.
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state)
    loop = GameLoop(
        controller, ArrayView(100, 100), FakeTimeSource([0.0, 1.0, 2.0]), promotion_menu=make_promotion_menu_set()
    )

    loop.tick()
    assert piece in loop._open_promotion_menus

    controller._moved_pieces.add(piece)  # the piece starts moving
    loop.tick()
    assert loop._open_promotion_menus == {}

    controller._moved_pieces.discard(piece)  # the move settles - LONG_REST again, same as right after promoting
    loop.tick()

    assert loop._open_promotion_menus == {}  # must stay closed, not reopen
    assert piece in loop._dismissed_promotion_pieces


def test_tick_closes_the_menu_once_the_engine_no_longer_lists_it_pending():
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState(pending=[])
    controller = FakePromotionController(game_state)
    loop = GameLoop(controller, ArrayView(100, 100), FakeTimeSource([0.0]), promotion_menu=make_promotion_menu_set())
    loop._open_promotion_menus[piece] = OpenPromotionMenu("w", ("Q", "R", "B", "N"))

    loop.tick()

    assert loop._open_promotion_menus == {}


def test_promotion_menu_lifecycle_is_a_no_op_when_not_configured():
    # Plain FakeController has no pending_promotions/board_rows/
    # has_moved_since_promotion at all - proves _update_promotion_menus
    # never even touches game_state when promotion_menu is omitted (the
    # same "byte-identical when absent" contract panels=None already has).
    controller = FakeController()
    loop = GameLoop(controller, FakeView(), FakeTimeSource([1000.0]))

    loop.tick()  # must not raise

    assert loop._open_promotion_menus == {}


def test_two_simultaneously_pending_promotions_both_open_their_own_menu():
    piece_a = Piece(color="w", kind="Q", cell=Position(0, 0))
    piece_b = Piece(color="b", kind="Q", cell=Position(3, 3))
    game_state = FakePromotionGameState([pending_promotion_for(piece_a), pending_promotion_for(piece_b)])
    controller = FakePromotionController(game_state)
    loop = GameLoop(controller, ArrayView(200, 200), FakeTimeSource([0.0]), promotion_menu=make_promotion_menu_set())

    loop.tick()

    assert set(loop._open_promotion_menus.keys()) == {piece_a, piece_b}


# --- rendering + click routing (via run()) ---


def make_promotion_loop(fake_cv2, native_w=100, native_h=100, cell_size_px=20, moved_pieces=None):
    piece = Piece(color="w", kind="Q", cell=Position(1, 1))
    game_state = FakePromotionGameState([pending_promotion_for(piece)])
    controller = FakePromotionController(game_state, moved_pieces=moved_pieces)
    loop = GameLoop(
        controller, ArrayView(native_w=native_w, native_h=native_h), FakeTimeSource([0.0]),
        promotion_menu=make_promotion_menu_set(cell_size_px=cell_size_px),
    )
    return loop, controller, piece


def test_run_renders_menu_click_regions_covering_the_promoted_square(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop, _controller, _piece = make_promotion_loop(fake_cv2)
    loop.run("win")

    assert len(loop._menu_click_regions) == 1
    (x0, y0, x1, y1), bounds, choices, _piece_ref = loop._menu_click_regions[0]
    assert choices == ["Q", "R", "B", "N"]
    assert x0 < x1 and y0 < y1
    assert len(bounds) == 4


def test_run_click_on_a_menu_option_calls_choose_promotion_and_closes_the_menu(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, controller, piece = make_promotion_loop(fake_cv2)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    (x0, y0, _x1, _y1), bounds, _choices, _piece_ref = loop._menu_click_regions[0]
    opt_x0, _opt_x1 = bounds[0]  # "Q" slot
    click_x, click_y = x0 + opt_x0 + 1, y0 + 1

    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, click_x, click_y, 0, None)

    assert controller.choose_promotion_calls == [(1, 1, "Q")]
    assert piece not in loop._open_promotion_menus
    assert recorded_clicks == []  # consumed by the menu - never reached board click handling


def test_run_click_on_a_menu_option_uses_the_pieces_live_cell_not_a_captured_one(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    loop, controller, piece = make_promotion_loop(fake_cv2)
    loop.run("win", on_click=lambda x, y: None)

    (x0, y0, _x1, _y1), bounds, _choices, _piece_ref = loop._menu_click_regions[0]
    opt_x0, _opt_x1 = bounds[0]  # "Q" slot, still at the menu's original screen position
    click_x, click_y = x0 + opt_x0 + 1, y0 + 1

    piece.cell = Position(2, 2)  # the piece's board position changed since the menu opened

    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, click_x, click_y, 0, None)

    assert controller.choose_promotion_calls == [(2, 2, "Q")]  # live cell, not the stale (1, 1)


def test_run_click_inside_menu_but_not_on_an_option_is_swallowed_without_a_choice(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, controller, piece = make_promotion_loop(fake_cv2)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    (x0, y0, x1, _y1), _bounds, _choices, _piece_ref = loop._menu_click_regions[0]
    click_x, click_y = x1 - 1, y0 + 1  # inside the outer bounds, in the trailing padding past the last option

    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, click_x, click_y, 0, None)

    assert controller.choose_promotion_calls == []
    assert piece not in loop._open_promotion_menus  # still closes - see module docstring
    assert recorded_clicks == []


def test_run_click_outside_the_menu_reaches_the_board_as_normal(monkeypatch):
    fake_cv2 = FakeCv2(quit_key=ord("q"))
    monkeypatch.setattr("kungfu_chess.driver.game_loop.cv2", fake_cv2)

    recorded_clicks = []
    loop, controller, piece = make_promotion_loop(fake_cv2)
    loop.run("win", on_click=lambda x, y: recorded_clicks.append((x, y)))

    (_x0, _y0, x1, _y1), _bounds, _choices, _piece_ref = loop._menu_click_regions[0]
    fake_cv2.mouse_callback(fake_cv2.EVENT_LBUTTONDOWN, x1 + 10, 90, 0, None)

    assert controller.choose_promotion_calls == []
    assert piece in loop._open_promotion_menus  # untouched
    assert recorded_clicks == [(x1 + 10, 90)]