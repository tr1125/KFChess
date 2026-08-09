import asyncio
import json

from kungfu_chess.model.piece import PieceState
from server.rooms import Room
from server import config, db, protocol, rating


# One king plus one pawn per color - NOT bare King-vs-King, so Stage 3's
# automatic K-v-K draw detection (see rooms.py's _drain_and_publish)
# never fires for these tests, which are about move dispatch/color
# enforcement/timing, not draw logic. (0,0)/(2,0)/(1,1) keep their
# original roles - only the two pawns at column 2 are new.
SMALL_BOARD = [
    "bK . bP",
    ". . .",
    "wK . wP",
]


def make_rating_service():
    """A real RatingService over a fresh in-memory SQLAlchemy session -
    the DI seam this project uses instead of a hand-rolled fake (see
    KFChess_Server_Plan.md Sec 8)."""
    session = db.create_session_factory("sqlite:///:memory:")()
    return rating.RatingService(session), session


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, raw_message):
        self.sent.append(raw_message)


def decoded(fake_socket):
    return [protocol.decode(raw) for raw in fake_socket.sent]


def run(coro):
    return asyncio.run(coro)


def make_room(board_lines=None):
    rating_service, _session = make_rating_service()
    return Room(
        rating_service=rating_service,
        board_lines=board_lines if board_lines is not None else SMALL_BOARD,
        time_source=lambda: 0.0,
    )


# --- connection/color assignment ---

def test_first_player_is_assigned_white():
    room = make_room()
    assert room.add_player(FakeWebSocket(), "alice") == "w"


def test_second_player_is_assigned_black():
    room = make_room()
    room.add_player(FakeWebSocket(), "alice")
    assert room.add_player(FakeWebSocket(), "bob") == "b"


def test_third_player_is_rejected():
    room = make_room()
    room.add_player(FakeWebSocket(), "alice")
    room.add_player(FakeWebSocket(), "bob")
    assert room.add_player(FakeWebSocket(), "carol") is None


def test_is_full_reflects_connection_count():
    room = make_room()
    assert not room.is_full()
    room.add_player(FakeWebSocket(), "alice")
    assert not room.is_full()
    room.add_player(FakeWebSocket(), "bob")
    assert room.is_full()


def test_remove_player_frees_a_color_slot():
    room = make_room()
    white_socket = FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(FakeWebSocket(), "bob")
    room.remove_player(white_socket)
    assert not room.is_full()
    assert room.add_player(FakeWebSocket(), "carol") == "w"


# --- announce_game_started ---

def test_announce_game_started_sends_game_started_and_initial_state_to_both():
    room = make_room()
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.announce_game_started())

    for socket in (white_socket, black_socket):
        msg_type, payload = decoded(socket)[0]
        assert msg_type == protocol.MSG_GAME_STARTED
        assert payload == {"white": "alice", "black": "bob", "room_id": config.ROOM_ID}

        state_type, state_payload = decoded(socket)[1]
        assert state_type == protocol.MSG_STATE
        assert state_payload["board"][0][0] == {"color": "b", "kind": "K", "state": "IDLE"}


# --- handle_move / handle_jump / handle_promote ---

def test_handle_move_broadcasts_move_started_to_both_players():
    room = make_room()
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.handle_move(white_socket, 2, 0, 1, 1))  # wK (2,0) -> (1,1)

    for socket in (white_socket, black_socket):
        msg_type, payload = decoded(socket)[0]
        assert msg_type == protocol.MSG_MOVE_STARTED
        assert payload["color"] == "w"
        assert payload["from"] == "a1"
        assert payload["to"] == "b2"


def test_handle_jump_broadcasts_move_started():
    room = make_room()
    socket = FakeWebSocket()
    room.add_player(socket, "alice")

    run(room.handle_jump(socket, 2, 0))

    msg_type, payload = decoded(socket)[0]
    assert msg_type == protocol.MSG_MOVE_STARTED
    assert payload == {"color": "w", "kind": "K", "from": "a1", "to": "a1", "duration_ms": 1000}


def test_settling_a_move_broadcasts_state():
    room = make_room()
    socket = FakeWebSocket()
    room.add_player(socket, "alice")

    run(room.handle_move(socket, 2, 0, 1, 1))
    run(room.tick_once())  # nothing settles yet - room's clock hasn't advanced

    socket.sent.clear()
    room._time_source = lambda: 1.0  # 1000ms later - the leg is now due
    run(room.tick_once())

    types = [msg_type for msg_type, _ in decoded(socket)]
    assert protocol.MSG_STATE in types


# --- color enforcement ---

def test_handle_move_is_rejected_when_the_socket_does_not_own_the_piece():
    room = make_room()
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.handle_move(black_socket, 2, 0, 1, 1))  # black tries to move wK

    assert room._engine.board().get(2, 0).color == "w"  # unmoved
    assert black_socket.sent == []
    assert white_socket.sent == []


def test_handle_jump_is_rejected_when_the_socket_does_not_own_the_piece():
    room = make_room()
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.handle_jump(white_socket, 0, 0))  # white tries to jump bK

    assert room._engine.board().get(0, 0).state == PieceState.IDLE
    assert white_socket.sent == []


def test_handle_promote_is_rejected_when_the_socket_does_not_own_the_piece():
    board_lines = [". . .", "wP . ."]
    rating_service, _session = make_rating_service()
    room = Room(rating_service=rating_service, board_lines=board_lines, time_source=lambda: 0.0)
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.handle_move(white_socket, 1, 0, 0, 0))
    room._time_source = lambda: 1.0
    run(room.tick_once())

    run(room.handle_promote(black_socket, 0, 0, "R"))  # black tries to override white's promotion

    assert room._engine.board().get(0, 0).kind == "Q"  # unchanged (still the auto-promoted default)


