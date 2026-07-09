"""Real-time move orchestration: click selection, shape-legal move
requests, and settling completed moves as the clock advances.

Board only knows how to store tokens and apply a move. MovementRules
only knows whether a shape is legal. Selection state, which pieces are
currently in transit, and the decision of *when* to ask MovementRules,
live here - the one place responsible for turning user input into
board changes.
"""

from dataclasses import dataclass

from config.settings import CELL_SIZE_PX, MOVE_DURATION_PER_CELL_MS
from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of, type_of

KING_TYPE = "K"
PAWN_TYPE = "P"
QUEEN_TYPE = "Q"


@dataclass
class _PendingMove:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    complete_at_ms: int
    mover_token: str  # captured at scheduling time - see _settle_completed_moves


class GameEngine:
    def __init__(self, board, clock, movement_rules):
        self._board = board
        self._clock = clock
        self._movement_rules = movement_rules
        self._selected = None  # (row, col) or None
        self._pending_moves = []
        self._game_over = False

    def board(self):
        return self._board

    def is_game_over(self):
        return self._game_over

    def click(self, x_px, y_px):
        if self._game_over:
            return

        col = x_px // CELL_SIZE_PX
        row = y_px // CELL_SIZE_PX

        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)

        if self._selected is None:
            # A piece already mid-route cannot be selected - this is what
            # makes redirecting an in-flight piece impossible. Once it
            # settles, _settle_completed_moves() removes its pending
            # entry and it becomes selectable again immediately - no
            # separate cooldown mechanism exists or is needed.
            if token != EMPTY_TOKEN and not self._has_pending_move_from(row, col):
                self._selected = (row, col)
            return

        selected_token = self._board.get(*self._selected)

        if token != EMPTY_TOKEN and color_of(token) == color_of(selected_token):
            if not self._has_pending_move_from(row, col):
                self._selected = (row, col)
            return

        self._try_request_move(self._selected, (row, col), selected_token)

    def wait(self, ms):
        if self._game_over:
            return
        self._clock.advance(ms)
        self._settle_completed_moves()

    def _has_pending_move_from(self, row, col):
        return any(
            move.from_row == row and move.from_col == col for move in self._pending_moves
        )

    def _has_opposing_color_in_flight(self, mover_color):
        # Read from the stored mover_token, not the board - the board at a
        # pending move's origin cell still shows the piece until it
        # settles, but the *pending move's own record* is the reliable
        # source of "whose move is this", independent of anything else
        # that might change on the board in the meantime.
        return any(color_of(move.mover_token) != mover_color for move in self._pending_moves)

    def _try_request_move(self, source, destination, selected_token):
        mover_color = color_of(selected_token)

        if self._has_opposing_color_in_flight(mover_color):
            # Opposite colors cannot move concurrently: while any piece of
            # the other color is still in transit, a new move cannot be
            # scheduled. Same-color pieces are unaffected and can still
            # move concurrently with each other.
            return

        is_legal = self._movement_rules.is_legal(
            selected_token, self._board, source[0], source[1], destination[0], destination[1]
        )
        if not is_legal:
            # ASSUMPTION: an illegal-shape click is treated as a no-op for
            # the whole click, so the current selection is kept - the user
            # gets to try a different destination.
            return

        complete_at = self._clock.now() + self._move_duration_ms(source, destination)
        self._pending_moves.append(
            _PendingMove(
                source[0], source[1], destination[0], destination[1], complete_at, selected_token
            )
        )
        self._selected = None

    @staticmethod
    def _move_duration_ms(source, destination):
        row_distance = abs(destination[0] - source[0])
        col_distance = abs(destination[1] - source[1])
        distance = max(row_distance, col_distance)
        return distance * MOVE_DURATION_PER_CELL_MS

    def _settle_completed_moves(self):
        now = self._clock.now()
        still_pending = []

        for move in self._pending_moves:
            if move.complete_at_ms > now:
                still_pending.append(move)
                continue

            if not self._apply_if_still_valid(move):
                continue  # cancelled - piece captured mid-flight, or destination now friendly

            if self._game_over:
                self._pending_moves = []
                return

        self._pending_moves = still_pending

    def _apply_if_still_valid(self, move):
        # The piece that requested this move might no longer be at its
        # origin square (e.g. it was captured there by another move that
        # settled earlier in this same batch). Re-reading the board here,
        # instead of trusting move.mover_token blindly, is what makes this
        # safe - board.apply_move() only moves whatever token is actually
        # present.
        current_token = self._board.get(move.from_row, move.from_col)
        if current_token != move.mover_token:
            return False  # the mover itself is gone - nothing to move

        target_token = self._board.get(move.to_row, move.to_col)
        if target_token != EMPTY_TOKEN and color_of(target_token) == color_of(move.mover_token):
            return False  # destination is now friendly-occupied - cancel silently

        self._board.apply_move(move.from_row, move.from_col, move.to_row, move.to_col)
        self._maybe_promote(move.mover_token, move.to_row, move.to_col)

        if target_token != EMPTY_TOKEN and type_of(target_token) == KING_TYPE:
            self._game_over = True

        return True

    def _maybe_promote(self, mover_token, to_row, to_col):
        """Promote a pawn that has reached the far rank to a queen."""
        if type_of(mover_token) != PAWN_TYPE:
            return
        color = color_of(mover_token)
        promotion_row = 0 if color == "w" else self._board.height - 1
        if to_row == promotion_row:
            self._board.promote(to_row, to_col, color + QUEEN_TYPE)