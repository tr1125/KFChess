"""In-flight move/timing state: the manual game clock, and tracking of
pending (in-transit) moves and airborne (mid-jump) pieces.

The game does not run in wall-clock time - it only advances when a
'wait' command is processed. ManualClock is the sole implementation for
now. If a future mode needs real time (e.g. a live multiplayer server),
it can add a WallClock implementing the same two methods (now, advance)
without the engine changing at all.

A multi-cell move is tracked one cell ("leg") at a time rather than as a
single atomic from/to pair: PendingMove.current_position is where the
piece has actually arrived so far, leg_target is the cell the in-flight
leg is heading to, and remaining_path holds whatever cells (if any) lie
beyond leg_target on the originally requested route. This is what lets
GameEngine re-check occupancy before every single-cell step instead of
only once at click time (see UI_PLAN.md Sec 2). MotionTracker itself has
no opinion about *how many* legs a given move should have - that's
decided entirely by whichever movement pattern matched it (see
RuleEngine.path_for_move / StepPattern/SlidePattern/PawnDoubleStepPattern
in rules/piece_rules.py); a knight's path is a single leg because
StepPattern says so, not because MotionTracker knows what a knight is.

A leg's own duration is `per_cell_ms` scaled by that leg's Chebyshev
distance (current_position to leg_target), not a flat `per_cell_ms`
regardless of span. Every leg produced by SlidePattern/PawnDoubleStepPattern
already spans exactly one cell, so this is a no-op for them - but a
StepPattern leg (e.g. a knight's L-shape) has no intermediate cells to
check and so is scheduled as a single leg (see above) that nonetheless
covers a Chebyshev distance of 2, and must take 2x as long to cross as a
single-cell leg at the same per_cell_ms rate. Getting this wrong once
silently halved knight move duration - the fix is computed here, from
the positions this class already receives, rather than pushing distance
awareness into GameEngine or the rules layer.

MotionTracker only knows scheduling questions - a move leg was requested,
here's when it completes; a piece jumped, here's when it lands; what's
due right now - it has no opinion about what settling a leg should *do*
(captures, cancellations, promotion, continuing to the next leg). That
resolution logic belongs to the rules layer, orchestrated by the engine,
which asks this class only scheduling questions.

MotionTracker is also the sole writer of Piece.state (and its
state_entered_at timestamp - see UI_PLAN.md Sec 5) for its own pending
lists: scheduling a move leg or jump marks the piece MOVING/AIRBORNE,
and taking a move/jump off a pending list marks it IDLE again - so a
piece's own `state` field is always an accurate, directly readable
reflection of what these lists say, without another caller needing to
ask MotionTracker by position. Whether a piece then goes on to *rest*
(LONG_REST/SHORT_REST) is a decision the caller (GameEngine) makes with
`begin_rest`, once it knows more than MotionTracker does - e.g. whether a
due leg actually settled as the end of the whole move, or that a landed
jump always counts as a real, successful event (see RealTimeArbiter - an
airborne piece can never be dislodged). Resting itself is tracked the
same way as pending moves and airborne jumps: a piece is registered with
a wake-up time and comes off the list (back to IDLE) once that time is
reached.
"""

from dataclasses import dataclass

from kungfu_chess.model.piece import PieceState
from kungfu_chess.model.position import chebyshev_distance


class ManualClock:
    def __init__(self):
        self._now_ms = 0

    def now(self):
        return self._now_ms

    def advance(self, ms):
        self._now_ms += ms


@dataclass
class PendingMove:
    current_position: object  # Position - where the piece has actually arrived so far
    leg_target: object  # Position - the cell this in-flight leg is heading to
    remaining_path: tuple  # Position, ... - cells beyond leg_target, in order (may be empty)
    leg_started_at_ms: int  # when this leg itself began (see in_flight_leg)
    complete_at_ms: int
    piece: object  # Piece - captured at scheduling time, not re-read from the board later
    steps_completed: int  # legs already successfully landed before this one


@dataclass
class AirborneJump:
    position: object  # Position
    piece: object  # Piece
    land_at_ms: int


@dataclass
class Resting:
    piece: object  # Piece
    rest_over_ms: int


