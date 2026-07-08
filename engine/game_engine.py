"""Real-time move orchestration: click selection, move requests, and
settling completed moves as the clock advances.

Board only knows how to store tokens and apply a move - it has no idea
what "selected" or "pending" mean. That state lives here, in the one
place responsible for turning user input into board changes.
"""

from dataclasses import dataclass

from config.settings import CELL_SIZE_PX, MOVE_DURATION_MS
from domain.board import EMPTY_TOKEN


@dataclass
class _PendingMove:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    complete_at_ms: int


def _same_color(token_a, token_b):
    return token_a[0] == token_b[0]


class GameEngine:
    def __init__(self, board, clock):
        self._board = board
        self._clock = clock
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
        if token != EMPTY_TOKEN and _same_color(token, selected_token):
            self._selected = (row, col)
            return

        self._request_move(self._selected, (row, col))
        self._selected = None

    def wait(self, ms):
        self._clock.advance(ms)
        self._settle_completed_moves()

    def _request_move(self, source, destination):
        complete_at = self._clock.now() + MOVE_DURATION_MS
        self._pending_moves.append(
            _PendingMove(source[0], source[1], destination[0], destination[1], complete_at)
        )

    def _settle_completed_moves(self):
        now = self._clock.now()
        still_pending = []
        for move in self._pending_moves:
            if move.complete_at_ms <= now:
                self._board.apply_move(move.from_row, move.from_col, move.to_row, move.to_col)
            else:
                still_pending.append(move)
        self._pending_moves = still_pending