def test_handle_move_is_rejected_for_a_socket_that_is_not_a_player_at_all():
    room = make_room()
    room.add_player(FakeWebSocket(), "alice")
    stranger = FakeWebSocket()

    run(room.handle_move(stranger, 2, 0, 1, 1))

    assert room._engine.board().get(2, 0).color == "w"  # unmoved
    assert stranger.sent == []


def test_handle_move_is_rejected_when_the_source_square_is_empty():
    room = make_room()
    white_socket = FakeWebSocket()
    room.add_player(white_socket, "alice")

    run(room.handle_move(white_socket, 1, 1, 1, 0))  # (1,1) is empty on SMALL_BOARD

    assert white_socket.sent == []


# --- tick_once (real-time clock) ---

def test_tick_once_advances_the_engine_by_elapsed_real_time():
    rating_service, _session = make_rating_service()
    room = Room(rating_service=rating_service, board_lines=SMALL_BOARD, time_source=lambda: 0.0)
    socket = FakeWebSocket()
    room.add_player(socket, "alice")
    run(room.handle_move(socket, 2, 0, 1, 1))

    room._time_source = lambda: 1.0
    run(room.tick_once())

    piece = room._engine.board().get(1, 1)
    assert piece is not None
    assert piece.state == PieceState.LONG_REST


def test_tick_once_does_nothing_when_no_time_has_elapsed():
    rating_service, _session = make_rating_service()
    room = Room(rating_service=rating_service, board_lines=SMALL_BOARD, time_source=lambda: 5.0)
    socket = FakeWebSocket()
    room.add_player(socket, "alice")
    run(room.tick_once())
    assert socket.sent == []


# --- rest-elapsed state sync (regression: pieces stuck LONG_REST client-side) ---

def test_state_is_broadcast_again_once_a_settled_pieces_rest_elapses_with_nothing_else_happening():
    """Reproduces the reported "stuck piece" bug: with no OTHER event
    anywhere on the board, a piece's own rest naturally elapsing must
    still trigger a fresh `state` broadcast (see engine/game_engine.py's
    "rest_over" event) - otherwise a networked client's cached snapshot
    would keep showing it as LONG_REST forever, unable to reselect it,
    until some unrelated piece happened to move.
    """
    room = make_room()
    socket = FakeWebSocket()
    room.add_player(socket, "alice")

    run(room.handle_move(socket, 2, 0, 1, 1))  # wK a1 -> b2
    room._time_source = lambda: 1.0  # settles into LONG_REST (1000ms)
    run(room.tick_once())
    socket.sent.clear()

    room._time_source = lambda: 2.0  # LONG_REST (another 1000ms) now elapses
    run(room.tick_once())

    state_messages = [payload for msg_type, payload in decoded(socket) if msg_type == protocol.MSG_STATE]
    assert len(state_messages) == 1
    assert state_messages[0]["board"][1][1]["state"] == "IDLE"


# --- game_ended broadcast mapping ---

def test_game_ended_maps_winner_to_result_string():
    board_lines = [
        "wR . bK",
    ]
    rating_service, session = make_rating_service()
    db.create_user(session, "alice", "hash")
    db.create_user(session, "bob", "hash")
    room = Room(rating_service=rating_service, board_lines=board_lines, time_source=lambda: 0.0)
    white_socket, black_socket = FakeWebSocket(), FakeWebSocket()
    room.add_player(white_socket, "alice")
    room.add_player(black_socket, "bob")

    run(room.handle_move(white_socket, 0, 0, 0, 2))
    room._time_source = lambda: 2.0
    run(room.tick_once())

    messages = decoded(white_socket)
    game_ended = [payload for msg_type, payload in messages if msg_type == protocol.MSG_GAME_ENDED]
    # Both accounts start at INITIAL_RATING (1200) - equal ratings, so a
    # win always moves each side by exactly K_FACTOR/2 (16).
    assert game_ended == [{
        "result": "white_wins", "reason": "capture",
        "rating_changes": {"white": 1216, "black": 1184},
    }]


def test_a_non_king_capture_that_leaves_only_kings_ends_the_game_as_a_draw():
    """Reproduces Stage 3's stated acceptance criterion end-to-end: a
    capture that removes the last non-king piece (NOT a king capture,
    so GameEngine's own ends_game_on_capture path never fires) must
    still trigger an automatic draw, purely via Room's normal
    handle_move/tick_once path - no manual force_draw() call here.
    """
    board_lines = [
        "bK . .",
        ". . .",
        ". wK bP",
    ]
    rating_service, session = make_rating_service()
    db.create_user(session, "alice", "hash")
    db.create_user(session, "bob", "hash")
    room = Room(rating_service=rating_service, board_lines=board_lines, time_source=lambda: 0.0)
    socket = FakeWebSocket()
    room.add_player(socket, "alice")
    room.add_player(FakeWebSocket(), "bob")

    run(room.handle_move(socket, 2, 1, 2, 2))  # wK captures bP - not a king capture
    room._time_source = lambda: 2.0
    run(room.tick_once())

    messages = decoded(socket)
    game_ended = [payload for msg_type, payload in messages if msg_type == protocol.MSG_GAME_ENDED]
    assert game_ended == [{
        "result": "draw", "reason": "insufficient_material",
        "rating_changes": {"white": 1200, "black": 1200},
    }]