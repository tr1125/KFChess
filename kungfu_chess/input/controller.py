"""Translates raw UI input (pixel clicks/jumps, wait durations, promotion
choices) into GameEngine calls via BoardMapper. The only door from input
events into the engine - GameEngine itself never sees a pixel, and owns
no click-selection state (see UI_PLAN.md Sec 3): "currently selected
piece" lives here, as Controller is the natural place for it to sit
alongside per-player identity (PlayerSession).

As the facade boundary itself, Controller is allowed to import model
types (PieceState) to inspect board contents when deciding what a click
means - the other input/view/driver modules must not; they may only
reach the logic layer through Controller and GameState snapshots.
"""

from kungfu_chess.model.piece import PieceState
from kungfu_chess.input.player_session import PlayerSession


class Controller:
    def __init__(self, engine, board_mapper, player_session=None):
        self._engine = engine
        self._board_mapper = board_mapper
        self._player_session = player_session if player_session is not None else PlayerSession()
        self._selected = None  # Position or None - UI-owned, see module docstring

    def click(self, x_px, y_px):
        position = self._board_mapper.cell_at(x_px, y_px)
        piece = self._piece_at(position)

        if self._selected is None:
            self._handle_first_click(position, piece)
            return

        if position == self._selected:
            # Same square clicked twice - in-place jump.
            self._engine.jump(position.row, position.col)
            self._selected = None
            return

        if piece is not None and piece.color == self._selected_piece().color and piece.state == PieceState.IDLE:
            # A different piece of our own color - switch selection, no move attempted.
            self._selected = position
            return

        # Anything else (empty, opponent, or a busy friendly piece) is an
        # attempted move. Controller doesn't need to know whether it was
        # legal: either it gets scheduled (and the piece is no longer
        # ours to keep selected), or it's rejected outright - both cases
        # end with the current selection cleared.
        self._engine.request_move(self._selected.row, self._selected.col, position.row, position.col)
        self._selected = None

    def _handle_first_click(self, position, piece):
        if piece is None or piece.state != PieceState.IDLE:
            return  # empty square, opponent's piece, or a busy piece - no selection
        self._player_session.claim(piece.color)
        self._selected = position

    def _selected_piece(self):
        return self._piece_at(self._selected)

    def _piece_at(self, position):
        state = self._engine.game_state()
        if not (0 <= position.row < state.board_height() and 0 <= position.col < state.board_width()):
            return None  # click landed outside the board (e.g. in a margin)
        return state.board_rows()[position.row][position.col]

    def jump(self, x_px, y_px):
        position = self._board_mapper.cell_at(x_px, y_px)
        self._engine.jump(position.row, position.col)

    def wait(self, ms):
        self._engine.wait(ms)

    def choose_promotion(self, row, col, piece_type):
        self._engine.choose_promotion(row, col, piece_type)

    def has_moved_since_promotion(self, piece):
        """Whether `piece` has left the settled state a still-open
        promotion choice requires (IDLE, or LONG_REST from the move that
        triggered the promotion) - i.e. it's now MOVING or AIRBORNE. The
        UI-facing trigger to hide that piece's promotion menu (see
        UI_PLAN.md's promotion-menu design) - PieceState is a model type,
        so this check lives here rather than in driver/view code (see
        module docstring)."""
        return piece.state not in (PieceState.IDLE, PieceState.LONG_REST)

    def game_state(self):
        return self._engine.game_state()

    def now(self):
        return self._engine.now()

    def in_flight_leg(self, piece):
        return self._engine.in_flight_leg(piece)