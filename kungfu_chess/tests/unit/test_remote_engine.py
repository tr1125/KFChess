import queue

from kungfu_chess.net.remote_engine import RemoteEngine
from kungfu_chess.io.state_codec import to_wire_state
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, PieceState
from kungfu_chess.model.position import Position
from kungfu_chess.model.game_state import GameState
from server import protocol


SMALL_BOARD_ROWS = [
    [Piece(color="w", kind="K", cell=Position(0, 0)), None, None],
    [None, None, None],
    [None, None, Piece(color="b", kind="K", cell=Position(2, 2))],
]


def make_state_payload(rows=None):
    board = Board(rows if rows is not None else [list(row) for row in SMALL_BOARD_ROWS])
    state = GameState()
    state.attach_board(board)
    return to_wire_state(state)


class RecordingSender:
    def __init__(self):
        self.calls = []

    def __call__(self, msg_type, payload):
        self.calls.append((msg_type, payload))


def make_engine():
    sender = RecordingSender()
    incoming = queue.Queue()
    engine = RemoteEngine(sender, incoming)
    return engine, sender, incoming


# --- outbound: request_move / jump / choose_promotion ---

def test_request_move_sends_a_move_message_with_square_names():
    engine, sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)  # drain the initial state so board_height() is known

    engine.request_move(0, 0, 1, 1)
    assert sender.calls == [(protocol.MSG_MOVE, {"from": "a3", "to": "b2"})]


def test_jump_sends_a_jump_message_with_a_square_name():
    engine, sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    engine.jump(0, 0)
    assert sender.calls == [(protocol.MSG_JUMP, {"square": "a3"})]


def test_choose_promotion_sends_a_promote_message():
    engine, sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    engine.choose_promotion(0, 0, "Q")
    assert sender.calls == [(protocol.MSG_PROMOTE, {"square": "a3", "piece_type": "Q"})]


# --- inbound: state messages update game_state() ---

def test_state_message_replaces_the_cached_game_state():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    top_left = engine.game_state().board_rows()[0][0]
    assert (top_left.color, top_left.kind) == ("w", "K")


def test_now_advances_by_whatever_wait_is_given():
    engine, _sender, _incoming = make_engine()
    assert engine.now() == 0
    engine.wait(250)
    assert engine.now() == 250
    engine.wait(10)
    assert engine.now() == 260


# --- inbound: move_started drives in_flight_leg ---

def test_move_started_produces_an_in_flight_leg_for_the_piece_at_its_from_square():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(0)

    current, target, started_at, complete_at = engine.in_flight_leg(piece)
    assert (current.row, current.col) == (0, 0)
    assert (target.row, target.col) == (1, 1)
    assert started_at == 0
    assert complete_at == 1000


def test_move_started_marks_the_piece_moving_so_it_renders_the_right_sprite():
    """Regression test: move_started previously only recorded WHERE a
    piece is headed (for in_flight_leg's position interpolation), never
    updating piece.state itself - so the client kept rendering the
    piece's stale (usually IDLE) sprite for the whole glide, since
    nothing else tells it the piece is now moving until the *settling*
    state message arrives. The local engine's own MotionTracker sets
    this the instant a move is scheduled - the client needs to mirror
    that for its sprite selection (_animated_sprite_path) to pick the
    "move" animation instead of "idle" while gliding.
    """
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]
    assert piece.state == PieceState.IDLE  # sanity check on the starting snapshot

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(250)

    assert piece.state == PieceState.MOVING
    assert piece.state_entered_at == 0


def test_move_started_for_a_jump_marks_the_piece_airborne():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "a3", "duration_ms": 1000,
    }))
    engine.wait(0)

    assert piece.state == PieceState.AIRBORNE


def test_a_chained_second_leg_updates_state_entered_at_for_the_new_leg():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(1000)
    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "b2", "to": "c1", "duration_ms": 1000,
    }))
    engine.wait(0)

    assert piece.state == PieceState.MOVING
    assert piece.state_entered_at == 1000


def test_in_flight_leg_is_none_for_a_piece_with_no_active_glide():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[2][2]
    assert engine.in_flight_leg(piece) is None


def test_in_flight_leg_freezes_progress_at_one_once_locally_overdue():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]
    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(0)

    engine.wait(5000)  # well past duration_ms, but no confirming `state` yet

    current, target, started_at, complete_at = engine.in_flight_leg(piece)
    assert complete_at == engine.now()  # frozen at "now", not the original overdue complete_at_ms


