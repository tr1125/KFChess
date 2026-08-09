"""End-to-end test against a real websockets server and two real
websockets client connections (the one place this project uses a real
socket - unit tests elsewhere use injected fake transports/clocks, per
KFChess_Server_Plan.md Sec 8). Proves the whole Stage 2 stack wired
together: login handshake, color assignment, move dispatch, real-time
settlement via Room's tick loop, and game-ended broadcast.
"""

import asyncio

import websockets

from kungfu_chess.net.remote_engine import RemoteEngine
from kungfu_chess.net.ws_client import WsClient

from server import auth, db, protocol, rating
from server.rooms import Room
from server.ws_server import handler

BOARD = [
    "wR . bK",
]

# Both accounts start at INITIAL_RATING (1200) with equal ratings, so a
# white win always moves them by exactly K_FACTOR/2 (16) regardless of
# the base rating - see server/tests/unit/test_rating.py for the
# general worked example.
WHITE_WINS_RATING_CHANGES = {"white": 1216, "black": 1184}


def _new_services():
    """One shared in-memory session for auth_service/rating_service, per
    KFChess_Server_Plan.md Sec 8's DI mandate - a real SQLAlchemy engine,
    not a hand-rolled fake.
    """
    session = db.create_session_factory("sqlite:///:memory:")()
    return auth.AuthService(session), rating.RatingService(session)


def _login_payload(username):
    return {"username": username, "password": "secret"}


async def _recv_until(websocket, target_type):
    while True:
        raw = await websocket.recv()
        msg_type, payload = protocol.decode(raw)
        if msg_type == target_type:
            return payload


