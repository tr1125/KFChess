"""Drives the engine in real time instead of only on manual/test-only
wait() calls (see UI_PLAN.md Sec 4, Sec 10 item 5).

GameLoop only reaches the logic layer through Controller and GameState
snapshots (see UI_PLAN.md Sec 9's facade discipline) - it never imports
engine/model/rules internals directly.

tick() is the pure, testable core: it measures real elapsed time via
TimeSource, advances the engine by exactly that much, and renders one
frame. It never touches cv2, so it can be unit-tested without a window.

run() is the only place that touches cv2 - window creation, mouse
callback wiring, and the poll loop. poll_ms controls only how often the
window pumps events / checks for the quit key; it must never be used to
compute the engine's dt (that's the whole point of measuring real
elapsed time independently every frame instead of deriving it from
cv2.waitKey's own timing).

The window is resizable (cv2.WINDOW_NORMAL). Every frame is letterboxed
to the window's current size via aspect_ratio.compose_letterboxed() so
the board is never stretched out of its native ratio (see
aspect_ratio.py). Because we hand cv2.imshow a canvas that already
exactly matches the window's displayed size, cv2's own mouse callback
reports raw (x, y) in that canvas's pixel space with no further
window-stretch scaling involved (verified empirically for the
unletterboxed case: on this OpenCV build's Win32 GUI backend, cv2
already reports click coordinates relative to whatever image was last
shown, regardless of window size). What run() still has to do itself is
translate a canvas-space click back into the board's native pixel space
(subtracting the letterbox offset, undoing the fit-size scale) via
aspect_ratio.canvas_to_native() - a click that lands in a letterbox bar
translates to None and is dropped. BoardMapper/renderer.py/opencv_view.py
stay untouched and keep working in native board pixel space throughout.

Score/move-list side panels (UI_PLAN.md Sec 11.3) are an optional
addition, `panels=None` by default - when omitted, every behavior above
is byte-identical to before panels existed. When a PanelSet is supplied,
show() reserves fixed-ish-width regions on each side (driver/panel_layout.py)
before letterboxing the board into what's left, then concatenates
[left panel | letterboxed board | right panel] into the final canvas.
Panel content comes from observers/move_log_observer.py - a pure,
pull-based read of the current GameState, called once per render tick
from here, never from inside RuleEngine/GameEngine's settlement code, so
it cannot block or slow down move resolution (see UI_PLAN.md Sec 9's
Observer pattern entry). Per-panel scroll offsets live on GameLoop
itself (the same place click_state already lives) - move_log_observer
and SidePanelView stay pure/stateless, taking scroll_offset as an input
like they take panel data.

The promotion-choice menu (UI_PLAN.md Sec 7's deferred item, now built)
is the same kind of optional addition, `promotion_menu=None` by default,
byte-identical to before when omitted. Unlike the side panels, though,
there can be any number of them open at once (one per pending
promotion - see GameEngine.pending_promotions, which is deliberately a
list and never blocks play while non-empty), each floating over its own
board square rather than a fixed window region - so this doesn't reuse
panel_layout.py's fixed-region composition, it uses
driver/promotion_menu_layout.py's per-square placement instead. Which
menus are open is UI-owned interaction state (`_open_promotion_menus`,
alongside `_scroll_offsets`/click_state) keyed by the actual Piece
instance each menu belongs to - Piece is hashable by identity (see
model/piece.py), the same identity match `in_flight_leg` already uses,
rather than a synthetic key. Each tick: a menu closes once its piece is
no longer IDLE/LONG_REST (Controller.has_moved_since_promotion - a
model-type check, so it can't live here directly) or once the engine no
longer lists its square as pending; new pending entries not yet tracked
open a menu. A click resolves via the piece's *current* `.cell`, never a
coordinate captured when the menu opened, and the local menu always
closes on a click regardless of whether the engine call actually applied
- a stale no-op (see RuleEngine.apply_promotion_choice's own staleness
guard) is indistinguishable from success here, by design.

Once a piece has left IDLE/LONG_REST even once since it promoted, it's
recorded in `_dismissed_promotion_pieces` and can never reopen a menu
again - a live has_moved_since_promotion(piece) check alone isn't
enough, because nothing clears the engine's stale pending-promotion
entry just because the piece moved on (only a successful
choose_promotion does - see RuleEngine), and a settled move always ends
in LONG_REST, the exact same state a freshly-promoted piece is
in. Without this standing memory, a piece that moves again after
promoting would flicker its menu closed for one tick (while MOVING) and
then have it reopen the moment it next settles into LONG_REST, since
piece.state itself has no memory of ever having been MOVING in between -
only this set does.
"""

