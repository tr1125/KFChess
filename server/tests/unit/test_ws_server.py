import asyncio

import websockets

from server import auth, db, protocol, rating
from server.rooms import Room
from server.ws_server import handler, _dispatch


# One king plus one pawn per color - NOT bare King-vs-King, so Stage 3's
# automatic K-v-K draw detection never fires for these tests (see
# test_rooms.py's SMALL_BOARD for the same fix, same reasoning).
SMALL_BOARD = [
    "bK . bP",
    ". . .",
    "wK . wP",
]


def make_services():
    """auth_service and rating_service sharing one real in-memory
    SQLAlchemy session - both read/write the same users table, so they
    must not be built over two separate :memory: engines."""
    session = db.create_session_factory("sqlite:///:memory:")()
    return auth.AuthService(session), rating.RatingService(session), session


class FakeWebSocket:
    """A hand-written test double (no mocking framework) standing in for
    a real websockets connection: `incoming` is fed out one message at a
    time via recv()/async iteration, `sent`/`closed` record what the
    handler did.
    """

    def __init__(self, incoming=None, disconnect_mid_loop=False):
        self._incoming = list(incoming or [])
        self._disconnect_mid_loop = disconnect_mid_loop
        self.sent = []
        self.closed = False
        self.close_code = None
        self.close_reason = None

    async def recv(self):
        if not self._incoming:
            raise websockets.ConnectionClosedOK(None, None)
        return self._incoming.pop(0)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._incoming:
            if self._disconnect_mid_loop:
                raise websockets.ConnectionClosedError(None, None)
            raise StopAsyncIteration
        return self._incoming.pop(0)

    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def send(self, raw_message):
        self.sent.append(raw_message)


def decoded(fake_socket):
    return [protocol.decode(raw) for raw in fake_socket.sent]


def run(coro):
    return asyncio.run(coro)


def make_room():
    auth_service, rating_service, _session = make_services()
    room = Room(rating_service=rating_service, board_lines=SMALL_BOARD, time_source=lambda: 0.0)
    return room, auth_service


def login_message(username, password="secret"):
    return protocol.encode(protocol.MSG_LOGIN, {"username": username, "password": password})


# --- login handshake ---

def test_first_connection_is_logged_in_as_white_and_not_yet_started():
    room, auth_service = make_room()
    socket = FakeWebSocket([login_message("alice")])

    run(handler(socket, room, auth_service))

    msg_type, payload = decoded(socket)[0]
    assert msg_type == protocol.MSG_LOGIN_OK
    assert payload["username"] == "alice"
    assert not socket.closed


def test_second_connection_triggers_game_started_and_initial_state_for_both():
    room, auth_service = make_room()
    # White's connection is registered directly (bypassing handler()'s own
    # login handshake, already covered by the single-connection test above)
    # so it stays "open" (present in the room) to receive Black's broadcast,
    # rather than immediately hitting handler()'s connection-closed cleanup
    # once its one queued message is exhausted.
    white_socket = FakeWebSocket()
    room.add_player(white_socket, "alice")

    black_socket = FakeWebSocket([login_message("bob")])
    run(handler(black_socket, room, auth_service))

    white_types = [msg_type for msg_type, _ in decoded(white_socket)]
    black_types = [msg_type for msg_type, _ in decoded(black_socket)]
    assert protocol.MSG_GAME_STARTED in white_types
    assert protocol.MSG_STATE in white_types
    assert protocol.MSG_GAME_STARTED in black_types
    assert protocol.MSG_STATE in black_types


def test_a_third_connection_is_rejected_with_an_error_and_closed():
    room, auth_service = make_room()
    room.add_player(FakeWebSocket(), "alice")
    room.add_player(FakeWebSocket(), "bob")

    third_socket = FakeWebSocket([login_message("carol")])
    run(handler(third_socket, room, auth_service))

    msg_type, payload = decoded(third_socket)[0]
    assert msg_type == protocol.MSG_ERROR
    assert payload == {"reason": "room_full"}
    assert third_socket.closed


def test_a_non_login_first_message_closes_the_connection():
    room, auth_service = make_room()
    socket = FakeWebSocket([protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "a2"})])
    run(handler(socket, room, auth_service))
    assert socket.closed
    assert socket.sent == []


def test_malformed_first_message_closes_the_connection():
    room, auth_service = make_room()
    socket = FakeWebSocket(["not json"])
    run(handler(socket, room, auth_service))
    assert socket.closed


def test_connection_closed_before_any_message_is_handled_gracefully():
    room, auth_service = make_room()
    socket = FakeWebSocket([])  # recv() immediately raises ConnectionClosedOK
    run(handler(socket, room, auth_service))  # must not raise
    assert socket.sent == []


