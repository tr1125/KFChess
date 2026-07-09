"""Real-time move orchestration: click selection, shape-legal move
requests, jumps, and settling completed moves/jumps as the clock
advances.

Board only knows how to store tokens and apply a move. MovementRules
only knows whether a shape is legal. MoveScheduler, JumpScheduler and
PromotionScheduler only know what's pending and what's due. MoveResolver
knows what settling a due move should *do* - captures, cancellations,
registering a pending promotion, game-over - and records each outcome
to MoveHistory as it happens. GameEngine is the one place that ties
selection state and all of these collaborators together into
click/jump/wait handling.

Promotion is user-driven, not automatic: once a move settles into a
pending promotion, click/jump/wait all become no-ops - the same way
they already do once is_game_over is true - until choose_promotion
supplies the piece to promote into. That is deliberately a whole-engine
pause rather than freezing just the one piece, so the state a caller
sees while a decision is outstanding is unambiguous.

The scheduler/resolver/history collaborators are constructed here by
default but accepted as optional constructor arguments, so a caller
(chiefly tests) can substitute a fake or a variant implementation
without reaching into GameEngine internals.
"""

from config.settings import CELL_SIZE_PX, MOVE_DURATION_PER_CELL_MS, JUMP_DURATION_MS
from domain.board import EMPTY_TOKEN
from domain.piece_token import color_of
from engine.move_scheduler import MoveScheduler
from engine.jump_scheduler import JumpScheduler
from engine.promotion_scheduler import PromotionScheduler
from engine.move_resolver import MoveResolver
from engine.move_history import MoveHistory
from engine.score_tracker import ScoreTracker


class GameEngine:
    def __init__(
        self,
        board,
        clock,
        movement_rules,
        moves=None,
        jumps=None,
        history=None,
        resolver=None,
        score_tracker=None,
        promotions=None,
        promotion_rules=None,
    ):
        self._board = board
        self._clock = clock
        self._movement_rules = movement_rules
        self._selected = None  # (row, col) or None
        self._moves = moves if moves is not None else MoveScheduler()
        self._jumps = jumps if jumps is not None else JumpScheduler()
        self._history = history if history is not None else MoveHistory()
        self._score_tracker = score_tracker if score_tracker is not None else ScoreTracker()
        self._promotions = promotions if promotions is not None else PromotionScheduler()
        self._resolver = (
            resolver
            if resolver is not None
            else MoveResolver(
                board,
                self._jumps,
                self._history,
                self._score_tracker,
                self._promotions,
                promotion_rules,
            )
        )
        self._game_over = False

    def board(self):
        return self._board

    def is_game_over(self):
        return self._game_over

    def move_history(self):
        """Settled moves so far, in algebraic notation, oldest first."""
        return self._history.entries()

    def scores(self):
        """Each color's cumulative score from captures so far, as {"w": int, "b": int}."""
        return self._score_tracker.scores()

    def pending_promotions(self):
        """Squares currently awaiting a promotion choice, as a list of
        {"row", "col", "color", "choices"} dicts. While this is non-empty
        the whole engine is paused - see choose_promotion.
        """
        return [
            {"row": p.row, "col": p.col, "color": p.color, "choices": p.choices}
            for p in self._promotions.pending()
        ]

    def choose_promotion(self, row, col, piece_type):
        """Resolve the pending promotion at (row, col) by turning the
        piece there into `piece_type` (e.g. "Q"). No-op if there's no
        pending promotion at that square, or piece_type isn't one of its
        configured choices - the engine stays paused until a valid
        choice is made.
        """
        if self._game_over:
            return

        pending = self._promotions.get(row, col)
        if pending is None or piece_type not in pending.choices:
            return

        self._promotions.take(row, col)
        promoted_token = pending.color + piece_type
        self._board.promote(row, col, promoted_token)
        self._history.record_promotion(self._board, promoted_token, row, col)

    def _is_paused(self):
        return self._game_over or self._promotions.has_any()

    def click(self, x_px, y_px):
        if self._is_paused():
            return

        row, col = self._cell_at(x_px, y_px)
        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)

        if self._selected is None:
            # A piece already mid-route cannot be selected - this is what
            # makes redirecting an in-flight piece impossible. Once it
            # settles, it becomes selectable again immediately - no
            # separate cooldown exists.
            if token != EMPTY_TOKEN and not self._moves.has_pending_from(row, col):
                self._selected = (row, col)
            return

        selected_token = self._board.get(*self._selected)

        if token != EMPTY_TOKEN and color_of(token) == color_of(selected_token):
            if not self._moves.has_pending_from(row, col):
                self._selected = (row, col)
            return

        self._try_request_move(self._selected, (row, col), selected_token)

    def jump(self, x_px, y_px):
        if self._is_paused():
            return

        row, col = self._cell_at(x_px, y_px)
        if not self._board.in_bounds(row, col):
            return

        token = self._board.get(row, col)
        if token == EMPTY_TOKEN:
            return
        if self._moves.has_pending_from(row, col):
            return  # a moving piece cannot jump
        if self._jumps.is_airborne(row, col):
            return  # ASSUMPTION: already-airborne piece cannot re-jump

        land_at = self._clock.now() + JUMP_DURATION_MS
        self._jumps.schedule(row, col, token, land_at)

    def wait(self, ms):
        if self._is_paused():
            return
        self._clock.advance(ms)
        self._settle_due_moves()
        self._jumps.land_due(self._clock.now())

    @staticmethod
    def _cell_at(x_px, y_px):
        return y_px // CELL_SIZE_PX, x_px // CELL_SIZE_PX

    def _try_request_move(self, source, destination, selected_token):
        mover_color = color_of(selected_token)

        if self._moves.has_opposing_color_in_flight(mover_color):
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
        self._moves.schedule(
            source[0], source[1], destination[0], destination[1], complete_at, selected_token
        )
        self._selected = None

    @staticmethod
    def _move_duration_ms(source, destination):
        row_distance = abs(destination[0] - source[0])
        col_distance = abs(destination[1] - source[1])
        distance = max(row_distance, col_distance)
        return distance * MOVE_DURATION_PER_CELL_MS

    def _settle_due_moves(self):
        for move in self._moves.take_due(self._clock.now()):
            if self._resolver.resolve(move):
                self._game_over = True
            if self._game_over:
                self._moves.clear()
                self._jumps.clear()
                return