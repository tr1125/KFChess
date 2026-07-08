"""Real-time move orchestration: click selection, shape-legal move
requests, and settling completed moves as the clock advances.

Board only knows how to store tokens and apply a move. MovementRules
only knows whether a shape is legal. Selection state, and the decision
of *when* to ask MovementRules, live here - the one place responsible
for turning user input into board changes.
"""

from dataclasses import dataclass

from config.settings import CELL_SIZE_PX, MOVE_DURATION_MS
from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of, type_of


@dataclass
class _PendingMove:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    complete_at_ms: int


class GameEngine:
    def __init__(self, board, clock, movement_rules):
        self._board = board
        self._clock = clock
        self._movement_rules = movement_rules
        self._selected = None  # (row, col) or None
        self._pending_moves = []

    def board(self):
        return self._board

    def click(self, x_px, y_px):
        col = x_px // CELL_SIZE_PX
        row = y_px // CELL_SIZE_PX

        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)

        if self._selected is None:
            if token != EMPTY_TOKEN:
                self._selected = (row, col)
            return

        selected_token = self._board.get(*self._selected)

        if token != EMPTY_TOKEN and color_of(token) == color_of(selected_token):
            self._selected = (row, col)
            return

        self._try_request_move(self._selected, (row, col), selected_token)

    def wait(self, ms):
        self._clock.advance(ms)
        self._settle_completed_moves()

    def _try_request_move(self, source, destination, selected_token):
        piece_type = type_of(selected_token)
        is_legal = self._movement_rules.is_legal(
            piece_type, self._board, source[0], source[1], destination[0], destination[1]
        )
        if not is_legal:
            # ASSUMPTION: an illegal-shape click is treated as a no-op for
            # the whole click, so the current selection is kept - the user
            # gets to try a different destination. Not covered by this
            # iteration's spec text; revisit if a test says otherwise.
            return

        complete_at = self._clock.now() + MOVE_DURATION_MS
        self._pending_moves.append(
            _PendingMove(source[0], source[1], destination[0], destination[1], complete_at)
        )
        self._selected = None

    def _settle_completed_moves(self):
        now = self._clock.now()
        still_pending = []
        for move in self._pending_moves:
            if move.complete_at_ms <= now:
                self._board.apply_move(move.from_row, move.from_col, move.to_row, move.to_col)
            else:
                still_pending.append(move)
        self._pending_moves = still_pending