"""KFChess WebSocket server entry point (Stage 2: single hardcoded room,
exactly two players, no accounts yet - see KFChess_Server_Plan.md).

Repo: https://github.com/tr1125/KFChess
"""

import asyncio

import websockets

from kungfu_chess.model.position import parse_square_name

from server import auth, config, db, protocol, rating
from server.rooms import Room


async def _dispatch(room, websocket, msg_type, payload):
    board_height = room.board_height()
    if msg_type == protocol.MSG_MOVE:
        from_pos = parse_square_name(payload["from"], board_height)
        to_pos = parse_square_name(payload["to"], board_height)
        await room.handle_move(websocket, from_pos.row, from_pos.col, to_pos.row, to_pos.col)
    elif msg_type == protocol.MSG_JUMP:
        position = parse_square_name(payload["square"], board_height)
        await room.handle_jump(websocket, position.row, position.col)
    elif msg_type == protocol.MSG_PROMOTE:
        position = parse_square_name(payload["square"], board_height)
        await room.handle_promote(websocket, position.row, position.col, payload["piece_type"])


async def _login(websocket, room, auth_service):
    """Read the connection's first message, expect a `login` envelope,
    verify it against `auth_service`, and register it with `room`.
    Returns the assigned color ('w'/'b'), or None if login/auth failed or
    the room was full (the caller should stop, the connection has
    already been closed).
    """
    try:
        raw = await websocket.recv()
    except websockets.ConnectionClosed:
        return None

    try:
        msg_type, payload = protocol.decode(raw)
    except protocol.ProtocolError:
        await websocket.close(code=1002, reason="expected a login message")
        return None

    if msg_type != protocol.MSG_LOGIN:
        await websocket.close(code=1002, reason="expected a login message")
        return None

    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        await websocket.send(
            protocol.encode(protocol.MSG_LOGIN_ERROR, {"reason": config.LOGIN_FAILURE_REASON})
        )
        await websocket.close()
        return None

    try:
        player_rating = auth_service.login(username, password)
    except auth.AuthError:
        await websocket.send(
            protocol.encode(protocol.MSG_LOGIN_ERROR, {"reason": config.LOGIN_FAILURE_REASON})
        )
        await websocket.close()
        return None

    color = room.add_player(websocket, username)
    if color is None:
        await websocket.send(protocol.encode(protocol.MSG_ERROR, {"reason": "room_full"}))
        await websocket.close()
        return None

    await websocket.send(
        protocol.encode(protocol.MSG_LOGIN_OK, {"username": username, "rating": player_rating})
    )
    return color


async def handler(websocket, room, auth_service):
    color = await _login(websocket, room, auth_service)
    if color is None:
        return

    if room.is_full():
        await room.announce_game_started()

    try:
        async for raw in websocket:
            try:
                msg_type, payload = protocol.decode(raw)
            except protocol.ProtocolError:
                continue
            await _dispatch(room, websocket, msg_type, payload)
    except websockets.ConnectionClosed:
        pass
    finally:
        room.remove_player(websocket)


async def main(host=config.WS_HOST, port=config.WS_PORT):
    # auth_service and rating_service share one session, since both read
    # and write the same users table (see server/db.py).
    session = db.create_session_factory()()
    auth_service = auth.AuthService(session)
    rating_service = rating.RatingService(session)
    room = Room(rating_service=rating_service)
    async with websockets.serve(lambda websocket: handler(websocket, room, auth_service), host, port):
        await room.tick_loop()


if __name__ == "__main__":
    asyncio.run(main())