from dataclasses import dataclass

import cv2

from kungfu_chess.driver.aspect_ratio import canvas_to_native, compose_letterboxed
from kungfu_chess.driver.mouse_wheel import wheel_delta_from_flags
from kungfu_chess.driver.panel_layout import compose_with_panels, panel_regions
from kungfu_chess.driver.promotion_menu_layout import composite_menu, menu_origin
from kungfu_chess.observers.move_log_observer import clamp_scroll_offset, snapshot_for_color
from kungfu_chess.view.promotion_menu_view import PromotionMenuData, option_bounds, ordered_choices


@dataclass(frozen=True)
class PanelSet:
    """Everything GameLoop needs to render and scroll the two side
    panels. left_view/right_view are SidePanelView instances;
    left_color/right_color decide which player's data each side shows
    (arbitrary/cosmetic - see app_ui.py); panel_config supplies both
    panel_width_px (for panel_layout) and line_height_px (needed here
    too, so scroll-offset clamping agrees with what SidePanelView itself
    will render at that same height).
    """

    left_view: object
    right_view: object
    left_color: str
    right_color: str
    panel_config: object


@dataclass(frozen=True)
class PromotionMenuSet:
    """Everything GameLoop needs to position and render promotion-choice
    menus. `view` is a PromotionMenuView, `config` its matching
    PromotionMenuConfig (needed here too, for menu_size_px/option_bounds
    - the same per-icon geometry the view uses internally, reused for
    click hit-testing). `board_renderer` supplies pixel_position/
    cell_size_px so a menu can be placed over its piece's actual square
    - a second BoardRenderer instance, independent of whichever one the
    board view itself owns internally (BoardRenderer is stateless/pure,
    so instantiating it twice from the same board_config is harmless -
    see app_ui.py).
    """

    view: object
    config: object
    board_renderer: object


@dataclass(frozen=True)
class OpenPromotionMenu:
    color: str
    choices: tuple


