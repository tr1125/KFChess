"""Real-time move orchestration: click selection, shape-legal move
requests, jumps, and settling completed moves/jumps as the clock
advances.

Board only knows how to store tokens and apply a move. MovementRules
only knows whether a shape is legal. Selection state, which pieces are
currently in transit or airborne, and the decision of *when* to ask
MovementRules, live here - the one place responsible for turning user
input into board changes.
"""

from dataclasses import dataclass

from config.settings import CELL_SIZE_PX, MOVE_DURATION_PER_CELL_MS, JUMP_DURATION_MS
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
    mover_token: str  # captured at scheduling time - see _apply_if_still_valid


@dataclass
class _AirborneJump:
    row: int
    col: int
    token: str
    land_at_ms: int


class GameEngine:
    def __init__(self, board, clock, movement_rules):
        self._board = board
        self._clock = clock
        self._movement_rules = movement_rules
        self._selected = None  # (row, col) or None
        self._pending_moves = []
        self._airborne = []
        self._game_over = False

    def board(self):
        return self._board

    def is_game_over(self):
        return self._game_over

    def click(self, x_px, y_px):
        if self._game_over:
            return

        row, col = self._cell_at(x_px, y_px)
        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)

        if self._selected is None:
            # A piece already mid-route cannot be selected - this is what
            # makes redirecting an in-flight piece impossible. Once it
            # settles, its pending entry is removed and it becomes
            # selectable again immediately - no separate cooldown exists.
            if token != EMPTY_TOKEN and not self._has_pending_move_from(row, col):
                self._selected = (row, col)
            return

        selected_token = self._board.get(*self._selected)

        if token != EMPTY_TOKEN and color_of(token) == color_of(selected_token):
            if not self._has_pending_move_from(row, col):
                self._selected = (row, col)
            return

        self._try_request_move(self._selected, (row, col), selected_token)

    def jump(self, x_px, y_px):
        if self._game_over:
            return

        row, col = self._cell_at(x_px, y_px)
        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)
        if token == EMPTY_TOKEN:
            return
        if self._has_pending_move_from(row, col):
            return  # a moving piece cannot jump
        if self._is_airborne(row, col):
            return  # ASSUMPTION: already-airborne piece cannot re-jump; not stated explicitly

        land_at = self._clock.now() + JUMP_DURATION_MS
        self._airborne.append(_AirborneJump(row, col, token, land_at))

    def wait(self, ms):
        if self._game_over:
            return
        self._clock.advance(ms)
        self._settle_completed_moves()
        self._land_completed_jumps()

    @staticmethod
    def _cell_at(x_px, y_px):
        return y_px // CELL_SIZE_PX, x_px // CELL_SIZE_PX

    def _has_pending_move_from(self, row, col):
        return any(
            move.from_row == row and move.from_col == col for move in self._pending_moves
        )

    def _is_airborne(self, row, col):
        return any(jump.row == row and jump.col == col for jump in self._airborne)

    def _has_opposing_color_in_flight(self, mover_color):
        return any(color_of(move.mover_token) != mover_color for move in self._pending_moves)

    def _try_request_move(self, source, destination, selected_token):
        mover_color = color_of(selected_token)

        if self._has_opposing_color_in_flight(mover_color):
            # Opposite colors cannot move concurrently: while any piece of
            # the other color is still in transit, a new move cannot be
            # scheduled. Same-color pieces are unaffected.
            return

        is_legal = self._movement_rules.is_legal(
            selected_token, self._board, source[0], source[1], destination[0], destination[1]
        )
        if not is_legal:
            # ASSUMPTION: an illegal-shape click is a no-op for the whole
            # click, so the current selection is kept.
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
                continue  # cancelled - mover gone, friendly destination, or captured mid-air

            if self._game_over:
                self._pending_moves = []
                return

        self._pending_moves = still_pending

    def _land_completed_jumps(self):
        now = self._clock.now()
        self._airborne = [jump for jump in self._airborne if jump.land_at_ms > now]
        # No board change on landing - the piece was on this cell the
        # whole time. Simply falling out of self._airborne is "landing".

    def _apply_if_still_valid(self, move):
        # The piece that requested this move might no longer be at its
        # origin square (e.g. it was captured there by another move that
        # settled earlier in this same batch).
        current_token = self._board.get(move.from_row, move.from_col)
        if current_token != move.mover_token:
            return False  # the mover itself is gone - nothing to move

        target_token = self._board.get(move.to_row, move.to_col)

        if target_token != EMPTY_TOKEN and color_of(target_token) == color_of(move.mover_token):
            return False  # destination is friendly-occupied - cancel silently

        if target_token != EMPTY_TOKEN and self._is_airborne(move.to_row, move.to_col):
            # The defender is airborne and the arriver is an enemy (the
            # friendly case was already handled above): the airborne
            # piece captures the arriver instead of being captured. The
            # arriver is simply removed; the airborne piece is untouched.
            self._board.remove(move.from_row, move.from_col)
            return True

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