def test_a_second_leg_chains_onto_the_same_piece_via_its_previous_to_square():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(1000)  # first leg's local timer elapses
    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "b2", "to": "c1", "duration_ms": 1000,
    }))
    engine.wait(0)

    current, target, started_at, complete_at = engine.in_flight_leg(piece)
    assert (current.row, current.col) == (1, 1)
    assert (target.row, target.col) == (2, 2)
    assert started_at == 1000
    assert complete_at == 2000


def test_state_message_preserves_a_glide_still_reported_as_in_flight():
    """An UNRELATED state broadcast (e.g. triggered by the other player's
    own settlement elsewhere on the board) must not cut off THIS piece's
    still-in-progress glide - it should only be dropped once a state
    message actually shows this piece as no longer MOVING/AIRBORNE. A
    piece that's still mid-flight is physically still at its origin
    square in any such snapshot (Board.apply_move only runs at
    settlement), reported MOVING.
    """
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(500)  # halfway through the glide

    unrelated_rows = [list(row) for row in SMALL_BOARD_ROWS]
    unrelated_rows[0][0] = Piece(color="w", kind="K", cell=Position(0, 0), state=PieceState.MOVING)
    incoming.put((protocol.MSG_STATE, make_state_payload(unrelated_rows)))
    engine.wait(0)

    new_piece = engine.game_state().board_rows()[0][0]
    current, target, started_at, complete_at = engine.in_flight_leg(new_piece)
    assert (current.row, current.col) == (0, 0)
    assert (target.row, target.col) == (1, 1)
    assert started_at == 0
    assert complete_at == 1000


def test_a_third_move_started_still_chains_correctly_after_a_preserved_glide():
    """The chaining index (_active_piece_by_position) must stay keyed to
    the NEW piece object after a preserved glide, not the one from before
    the state refresh - otherwise a later leg's move_started (whose
    `from` matches this glide's `to`) would fail to find it.
    """
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(500)

    unrelated_rows = [list(row) for row in SMALL_BOARD_ROWS]
    unrelated_rows[0][0] = Piece(color="w", kind="K", cell=Position(0, 0), state=PieceState.MOVING)
    incoming.put((protocol.MSG_STATE, make_state_payload(unrelated_rows)))
    engine.wait(500)  # leg settles locally

    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "b2", "to": "c1", "duration_ms": 1000,
    }))
    engine.wait(0)

    new_piece = engine.game_state().board_rows()[0][0]
    current, target, started_at, complete_at = engine.in_flight_leg(new_piece)
    assert (current.row, current.col) == (1, 1)
    assert (target.row, target.col) == (2, 2)
    assert started_at == 1000
    assert complete_at == 2000


def test_state_message_clears_any_active_glide():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    piece = engine.game_state().board_rows()[0][0]
    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "a3", "to": "b2", "duration_ms": 1000,
    }))
    engine.wait(0)

    settled_rows = [list(row) for row in SMALL_BOARD_ROWS]
    settled_rows[0][0] = None
    settled_rows[1][1] = Piece(color="w", kind="K", cell=Position(1, 1))
    incoming.put((protocol.MSG_STATE, make_state_payload(settled_rows)))
    engine.wait(0)

    assert engine.in_flight_leg(piece) is None


# --- defensive edge cases ---

def test_move_started_for_an_unknown_square_is_silently_ignored():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)

    # (1, 0) is empty on SMALL_BOARD_ROWS - no piece to find there.
    incoming.put((protocol.MSG_MOVE_STARTED, {
        "color": "w", "kind": "K", "from": "b2", "to": "a3", "duration_ms": 1000,
    }))
    engine.wait(0)  # must not raise

    assert engine._glides == {}


def test_piece_at_returns_none_outside_board_bounds():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_STATE, make_state_payload()))
    engine.wait(0)
    assert engine._piece_at(Position(-1, 0)) is None
    assert engine._piece_at(Position(0, 99)) is None


# --- status messages surfaced for app_ui.py ---

def test_login_ok_and_game_started_and_game_ended_are_recorded_in_status():
    engine, _sender, incoming = make_engine()
    incoming.put((protocol.MSG_LOGIN_OK, {"username": "alice", "rating": 1200}))
    incoming.put((protocol.MSG_GAME_STARTED, {"white": "alice", "black": "bob", "room_id": "local"}))
    incoming.put((protocol.MSG_GAME_ENDED, {"result": "white_wins", "reason": "capture"}))
    engine.wait(0)

    assert engine.status[protocol.MSG_LOGIN_OK] == {"username": "alice", "rating": 1200}
    assert engine.status[protocol.MSG_GAME_STARTED] == {"white": "alice", "black": "bob", "room_id": "local"}
    assert engine.status[protocol.MSG_GAME_ENDED] == {"result": "white_wins", "reason": "capture"}