class GameLoop:
    def __init__(self, controller, view, time_source, panels=None, promotion_menu=None):
        self._controller = controller
        self._view = view
        self._time_source = time_source
        self._panels = panels
        self._promotion_menu = promotion_menu
        self._last_tick_ms = None
        self._carry_ms = 0.0
        self._scroll_offsets = {"left": 0, "right": 0}
        self._open_promotion_menus = {}   # Piece -> OpenPromotionMenu, keyed by identity (see module docstring)
        self._dismissed_promotion_pieces = set()  # Piece - see _update_promotion_menus
        self._menu_click_regions = []     # rebuilt every render - see _render_promotion_menus/_handle_menu_click

    def tick(self):
        now = self._time_source.now_ms()
        if self._last_tick_ms is None:
            self._last_tick_ms = now
            self._update_promotion_menus()
            return self._render()

        elapsed = now - self._last_tick_ms + self._carry_ms
        dt_ms = int(elapsed)
        self._carry_ms = elapsed - dt_ms
        self._last_tick_ms = now

        if dt_ms > 0:
            self._controller.wait(dt_ms)

        self._update_promotion_menus()
        return self._render()

    def _update_promotion_menus(self):
        if self._promotion_menu is None:
            return

        # game_state() is the same raw GameState snapshot the view layer
        # already reads directly (see renderer.py's BoardRenderer.render) -
        # pending_promotions() here returns GameState's own
        # PendingPromotion dataclasses (.position/.color/.choices/.piece),
        # not GameEngine.pending_promotions()'s sanitized row/col dicts
        # (a different method, on a different object, that GameLoop never
        # touches - it only reaches the logic layer through Controller and
        # GameState, per this module's own docstring).
        pending = self._controller.game_state().pending_promotions()
        still_pending_pieces = {entry.piece for entry in pending}

        for piece in list(self._open_promotion_menus):
            if self._controller.has_moved_since_promotion(piece):
                del self._open_promotion_menus[piece]  # moved on - see Controller.has_moved_since_promotion
                self._dismissed_promotion_pieces.add(piece)
            elif piece not in still_pending_pieces:
                del self._open_promotion_menus[piece]  # resolved some other way (e.g. a stale-safe no-op)

        for entry in pending:
            piece = entry.piece
            if piece in self._open_promotion_menus or piece in self._dismissed_promotion_pieces:
                # _dismissed_promotion_pieces is why this can't just be a
                # fresh has_moved_since_promotion(piece) check here: once a
                # piece completes whatever move dismissed its menu, it
                # settles into LONG_REST again - the exact same state a
                # freshly-promoted piece is in - so a live state check
                # alone can no longer tell "still resting from the
                # promotion" apart from "resting again after a later,
                # unrelated move" (this is what actually broke - see the
                # investigation this fix is a response to). Only a
                # standing memory of "this piece already left IDLE/
                # LONG_REST once" - which piece.state itself doesn't keep -
                # can catch that the stale pending entry (nothing clears it
                # except a successful choose_promotion) has already been
                # dismissed once and must never reopen.
                continue
            if self._controller.has_moved_since_promotion(piece):
                # A same-tick IDLE -> MOVING transition can coincide with
                # a still-stale pending entry (nothing clears
                # pending_promotions() just because a piece moved on -
                # only a successful choose_promotion does) - without this
                # check a menu could flicker open for one tick before the
                # close-loop above ever gets a chance to catch it.
                self._dismissed_promotion_pieces.add(piece)
                continue
            self._open_promotion_menus[piece] = OpenPromotionMenu(entry.color, entry.choices)

    def _render(self):
        frame = self._view.render_frame(
            self._controller.game_state(),
            now_ms=self._controller.now(),
            in_flight_leg=self._controller.in_flight_leg,
            selected=self._controller.selected(),
        )
        if self._promotion_menu is not None:
            frame, self._menu_click_regions = self._render_promotion_menus(frame)
        else:
            self._menu_click_regions = []
        return frame

    def _render_promotion_menus(self, board_frame):
        promo = self._promotion_menu
        board_h, board_w = board_frame.shape[0], board_frame.shape[1]
        click_regions = []

        for piece, menu in self._open_promotion_menus.items():
            square_x, square_y = promo.board_renderer.pixel_position(piece.cell.row, piece.cell.col)
            menu_frame = promo.view.render_frame(PromotionMenuData(color=menu.color, choices=menu.choices))
            menu_h, menu_w = menu_frame.shape[0], menu_frame.shape[1]

            x_px, y_px = menu_origin(
                square_x, square_y, promo.board_renderer.cell_size_px, menu_w, menu_h, board_w, board_h
            )
            board_frame = composite_menu(board_frame, menu_frame, x_px, y_px)

            choices = ordered_choices(menu.choices, promo.config)
            bounds = option_bounds(len(choices), promo.config)
            click_regions.append(((x_px, y_px, x_px + menu_w, y_px + menu_h), bounds, choices, piece))

        return board_frame, click_regions

    def run(self, window_name, on_click=None, poll_ms=1, quit_keys=(ord("q"), 27)):
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        frame = self.tick()
        native_h, native_w = frame.shape[0], frame.shape[1]
        native_size = (native_w, native_h)

        if self._panels is not None:
            initial_w = native_w + 2 * self._panels.panel_config.panel_width_px
            initial_h = native_h
        else:
            initial_w, initial_h = native_w, native_h
        cv2.resizeWindow(window_name, initial_w, initial_h)

        click_state = {
            "content_size": native_size,
            "offset": (0, 0),
            "left_width": 0,
            "board_width": native_w,
            "window_h": native_h,
        }

        if on_click is not None:
            def _on_mouse(event, x, y, flags, userdata):
                if event == cv2.EVENT_LBUTTONDOWN:
                    self._handle_click(x, y, native_size, click_state, on_click)
                elif event == cv2.EVENT_MOUSEWHEEL and self._panels is not None:
                    self._handle_wheel(x, flags, click_state)

            cv2.setMouseCallback(window_name, _on_mouse)

        def show(frame):
            _, _, window_w, window_h = cv2.getWindowImageRect(window_name)

            if self._panels is not None:
                canvas = self._compose_panel_frame(frame, window_w, window_h, click_state)
            else:
                canvas, content_size, offset = compose_letterboxed(frame, (window_w, window_h))
                click_state["content_size"] = content_size
                click_state["offset"] = offset
                click_state["left_width"] = 0
                click_state["board_width"] = window_w
                click_state["window_h"] = window_h

            cv2.imshow(window_name, canvas)

        show(frame)
        while True:
            key = cv2.waitKey(poll_ms) & 0xFF
            if key in quit_keys:
                break
            show(self.tick())

        cv2.destroyAllWindows()

    def _handle_click(self, x, y, native_size, click_state, on_click):
        if self._panels is not None:
            left_width = click_state["left_width"]
            board_width = click_state["board_width"]
            if not (left_width <= x < left_width + board_width):
                return  # click landed on a panel - display-only, not interactive
            x -= left_width

        native_xy = canvas_to_native(x, y, native_size, click_state["content_size"], click_state["offset"])
        if native_xy is None:
            return
        if self._handle_menu_click(*native_xy):
            return  # consumed by an open promotion menu - never reaches on_click/board selection
        on_click(*native_xy)

    def _handle_menu_click(self, native_x, native_y):
        for (x0, y0, x1, y1), bounds, choices, piece in self._menu_click_regions:
            if not (x0 <= native_x < x1 and y0 <= native_y < y1):
                continue

            for piece_type, (opt_x0, opt_x1) in zip(choices, bounds):
                if x0 + opt_x0 <= native_x < x0 + opt_x1:
                    # Read the piece's *live* position, not any position
                    # captured when the menu opened - it may have moved
                    # since (see input/controller.py's has_moved_since_
                    # promotion and RuleEngine.apply_promotion_choice's
                    # own staleness guard, which makes this call safe
                    # even if it's a beat too late).
                    self._controller.choose_promotion(piece.cell.row, piece.cell.col, piece_type)
                    break

            self._open_promotion_menus.pop(piece, None)  # close regardless of whether it actually applied
            return True

        return False

    def _handle_wheel(self, x, flags, click_state):
        left_width = click_state["left_width"]
        board_width = click_state["board_width"]
        if x < left_width:
            side = "left"
            color = self._panels.left_color
        elif x >= left_width + board_width:
            side = "right"
            color = self._panels.right_color
        else:
            return  # wheel motion over the board - no-op

        game_state = self._controller.game_state()
        data = snapshot_for_color(game_state, color)
        viewport_lines = click_state["window_h"] // self._panels.panel_config.line_height_px

        delta = wheel_delta_from_flags(flags)
        new_offset = self._scroll_offsets[side] + delta
        self._scroll_offsets[side] = clamp_scroll_offset(new_offset, len(data.moves), viewport_lines)

    def _compose_panel_frame(self, board_frame, window_w, window_h, click_state):
        panels = self._panels
        game_state = self._controller.game_state()

        left_width, (board_width, _board_h), right_width = panel_regions(
            (window_w, window_h), panels.panel_config.panel_width_px
        )
        viewport_lines = window_h // panels.panel_config.line_height_px

        left_data = snapshot_for_color(game_state, panels.left_color)
        right_data = snapshot_for_color(game_state, panels.right_color)
        self._scroll_offsets["left"] = clamp_scroll_offset(
            self._scroll_offsets["left"], len(left_data.moves), viewport_lines
        )
        self._scroll_offsets["right"] = clamp_scroll_offset(
            self._scroll_offsets["right"], len(right_data.moves), viewport_lines
        )

        left_frame = panels.left_view.render_frame(
            left_data, window_h, self._scroll_offsets["left"], width_px=left_width
        )
        right_frame = panels.right_view.render_frame(
            right_data, window_h, self._scroll_offsets["right"], width_px=right_width
        )

        canvas, content_size, offset, left_width = compose_with_panels(
            board_frame, left_frame, right_frame, (window_w, window_h), panels.panel_config.panel_width_px
        )

        click_state["content_size"] = content_size
        click_state["offset"] = offset
        click_state["left_width"] = left_width
        click_state["board_width"] = board_width
        click_state["window_h"] = window_h

        return canvas