async def _poll_until(predicate, engine=None, timeout=5, interval=0.05):
    """Poll `predicate()` (optionally draining `engine`'s queue first)
    until it's truthy or `timeout` elapses - used to wait on RemoteEngine/
    WsClient's real background-thread transport, which is drained
    non-blockingly rather than awaited directly.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if engine is not None:
            engine.wait(0)
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("timed out polling for the expected condition")


async def _play_to_game_ended():
    auth_service, rating_service = _new_services()
    room = Room(rating_service=rating_service, board_lines=BOARD)
    async with websockets.serve(lambda ws: handler(ws, room, auth_service), "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        tick_task = asyncio.create_task(room.tick_loop())
        try:
            uri = f"ws://localhost:{port}"
            async with websockets.connect(uri) as white_ws, websockets.connect(uri) as black_ws:
                await white_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("alice")))
                await black_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("bob")))

                await _recv_until(white_ws, protocol.MSG_STATE)
                await _recv_until(black_ws, protocol.MSG_STATE)

                await white_ws.send(protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "c1"}))

                return await _recv_until(white_ws, protocol.MSG_GAME_ENDED)
        finally:
            tick_task.cancel()


def test_two_real_websocket_clients_play_a_capture_to_game_ended():
    result = asyncio.run(asyncio.wait_for(_play_to_game_ended(), timeout=8))
    assert result == {
        "result": "white_wins", "reason": "capture", "rating_changes": WHITE_WINS_RATING_CHANGES,
    }


async def _third_connection_is_rejected():
    auth_service, rating_service = _new_services()
    room = Room(rating_service=rating_service, board_lines=BOARD)
    async with websockets.serve(lambda ws: handler(ws, room, auth_service), "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        tick_task = asyncio.create_task(room.tick_loop())
        try:
            uri = f"ws://localhost:{port}"
            async with websockets.connect(uri) as white_ws, websockets.connect(uri) as black_ws:
                await white_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("alice")))
                await black_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("bob")))
                await _recv_until(white_ws, protocol.MSG_STATE)
                await _recv_until(black_ws, protocol.MSG_STATE)

                async with websockets.connect(uri) as third_ws:
                    await third_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("carol")))
                    msg_type, payload = protocol.decode(await third_ws.recv())
                    return msg_type, payload
        finally:
            tick_task.cancel()


def test_a_third_real_connection_is_rejected_cleanly():
    msg_type, payload = asyncio.run(asyncio.wait_for(_third_connection_is_rejected(), timeout=8))
    assert msg_type == protocol.MSG_ERROR
    assert payload == {"reason": "room_full"}


async def _black_tries_to_move_white_piece():
    auth_service, rating_service = _new_services()
    room = Room(rating_service=rating_service, board_lines=BOARD)
    async with websockets.serve(lambda ws: handler(ws, room, auth_service), "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        tick_task = asyncio.create_task(room.tick_loop())
        try:
            uri = f"ws://localhost:{port}"
            async with websockets.connect(uri) as white_ws, websockets.connect(uri) as black_ws:
                await white_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("alice")))
                await black_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("bob")))
                await _recv_until(white_ws, protocol.MSG_STATE)
                await _recv_until(black_ws, protocol.MSG_STATE)

                # bob (black) tries to move the white rook - must be silently
                # rejected, not applied and not broadcast to anyone.
                await black_ws.send(protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "c1"}))

                # Prove nothing happened: white can still move that same
                # piece itself afterward, ending the game normally.
                await white_ws.send(protocol.encode(protocol.MSG_MOVE, {"from": "a1", "to": "c1"}))
                return await _recv_until(white_ws, protocol.MSG_GAME_ENDED)
        finally:
            tick_task.cancel()


def test_a_black_socket_cannot_move_a_white_piece_over_the_real_network():
    result = asyncio.run(asyncio.wait_for(_black_tries_to_move_white_piece(), timeout=8))
    assert result == {
        "result": "white_wins", "reason": "capture", "rating_changes": WHITE_WINS_RATING_CHANGES,
    }


async def _play_via_the_real_client_transport():
    """Drives White through the actual app_ui.py client stack (WsClient's
    background thread + RemoteEngine), not just a raw websockets client -
    the other tests above prove the server side; this one proves
    net/ws_client.py and net/remote_engine.py integrate correctly against
    a real socket too.
    """
    auth_service, rating_service = _new_services()
    room = Room(rating_service=rating_service, board_lines=BOARD)
    async with websockets.serve(lambda ws: handler(ws, room, auth_service), "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        tick_task = asyncio.create_task(room.tick_loop())
        try:
            uri = f"ws://localhost:{port}"
            # WsClient's constructor blocks the calling thread until its
            # background thread finishes connecting - run it in a worker
            # thread so it doesn't freeze this test's own event loop
            # (which the server needs in order to accept that connection).
            white_client = await asyncio.to_thread(WsClient, uri)
            white_engine = RemoteEngine(white_client.send, white_client.incoming)
            white_client.send(protocol.MSG_LOGIN, _login_payload("alice"))

            # White's login is dispatched via a background thread
            # (asyncio.run_coroutine_threadsafe), so it isn't guaranteed to
            # reach the server before a second connection's login otherwise
            # would - wait for it to be acknowledged first so join order
            # (and thus color assignment) is deterministic.
            await _poll_until(
                lambda: protocol.MSG_LOGIN_OK in white_engine.status, engine=white_engine
            )

            async with websockets.connect(uri) as black_ws:
                await black_ws.send(protocol.encode(protocol.MSG_LOGIN, _login_payload("bob")))
                await _recv_until(black_ws, protocol.MSG_STATE)

                def board_is_ready():
                    try:
                        white_engine.game_state().board_rows()
                        return True
                    except AttributeError:
                        return False

                await _poll_until(board_is_ready, engine=white_engine)

                white_engine.request_move(0, 0, 0, 2)  # wR a1 -> c1, per BOARD

                await _poll_until(
                    lambda: protocol.MSG_GAME_ENDED in white_engine.status, engine=white_engine
                )
                return white_engine.status[protocol.MSG_GAME_ENDED]
        finally:
            tick_task.cancel()


def test_the_real_client_transport_plays_a_capture_to_game_ended():
    result = asyncio.run(asyncio.wait_for(_play_via_the_real_client_transport(), timeout=8))
    assert result == {
        "result": "white_wins", "reason": "capture", "rating_changes": WHITE_WINS_RATING_CHANGES,
    }