"""Ties board, real-time motion, the arbiter, and the rule engine
together into request_move/jump/wait/choose_promotion handling.

Board only knows how to store pieces and apply a move. RuleEngine only
knows whether a shape is legal, what cell-by-cell path it follows, and
what settling a leg should *do*. MotionTracker only knows what's pending
and what's due. RealTimeArbiter only knows what kind of collision a due
leg ran into. GameEngine is the one place that ties all of these
collaborators together, working entirely in board cell coordinates (row,
col) - pixel mapping and click-selection state are the input layer's job
(see input/board_mapper.py and input/controller.py), not this engine's.

A multi-cell move advances one cell ("leg") at a time rather than as a
single atomic jump from source to destination: after each leg completes,
the next cell's occupancy is re-checked in real time before advancing
into it (see UI_PLAN.md Sec 2) - a friendly piece there stops the move
permanently where it stands, a grounded enemy is captured and ends the
move right there, and an enemy currently airborne is safely passable (no
collision until its own landing instant - see _land_due_jumps). Only the
final leg of a move (wherever it actually ends up stopping) is recorded
into GameState - intermediate legs are bare board relocations with no
history/score/promotion bookkeeping, so a slide across several cells
still produces exactly one move-history entry, not one per cell.

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
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from kungfu_chess.realtime.motion import ManualClock, MotionTracker
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter, CollisionKind

DEFAULT_MOVE_DURATION_PER_CELL_MS = 1000
DEFAULT_JUMP_DURATION_MS = 1000
DEFAULT_LONG_REST_DURATION_MS = 1000
DEFAULT_SHORT_REST_DURATION_MS = 500


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
        long_rest_duration_ms=DEFAULT_LONG_REST_DURATION_MS,
        short_rest_duration_ms=DEFAULT_SHORT_REST_DURATION_MS,
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
        self._long_rest_duration_ms = long_rest_duration_ms
        self._short_rest_duration_ms = short_rest_duration_ms

    def board(self):
        return self._board

    def game_state(self):
        """The read-only snapshot the view layer draws from."""
        return self._game_state

    def now(self):
        """The engine's own clock reading in ms (see realtime.motion.
        ManualClock) - exposed read-only for the animation layer
        (UI_PLAN.md Sec 5) to compute elapsed = now() - state_entered_at.
        Not the same clock as driver.time_source's wall-clock now_ms() -
        this one only advances via wait(), and the two stay in step only
        because game_loop feeds real elapsed time into wait(ms) every
        tick.
        """
        return self._clock.now()

    def in_flight_leg(self, piece):
        """(current_position, leg_target, leg_started_at_ms,
        complete_at_ms) for `piece`'s currently in-flight move leg, or
        None if it isn't mid-leg right now. Forwards to MotionTracker.
        in_flight_leg (see realtime/motion.py) - exposed for the
        animation layer (UI_PLAN.md Sec 5) to interpolate a MOVING
        piece's on-screen position between two cells. `piece` is matched
        by identity, the same Piece instance the caller already read off
        a GameState board snapshot.
        """
        return self._motion.in_flight_leg(piece)

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

    def request_move(self, from_row, from_col, to_row, to_col):
        if self._is_paused():
            return
        if not self._board.in_bounds(from_row, from_col) or not self._board.in_bounds(to_row, to_col):
            return

        piece = self._board.get(from_row, from_col)
        # Only an IDLE piece can move - this is what makes redirecting an
        # in-flight piece impossible, keeps an airborne piece committed to
        # its jump, and keeps a resting piece unmovable until its rest
        # elapses.
        if piece is None or piece.state != PieceState.IDLE:
            return

        self._try_request_move(Position(from_row, from_col), Position(to_row, to_col), piece)

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
            return  # a moving, resting, or already-airborne piece cannot (re-)jump

        land_at = self._clock.now() + self._jump_duration_ms
        self._motion.schedule_jump(position, piece, land_at, self._clock.now())

    def wait(self, ms):
        if self._is_paused():
            return
        self._clock.advance(ms)
        self._settle_due_moves()
        self._land_due_jumps()
        self._motion.wake_due_rests(self._clock.now())

    def _clear_all_motion(self):
        now = self._clock.now()
        self._motion.clear_moves(now)
        self._motion.clear_jumps(now)
        self._motion.clear_rests(now)

    def _land_due_jumps(self):
        for jump in self._motion.land_due_jumps(self._clock.now()):
            occupant = self._board.get(jump.position.row, jump.position.col)

            if occupant is not None and occupant is not jump.piece and occupant.color != jump.piece.color:
                # Someone settled onto this cell as an ordinary (non-
                # capturing) arrival sometime during the flight (see
                # passes_as_empty / settle_clear_move) - only now, at the
                # exact landing instant, is it actually captured.
                ends_game = self._rule_engine.settle_airborne_capture(
                    self._board, self._game_state, occupant, jump.piece, jump.position, jump.position
                )
                if ends_game:
                    self._clear_all_motion()
                    return
            else:
                # No one to capture: either an untouched landing (occupant
                # is still jump.piece itself), or the cell is now empty
                # because some other piece merely passed *through* it and
                # continued elsewhere (see SlidePattern - an enemy-airborne
                # cell doesn't stop a slide, so a mover can vacate it again
                # on its way past) - either way the piece reclaims its own
                # cell here. (A friendly occupant is also handled by this
                # branch, but is unreachable given passes_as_empty's
                # invariants - a friendly piece is never treated as
                # passable onto the jumper's own cell, see FRIENDLY_BLOCK -
                # kept only as a defensive fallback, not a live scenario.)
                self._board.place(jump.position.row, jump.position.col, jump.piece)

            self._motion.begin_rest(
                jump.piece, PieceState.SHORT_REST, self._clock.now() + self._short_rest_duration_ms, self._clock.now()
            )

    def _try_request_move(self, source, destination, selected_piece):
        if self._motion.has_opposing_color_in_flight(selected_piece.color):
            # Opposite colors cannot move concurrently: while any piece of
            # the other color is still in transit, a new move cannot be
            # scheduled. Same-color pieces are unaffected.
            return

        is_legal = self._rule_engine.is_legal_move(selected_piece, self._board, source, destination)
        if not is_legal:
            return

        path = self._rule_engine.path_for_move(selected_piece, self._board, source, destination)
        self._motion.schedule_move(source, path, selected_piece, self._move_duration_per_cell_ms, self._clock.now())

    def _settle_due_moves(self):
        while True:
            due = self._motion.take_due_moves(self._clock.now())
            if not due:
                return
            for move in due:
                self._settle_one_leg(move)
                if self._game_state.is_game_over():
                    self._clear_all_motion()
                    return

    def _settle_one_leg(self, move):
        outcome = self._arbiter.classify(self._board, move)

        if outcome.kind == CollisionKind.MOVER_GONE:
            return

        if outcome.kind == CollisionKind.FRIENDLY_BLOCK:
            self._stop_for_friendly_block(move)
            return

        if outcome.kind == CollisionKind.ENEMY_CAPTURE:
            self._finish_leg_and_settle(move, move.leg_target)
            return

        # CLEAR: either truly empty, or a safely-passable airborne enemy.
        if move.remaining_path:
            # An intermediate hop - bare relocation, no bookkeeping - the
            # move isn't over yet, so nothing is recorded until it is.
            self._board.apply_move(
                move.current_position.row, move.current_position.col,
                move.leg_target.row, move.leg_target.col,
            )
            self._motion.schedule_next_leg(move, self._move_duration_per_cell_ms)
        else:
            self._finish_leg_and_settle(move, move.leg_target)

    def _stop_for_friendly_block(self, move):
        if move.steps_completed == 0:
            # Blocked before moving even one cell - as if nothing happened
            # (this can only occur if the path became blocked between
            # request time and this first leg; the initial request-time
            # legality check already rejects a destination blocked by a
            # friendly piece at request time).
            self._motion.mark_idle(move.piece, self._clock.now())
            return

        self._rule_engine.settle_stopped_move(
            self._board, self._game_state, move.piece, move.current_position, move.current_position
        )
        self._motion.begin_rest(
            move.piece, PieceState.LONG_REST, self._clock.now() + self._long_rest_duration_ms, self._clock.now()
        )

    def _finish_leg_and_settle(self, move, stop_at):
        self._rule_engine.settle_clear_move(self._board, self._game_state, move.piece, move.current_position, stop_at)
        if self._game_state.is_game_over():
            return
        self._motion.begin_rest(
            move.piece, PieceState.LONG_REST, self._clock.now() + self._long_rest_duration_ms, self._clock.now()
        )