def test_connection_closed_mid_game_is_handled_gracefully_and_frees_the_slot():
    room, auth_service = make_room()
    socket = FakeWebSocket([login_message("alice")], disconnect_mid_loop=True)
    run(handler(socket, room, auth_service))  # must not raise despite the mid-loop disconnect
    assert not room.is_full()
    assert room.add_player(FakeWebSocket(), "bob") == "w"  # alice's slot was freed


# --- login/auth ---

def test_missing_password_is_rejected_with_login_error():
    room, auth_service = make_room()
    socket = FakeWebSocket([protocol.encode(protocol.MSG_LOGIN, {"username": "alice"})])
    run(handler(socket, room, auth_service))

    msg_type, payload = decoded(socket)[0]
    assert msg_type == protocol.MSG_LOGIN_ERROR
    assert payload == {"reason": "invalid username or password"}
    assert socket.closed


def test_wrong_password_on_an_existing_account_is_rejected_with_login_error():
    room, auth_service = make_room()
    # First login auto-creates "alice" with the password used here...
    run(handler(FakeWebSocket([login_message("alice", "secret")]), room, auth_service))

    # ...so a second login attempt with the wrong password must fail.
    socket = FakeWebSocket([login_message("alice", "wrong")])
    run(handler(socket, room, auth_service))

    msg_type, payload = decoded(socket)[0]
    assert msg_type == protocol.MSG_LOGIN_ERROR
    assert payload == {"reason": "invalid username or password"}
    assert socket.closed


def test_first_time_username_auto_creates_an_account_at_initial_rating():
    room, auth_service = make_room()
    socket = FakeWebSocket([login_message("alice")])
    run(handler(socket, room, auth_service))

    msg_type, payload = decoded(socket)[0]
    assert msg_type == protocol.MSG_LOGIN_OK
    assert payload["rating"] == 1200


# --- move/jump/promote dispatch ---

def test_move_message_is_decoded_and_forwarded_to_the_room():
    room, auth_service = make_room()
    socket = FakeWebSocket([
        login_message("alice"),
        protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "b2"}),
    ])
    run(handler(socket, room, auth_service))

    types = [msg_type for msg_type, _ in decoded(socket)]
    assert protocol.MSG_MOVE_STARTED in types


def test_jump_message_is_decoded_and_forwarded_to_the_room():
    room, auth_service = make_room()
    socket = FakeWebSocket([
        login_message("alice"),
        protocol.encode(protocol.MSG_JUMP, {"square": "a1"}),
    ])
    run(handler(socket, room, auth_service))

    move_started = [payload for msg_type, payload in decoded(socket) if msg_type == protocol.MSG_MOVE_STARTED]
    assert move_started == [{"color": "w", "kind": "K", "from": "a1", "to": "a1", "duration_ms": 1000}]


def test_dispatch_promote_message_forwards_a_decoded_square_to_the_room():
    # _dispatch is tested directly (rather than round-tripped through
    # handler()) because promoting requires the pawn's move to actually
    # settle first (room.tick_once()), and handler() has no opportunity to
    # tick between two back-to-back queued FakeWebSocket messages.
    board_lines = [". . .", "wP . ."]
    _auth_service, rating_service, _session = make_services()
    room = Room(rating_service=rating_service, board_lines=board_lines, time_source=lambda: 0.0)
    socket = FakeWebSocket([])
    room.add_player(socket, "alice")
    run(room.handle_move(socket, 1, 0, 0, 0))
    room._time_source = lambda: 1.0
    run(room.tick_once())

    run(_dispatch(room, socket, protocol.MSG_PROMOTE, {"square": "a2", "piece_type": "R"}))

    assert room._engine.board().get(0, 0).kind == "R"


def test_a_black_socket_cannot_move_a_white_piece_via_the_full_dispatch_path():
    room, auth_service = make_room()
    white_socket = FakeWebSocket()
    room.add_player(white_socket, "alice")  # white owns wK at a1 (SMALL_BOARD)

    black_socket = FakeWebSocket([
        login_message("bob"),
        protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "b2"}),  # bob tries to move wK
    ])
    run(handler(black_socket, room, auth_service))

    assert room._engine.board().get(2, 0).color == "w"  # wK unmoved
    types = [msg_type for msg_type, _ in decoded(black_socket)]
    assert protocol.MSG_MOVE_STARTED not in types


def test_malformed_message_after_login_is_ignored_not_fatal():
    room, auth_service = make_room()
    socket = FakeWebSocket([login_message("alice"), "not json", protocol.encode(protocol.MSG_JUMP, {"square": "a1"})])
    run(handler(socket, room, auth_service))

    types = [msg_type for msg_type, _ in decoded(socket)]
    assert protocol.MSG_MOVE_STARTED in types  # the jump after the bad message still went through