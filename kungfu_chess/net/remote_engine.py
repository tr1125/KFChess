"""A GameEngine-shaped adapter over the network (see
KFChess_Server_Plan.md Stage 2). `Controller` (input/controller.py) only
ever calls seven methods on whatever `engine` it's given - request_move,
jump, wait, choose_promotion, game_state, now, in_flight_leg - and never
imports GameEngine's type. Handing Controller one of these instead of a
real GameEngine is what lets the existing Controller/GameLoop/OpenCvView
code (and their tests) drive networked play completely unchanged.

`send`/`incoming` are injected (a plain callable and a queue.Queue-like
object exposing get_nowait()) rather than a concrete transport, so this
class is unit-testable without a real socket or background thread - see
KFChess_Server_Plan.md Sec 8's DI mandate ("no monkey-patching, ever").
See net/ws_client.py for the real transport that supplies both.
"""

import queue

from kungfu_chess.model.game_state import GameState
from kungfu_chess.model.piece import PieceState
from kungfu_chess.model.position import Position, square_name, parse_square_name
from kungfu_chess.io.state_codec import from_wire_state

from server import protocol

# Piece states a state message can catch mid-flight - a glide for a piece
# reported as anything else (IDLE/LONG_REST/SHORT_REST) has genuinely
# settled and should not be carried forward - see _handle_state.
_IN_FLIGHT_STATES = (PieceState.MOVING, PieceState.AIRBORNE)


class RemoteEngine:
    def __init__(self, send, incoming):
        self._send = send
        self._incoming = incoming
        self._game_state = GameState()
        self._now_ms = 0
        # Piece -> (current_position, leg_target, leg_started_at_ms,
        # complete_at_ms), same shape as MotionTracker.in_flight_leg -
        # populated from `move_started` messages, cleared wholesale
        # whenever an authoritative `state` message lands (see
        # _handle_state). Piece is eq=False (identity semantics - see
        # model/piece.py), so this dict is keyed exactly like
        # MotionTracker's own identity-based lookup.
        self._glides = {}
        # Position -> Piece: which piece a still-in-flight multi-leg move
        # is currently heading towards, so a later leg's `move_started`
        # (whose `from` is that same position) can find the right piece
        # even though the client's cached board never physically moves it
        # mid-flight (only a `state` message updates the board) - see
        # _handle_move_started.
        self._active_piece_by_position = {}
        # Last-seen payload per status message type (login_ok, login_error,
        # game_started, game_ended, error) - read directly by app_ui.py,
        # which isn't bound by the input/view/driver boundary discipline
        # (it's the composition root, same as it already owns Controller).
        self.status = {}

    # --- Controller-facing surface ---------------------------------------

    def request_move(self, from_row, from_col, to_row, to_col):
        height = self._game_state.board_height()
        self._send(protocol.MSG_MOVE, {
            "from": square_name(Position(from_row, from_col), height),
            "to": square_name(Position(to_row, to_col), height),
        })

    def jump(self, row, col):
        height = self._game_state.board_height()
        self._send(protocol.MSG_JUMP, {"square": square_name(Position(row, col), height)})

    def choose_promotion(self, row, col, piece_type):
        height = self._game_state.board_height()
        self._send(protocol.MSG_PROMOTE, {
            "square": square_name(Position(row, col), height), "piece_type": piece_type,
        })

    def game_state(self):
        return self._game_state

    def now(self):
        return self._now_ms

    def in_flight_leg(self, piece):
        leg = self._glides.get(piece)
        if leg is None:
            return None
        current_position, leg_target, started_at_ms, complete_at_ms = leg
        if complete_at_ms < self._now_ms:
            # The locally-timed glide has run its course but the
            # settling `state` message hasn't arrived yet - freeze
            # progress at exactly 1.0 (piece held at its destination)
            # instead of letting it overshoot, until `state` clears this
            # entry and the (by-then-updated) static cell position takes
            # over with no visible jump.
            complete_at_ms = self._now_ms
        return (current_position, leg_target, started_at_ms, complete_at_ms)

    def wait(self, ms):
        self._drain_incoming()
        self._now_ms += ms

    # --- inbound message handling ----------------------------------------

    def _drain_incoming(self):
        while True:
            try:
                msg_type, payload = self._incoming.get_nowait()
            except queue.Empty:
                return
            self._handle(msg_type, payload)

    def _handle(self, msg_type, payload):
        if msg_type == protocol.MSG_STATE:
            self._handle_state(payload)
        elif msg_type == protocol.MSG_MOVE_STARTED:
            self._handle_move_started(payload)
        else:
            self.status[msg_type] = payload

    def _handle_state(self, payload):
        """Replace the cached snapshot, carrying forward any glide that
        the NEW snapshot itself still reports as MOVING/AIRBORNE at its
        destination square. This matters because a `state` broadcast
        isn't only sent when *this* piece's own move settles - it's sent
        on *any* settlement/score-change anywhere on the board (real-time
        play means the other player's moves settle independently and
        often). Wiping every glide unconditionally on every `state`
        message would cut off this piece's own still-in-flight animation
        the instant an unrelated piece elsewhere finished moving.
        """
        old_glides = self._glides
        self._game_state = from_wire_state(payload)
        self._glides = {}
        self._active_piece_by_position = {}
        for from_pos, to_pos, started_at_ms, complete_at_ms in old_glides.values():
            # A leg's own board mutation (Board.apply_move) only happens
            # once that leg actually settles - so a piece that's still
            # genuinely mid-flight is still physically sitting at
            # from_pos in any snapshot taken before then, still reported
            # MOVING/AIRBORNE (MotionTracker sets that the instant the
            # leg is scheduled, well before it settles).
            piece = self._piece_at(from_pos)
            if piece is not None and piece.state in _IN_FLIGHT_STATES:
                self._glides[piece] = (from_pos, to_pos, started_at_ms, complete_at_ms)
                self._active_piece_by_position[to_pos] = piece

    def _handle_move_started(self, payload):
        height = self._game_state.board_height()
        from_pos = parse_square_name(payload["from"], height)
        to_pos = parse_square_name(payload["to"], height)

        piece = self._active_piece_by_position.pop(from_pos, None)
        if piece is None:
            piece = self._piece_at(from_pos)
        if piece is None:
            return  # can't locate the piece this leg belongs to - skip the glide, not fatal

        # Mirror what the server's own MotionTracker does the instant a
        # leg is scheduled (see realtime/motion.py's schedule_move/
        # schedule_jump): mark the piece MOVING/AIRBORNE right away, not
        # just registering where it's headed. Without this, the piece
        # keeps rendering its previous (stale) sprite state - usually
        # IDLE - for the entire glide, since nothing else updates
        # piece.state until the settling `state` message arrives. A jump
        # is recognizable as a leg whose `from`/`to` are the same square.
        piece.state = PieceState.AIRBORNE if from_pos == to_pos else PieceState.MOVING
        piece.state_entered_at = self._now_ms

        self._active_piece_by_position[to_pos] = piece
        self._glides[piece] = (from_pos, to_pos, self._now_ms, self._now_ms + payload["duration_ms"])

    def _piece_at(self, position):
        if not (0 <= position.row < self._game_state.board_height()
                and 0 <= position.col < self._game_state.board_width()):
            return None
        return self._game_state.board_rows()[position.row][position.col]