"""Ties board, real-time motion, the arbiter, and the rule engine
together into click/jump/wait/choose_promotion handling.

Board only knows how to store pieces and apply a move. RuleEngine only
knows whether a shape is legal and what settling a move should *do*.
MotionTracker only knows what's pending and what's due. RealTimeArbiter
only knows what kind of collision a due move ran into. GameEngine is the
one place that ties selection state and all of these collaborators
together, working entirely in board cell coordinates (row, col) - pixel
mapping is the input layer's job (see input/board_mapper.py), not this
engine's.

Promotion never pauses the engine: a pawn reaching its promotion rank is
auto-promoted to that rule's default piece the instant it settles (see
RuleEngine), so click/jump/wait carry on uninterrupted. pending_promotions()
still surfaces the square as awaiting a choice, and choose_promotion can
swap in a different piece at any time afterwards - the default is a
placeholder, not a final answer.

The clock/motion/arbiter/game-state collaborators are constructed here
by default but accepted as optional constructor arguments, so a caller
(chiefly tests) can substitute a fake or a variant implementation
without reaching into GameEngine internals.
"""

from kungfu_chess.model.piece import PieceState
from kungfu_chess.model.position import Position, chebyshev_distance
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import ManualClock, MotionTracker
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter, CollisionKind

DEFAULT_MOVE_DURATION_PER_CELL_MS = 1000
DEFAULT_JUMP_DURATION_MS = 1000


class GameEngine:
    def __init__(
        self,
        board,
        rule_engine,
        clock=None,
        motion=None,
        arbiter=None,
        game_state=None,
        move_duration_per_cell_ms=DEFAULT_MOVE_DURATION_PER_CELL_MS,
        jump_duration_ms=DEFAULT_JUMP_DURATION_MS,
    ):
        self._board = board
        self._rule_engine = rule_engine
        self._clock = clock if clock is not None else ManualClock()
        self._motion = motion if motion is not None else MotionTracker()
        self._arbiter = arbiter if arbiter is not None else RealTimeArbiter()
        self._game_state = game_state if game_state is not None else GameState()
        self._game_state.attach_board(board)
        self._move_duration_per_cell_ms = move_duration_per_cell_ms
        self._jump_duration_ms = jump_duration_ms
        self._selected = None  # Position or None

    def board(self):
        return self._board

    def game_state(self):
        """The read-only snapshot the view layer draws from."""
        return self._game_state

    def is_game_over(self):
        return self._game_state.is_game_over()

    def move_history(self):
        """Settled moves so far, in algebraic notation, oldest first."""
        return self._game_state.move_history()

    def scores(self):
        """Each color's cumulative score from captures so far, as {"w": int, "b": int}."""
        return self._game_state.scores()

    def pending_promotions(self):
        """Squares that auto-promoted to a default piece and are still
        open to being overridden, as a list of
        {"row", "col", "color", "choices"} dicts. Play is not blocked
        while this is non-empty - see choose_promotion.
        """
        return [
            {"row": p.position.row, "col": p.position.col, "color": p.color, "choices": p.choices}
            for p in self._game_state.pending_promotions()
        ]

    def choose_promotion(self, row, col, piece_type):
        """Override the auto-promoted piece at (row, col) with
        `piece_type` (e.g. "Q"). No-op if there's no pending promotion at
        that square, or piece_type isn't one of its configured choices.
        """
        if self._game_state.is_game_over():
            return
        self._rule_engine.apply_promotion_choice(
            self._board, self._game_state, Position(row, col), piece_type
        )

    def _is_paused(self):
        return self._game_state.is_game_over()

    def click(self, row, col):
        if self._is_paused():
            return
        if not self._board.in_bounds(row, col):
            return

        position = Position(row, col)
        piece = self._board.get(row, col)

        if self._selected is None:
            # A piece already mid-route cannot be selected - this is what
            # makes redirecting an in-flight piece impossible. Once it
            # settles, it becomes selectable again immediately - no
            # separate cooldown exists.
            if piece is not None and piece.state != PieceState.MOVING:
                self._selected = position
            return

        selected_piece = self._board.get(self._selected.row, self._selected.col)

        if piece is not None and piece.color == selected_piece.color:
            if piece.state != PieceState.MOVING:
                self._selected = position
            return

        self._try_request_move(self._selected, position, selected_piece)

    def jump(self, row, col):
        if self._is_paused():
            return
        if not self._board.in_bounds(row, col):
            return

        position = Position(row, col)
        piece = self._board.get(row, col)
        if piece is None:
            return
        if piece.state != PieceState.IDLE:
            return  # a moving or already-airborne piece cannot (re-)jump

        land_at = self._clock.now() + self._jump_duration_ms
        self._motion.schedule_jump(position, piece, land_at)

    def wait(self, ms):
        if self._is_paused():
            return
        self._clock.advance(ms)
        self._settle_due_moves()
        self._motion.land_due_jumps(self._clock.now())

    def _try_request_move(self, source, destination, selected_piece):
        if self._motion.has_opposing_color_in_flight(selected_piece.color):
            # Opposite colors cannot move concurrently: while any piece of
            # the other color is still in transit, a new move cannot be
            # scheduled. Same-color pieces are unaffected.
            return

        is_legal = self._rule_engine.is_legal_move(selected_piece, self._board, source, destination)
        if not is_legal:
            # An illegal-shape click is a no-op for the whole click, so
            # the current selection is kept.
            return

        complete_at = self._clock.now() + self._move_duration_ms(source, destination)
        self._motion.schedule_move(source, destination, complete_at, selected_piece)
        self._selected = None

    def _move_duration_ms(self, source, destination):
        return chebyshev_distance(source, destination) * self._move_duration_per_cell_ms

    def _settle_due_moves(self):
        for move in self._motion.take_due_moves(self._clock.now()):
            self._settle_one_move(move)
            if self._game_state.is_game_over():
                self._motion.clear_moves()
                self._motion.clear_jumps()
                return

    def _settle_one_move(self, move):
        outcome = self._arbiter.classify(self._board, self._motion, move)

        if outcome.kind in (CollisionKind.MOVER_GONE, CollisionKind.FRIENDLY_CANCEL):
            return

        if outcome.kind == CollisionKind.AIRBORNE_CAPTURE:
            self._rule_engine.settle_airborne_capture(
                self._board,
                self._game_state,
                move.piece,
                outcome.defender_piece,
                move.to_position,
                move.from_position,
            )
            return

        self._rule_engine.settle_clear_move(
            self._board, self._game_state, move.piece, move.from_position, move.to_position
        )