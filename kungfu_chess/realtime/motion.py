"""In-flight move/timing state: the manual game clock, and tracking of
pending (in-transit) moves and airborne (mid-jump) pieces.

The game does not run in wall-clock time - it only advances when a
'wait' command is processed. ManualClock is the sole implementation for
now. If a future mode needs real time (e.g. a live multiplayer server),
it can add a WallClock implementing the same two methods (now, advance)
without the engine changing at all.

MotionTracker only knows scheduling questions - a move was requested,
here's when it completes; a piece jumped, here's when it lands; what's
due right now - it has no opinion about what settling should *do*
(captures, cancellations, promotion). That resolution logic belongs to
the rules layer, orchestrated by the engine, which asks this class only
scheduling questions.

MotionTracker is also the sole writer of Piece.state for its own pending
lists: scheduling a move or jump marks the piece MOVING/AIRBORNE, and
taking a move/jump off a pending list marks it IDLE again - so a piece's
own `state` field is always an accurate, directly readable reflection of
what these lists say, without another caller needing to ask
MotionTracker by position. Whether a piece then goes on to *rest*
(LONG_REST/SHORT_REST) is a decision the caller (GameEngine) makes with
`begin_rest`, once it knows more than MotionTracker does - e.g. whether
a due move actually settled, or that a landed jump always counts as a
real, successful event (see RealTimeArbiter - an airborne piece can
never be dislodged). Resting itself is tracked the same way as pending
moves and airborne jumps: a piece is registered with a wake-up time and
comes off the list (back to IDLE) once that time is reached.
"""

from dataclasses import dataclass

from kungfu_chess.model.piece import PieceState


class ManualClock:
    def __init__(self):
        self._now_ms = 0

    def now(self):
        return self._now_ms

    def advance(self, ms):
        self._now_ms += ms


@dataclass
class PendingMove:
    from_position: object  # Position
    to_position: object  # Position
    complete_at_ms: int
    piece: object  # Piece - captured at scheduling time, not re-read from the board later


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

    # --- moves -----------------------------------------------------------

    def schedule_move(self, from_position, to_position, complete_at_ms, piece):
        self._pending_moves.append(PendingMove(from_position, to_position, complete_at_ms, piece))
        piece.state = PieceState.MOVING

    def has_pending_move_from(self, position):
        return any(move.from_position == position for move in self._pending_moves)

    def has_opposing_color_in_flight(self, color):
        return any(move.piece.color != color for move in self._pending_moves)

    def take_due_moves(self, now_ms):
        """Remove and return every move whose time has come; the rest stay pending."""
        due = [move for move in self._pending_moves if move.complete_at_ms <= now_ms]
        self._pending_moves = [move for move in self._pending_moves if move.complete_at_ms > now_ms]
        for move in due:
            move.piece.state = PieceState.IDLE
        return due

    def clear_moves(self):
        for move in self._pending_moves:
            move.piece.state = PieceState.IDLE
        self._pending_moves = []

    # --- jumps -----------------------------------------------------------

    def schedule_jump(self, position, piece, land_at_ms):
        self._airborne_jumps.append(AirborneJump(position, piece, land_at_ms))
        piece.state = PieceState.AIRBORNE

    def is_airborne(self, position):
        return any(jump.position == position for jump in self._airborne_jumps)

    def land_due_jumps(self, now_ms):
        """Remove and return every jump whose window has elapsed; the
        rest stay airborne. No board change is needed here - the piece
        stayed on its cell the whole time, so simply no longer being
        tracked here *is* landing."""
        landed = [jump for jump in self._airborne_jumps if jump.land_at_ms <= now_ms]
        self._airborne_jumps = [jump for jump in self._airborne_jumps if jump.land_at_ms > now_ms]
        for jump in landed:
            jump.piece.state = PieceState.IDLE
        return landed

    def clear_jumps(self):
        for jump in self._airborne_jumps:
            jump.piece.state = PieceState.IDLE
        self._airborne_jumps = []

    # --- rests -------------------------------------------------------------

    def begin_rest(self, piece, state, rest_over_ms):
        self._resting.append(Resting(piece, rest_over_ms))
        piece.state = state

    def wake_due_rests(self, now_ms):
        """Wake every resting piece whose rest is over, back to IDLE."""
        woken = [resting for resting in self._resting if resting.rest_over_ms <= now_ms]
        self._resting = [resting for resting in self._resting if resting.rest_over_ms > now_ms]
        for resting in woken:
            resting.piece.state = PieceState.IDLE

    def clear_rests(self):
        for resting in self._resting:
            resting.piece.state = PieceState.IDLE
        self._resting = []