class MotionTracker:
    def __init__(self):
        self._pending_moves = []
        self._airborne_jumps = []
        self._resting = []

    #TODO: consider implementing inheritance
    # --- moves -----------------------------------------------------------

    def schedule_move(self, from_position, path, piece, per_cell_ms, now_ms):
        """Schedule the first leg of a move along `path` (the cell-by-cell
        route already computed by RuleEngine.path_for_move - one entry
        per leg, in order), taking `per_cell_ms` per cell of this leg's own
        Chebyshev distance to cross - not a flat `per_cell_ms` regardless of
        span (see module docstring: a knight's single StepPattern leg still
        covers 2 cells and must take 2x as long as a 1-cell leg).
        """
        leg_target = path[0]
        leg_duration_ms = chebyshev_distance(from_position, leg_target) * per_cell_ms
        self._pending_moves.append(PendingMove(
            current_position=from_position,
            leg_target=leg_target,
            remaining_path=tuple(path[1:]),
            leg_started_at_ms=now_ms,
            complete_at_ms=now_ms + leg_duration_ms,
            piece=piece,
            steps_completed=0,
        ))
        piece.state = PieceState.MOVING
        piece.state_entered_at = now_ms

    def schedule_next_leg(self, move, per_cell_ms):
        """Continue an in-flight move to its next leg once the current
        leg has completed cleanly and cells remain beyond it. The next
        leg's due time is chained from *this* leg's own due time (not
        from whenever `wait()` happened to process it) - otherwise a
        single big `wait()` call that jumps far past several legs'-worth
        of time would only ever advance one leg per call, since each new
        leg would keep being scheduled `per_cell_ms` further into the
        future from "now" instead of from the schedule already in
        progress. Chaining from complete_at_ms keeps every leg's due time
        anchored to when the whole move was first requested, so a big
        enough `wait()` still cascades through every remaining leg in one
        call, exactly as it would if the same total time were spent
        across several smaller `wait()` calls instead.

        The piece stays MOVING throughout, so its state/state_entered_at
        are left untouched here - only the pending entry's current/target
        cells advance. This next leg's own duration is likewise scaled by
        its own Chebyshev distance (leg_target to next_target), same as
        schedule_move - see module docstring.
        """
        next_target = move.remaining_path[0]
        leg_started_at_ms = move.complete_at_ms
        leg_duration_ms = chebyshev_distance(move.leg_target, next_target) * per_cell_ms
        self._pending_moves.append(PendingMove(
            current_position=move.leg_target,
            leg_target=next_target,
            remaining_path=move.remaining_path[1:],
            leg_started_at_ms=leg_started_at_ms,
            complete_at_ms=leg_started_at_ms + leg_duration_ms,
            piece=move.piece,
            steps_completed=move.steps_completed + 1,
        ))

    def in_flight_leg(self, piece):
        """The (current_position, leg_target, leg_started_at_ms,
        complete_at_ms) of the pending leg currently tracking `piece`, or
        None if it isn't mid-leg. Exposed for the animation step
        (UI_PLAN.md Sec 5) to compute glide progress between the two
        cells - leg_started_at_ms/complete_at_ms are returned explicitly
        rather than derived from a flat per-cell-ms constant, since a
        leg's duration is not always exactly one cell's worth of time
        (see module docstring: a knight's leg spans 2 cells' worth).
        """
        for move in self._pending_moves:
            if move.piece is piece:
                return (move.current_position, move.leg_target, move.leg_started_at_ms, move.complete_at_ms)
        return None

    def has_pending_move_from(self, position):
        return any(move.current_position == position for move in self._pending_moves)

    def has_opposing_color_in_flight(self, color):
        return any(move.piece.color != color for move in self._pending_moves)

    def take_due_moves(self, now_ms):
        """Remove and return every move leg whose time has come; the
        rest stay pending. Does not touch piece.state - a due leg can end
        several different ways (continue, stop, capture), which only the
        caller (GameEngine, via RealTimeArbiter's classification) knows
        how to resolve.
        """
        due = [move for move in self._pending_moves if move.complete_at_ms <= now_ms]
        self._pending_moves = [move for move in self._pending_moves if move.complete_at_ms > now_ms]
        return due

    def mark_idle(self, piece, now_ms):
        """Directly return a piece to IDLE without resting - used when a
        move leg is blocked before the piece has moved even one cell (see
        UI_PLAN.md Sec 2's "stays IDLE" rule), after it's already been
        taken off the pending list by take_due_moves.
        """
        piece.state = PieceState.IDLE
        piece.state_entered_at = now_ms

    def clear_moves(self, now_ms):
        for move in self._pending_moves:
            self.mark_idle(move.piece, now_ms)
        self._pending_moves = []

    # --- jumps -----------------------------------------------------------

    def schedule_jump(self, position, piece, land_at_ms, now_ms):
        self._airborne_jumps.append(AirborneJump(position, piece, land_at_ms))
        piece.state = PieceState.AIRBORNE
        piece.state_entered_at = now_ms

    def is_airborne(self, position):
        return any(jump.position == position for jump in self._airborne_jumps)

    def land_due_jumps(self, now_ms):
        """Remove and return every jump whose window has elapsed; the
        rest stay airborne. No board change is needed here - the piece
        stayed on its cell the whole time, so simply no longer being
        tracked here *is* landing. Does not touch piece.state - whether
        landing is a normal arrival or a mid-air capture depends on who
        (if anyone) is now occupying the cell, which only the caller
        (GameEngine) can decide (see _land_due_jumps).
        """
        landed = [jump for jump in self._airborne_jumps if jump.land_at_ms <= now_ms]
        self._airborne_jumps = [jump for jump in self._airborne_jumps if jump.land_at_ms > now_ms]
        return landed

    def clear_jumps(self, now_ms):
        for jump in self._airborne_jumps:
            jump.piece.state = PieceState.IDLE
            jump.piece.state_entered_at = now_ms
        self._airborne_jumps = []

    # --- rests -------------------------------------------------------------

    def begin_rest(self, piece, state, rest_over_ms, now_ms):
        self._resting.append(Resting(piece, rest_over_ms))
        piece.state = state
        piece.state_entered_at = now_ms

    def wake_due_rests(self, now_ms):
        """Wake every resting piece whose rest is over, back to IDLE."""
        woken = [resting for resting in self._resting if resting.rest_over_ms <= now_ms]
        self._resting = [resting for resting in self._resting if resting.rest_over_ms > now_ms]
        for resting in woken:
            resting.piece.state = PieceState.IDLE
            resting.piece.state_entered_at = now_ms

    def clear_rests(self, now_ms):
        for resting in self._resting:
            resting.piece.state = PieceState.IDLE
            resting.piece.state_entered_at = now_ms
        self._resting = []