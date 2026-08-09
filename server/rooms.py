"""Room: the server-side composition root (replaces the old local wiring
that used to live in app_ui.py - see KFChess_Server_Plan.md Stage 2). Owns
the one real EventBus/GameEngine/Controller for a game, the connected
sockets, and the real-time tick that advances the engine's otherwise
pull-based clock.

Stage 2 has exactly one hardcoded room (no room management yet - Stage 5's
job), so there is no room_id -> Room mapping here yet; ws_server.py owns a
single Room instance directly.
"""

import asyncio
import time

from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.io.state_codec import to_wire_state
from kungfu_chess.rules.piece_rules import default_piece_rules
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.controller import Controller

from server import config, protocol, rating
from server.bus import EventBus

STANDARD_START = [
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    ". . . . . . . .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
]

# Join order decides color, per KFChess_Server_Plan.md Sec 0 - first
# connection is White, second is Black. Deliberately not configurable/
# randomized - "no coin flip anywhere in this project".
JOIN_ORDER_COLORS = ("w", "b")


class Room:
    def __init__(self, rating_service, board_lines=None, time_source=time.monotonic, sleep=None):
        board = parse_board(board_lines if board_lines is not None else STANDARD_START)
        self._bus = EventBus()
        self._engine = GameEngine(board, RuleEngine(default_piece_rules()))
        self._controller = Controller(self._engine)
        self._rating_service = rating_service
        self._time_source = time_source
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._last_tick = time_source()
        self._sockets = {}  # color -> websocket
        self._usernames = {}  # color -> username

        self._bus.subscribe("move_started", self._broadcast_move_started)
        self._bus.subscribe("move_made", self._broadcast_state)
        self._bus.subscribe("score_updated", self._broadcast_state)
        self._bus.subscribe("rest_over", self._broadcast_state)
        self._bus.subscribe("game_ended", self._broadcast_game_ended)

    # --- connection/session management --------------------------------

    def is_full(self):
        return len(self._sockets) >= config.MAX_PLAYERS_PER_ROOM

    def board_height(self):
        """Exposed so ws_server.py can decode wire square names
        (e.g. "e4") into board cells without reaching into the engine
        directly - see model/position.py's parse_square_name."""
        return self._engine.board().height

    def add_player(self, websocket, username):
        """Assign the next free color in join order and register the
        connection. Returns the assigned color ('w'/'b'), or None if the
        room already has MAX_PLAYERS_PER_ROOM connections.
        """
        if self.is_full():
            return None
        color = next(color for color in JOIN_ORDER_COLORS if color not in self._sockets)
        self._sockets[color] = websocket
        self._usernames[color] = username
        return color

    def remove_player(self, websocket):
        for color, sock in list(self._sockets.items()):
            if sock is websocket:
                del self._sockets[color]
                del self._usernames[color]

    def color_for(self, websocket):
        """The color assigned to `websocket`, or None if it isn't a
        registered player of this room (e.g. a spectator, once those
        exist in Stage 5) - used to enforce that a connection can only
        move/jump/promote its own color's pieces (see _owns_piece_at)."""
        for color, sock in self._sockets.items():
            if sock is websocket:
                return color
        return None

    def _owns_piece_at(self, websocket, row, col):
        color = self.color_for(websocket)
        if color is None:
            return False
        board = self._engine.board()
        if not board.in_bounds(row, col):
            return False
        piece = board.get(row, col)
        return piece is not None and piece.color == color

    # --- inbound client messages ----------------------------------------

    async def handle_move(self, websocket, from_row, from_col, to_row, to_col):
        if not self._owns_piece_at(websocket, from_row, from_col):
            return
        self._controller.move_piece(from_row, from_col, to_row, to_col)
        await self._drain_and_publish()

    async def handle_jump(self, websocket, row, col):
        if not self._owns_piece_at(websocket, row, col):
            return
        self._controller.jump_piece(row, col)
        await self._drain_and_publish()

    async def handle_promote(self, websocket, row, col, piece_type):
        if not self._owns_piece_at(websocket, row, col):
            return
        self._controller.choose_promotion(row, col, piece_type)
        await self._drain_and_publish()

    async def announce_game_started(self):
        payload = {
            "white": self._usernames.get("w"),
            "black": self._usernames.get("b"),
            "room_id": config.ROOM_ID,
        }
        await self._send_to_all(protocol.encode(protocol.MSG_GAME_STARTED, payload))
        await self._broadcast_state(None)  # so both clients render the starting position

    # --- real-time engine clock -----------------------------------------

    async def tick_loop(self):
        while True:
            await self._sleep(config.TICK_INTERVAL_MS / 1000)
            await self.tick_once()

    async def tick_once(self):
        """Advance the engine's clock by however much real time elapsed
        since the last tick, then publish whatever settled. Split out
        from tick_loop() so tests can drive exactly one tick at a time
        with an injected time_source, without running the infinite loop.
        """
        now = self._time_source()
        elapsed_ms = int((now - self._last_tick) * 1000)
        self._last_tick = now
        if elapsed_ms <= 0:
            return
        self._controller.wait(elapsed_ms)
        await self._drain_and_publish()

    async def _drain_and_publish(self):
        for topic, payload in self._engine.drain_events():
            await self._bus.publish(topic, payload)

        # After every settle, check for King-vs-King insufficient
        # material (Sec 0's sole automatic draw condition) - deliberately
        # not part of GameEngine/RuleEngine's own settle path (see
        # server/rating.py's module docstring), so this is the one place
        # that decides to end the game that way and drains the resulting
        # game_ended event through the same mechanism as any other.
        if not self._engine.is_game_over() and rating.is_king_vs_king(self._engine.board().rows()):
            self._engine.force_draw()
            for topic, payload in self._engine.drain_events():
                await self._bus.publish(topic, payload)

    # --- bus subscribers -> broadcasts -----------------------------------

    async def _broadcast_move_started(self, payload):
        await self._send_to_all(protocol.encode(protocol.MSG_MOVE_STARTED, payload))

    async def _broadcast_state(self, _payload):
        state_payload = to_wire_state(self._controller.game_state())
        await self._send_to_all(protocol.encode(protocol.MSG_STATE, state_payload))

    async def _broadcast_game_ended(self, payload):
        winner = payload.get("winner")
        if winner is None:
            result, reason = protocol.RESULT_DRAW, protocol.REASON_INSUFFICIENT_MATERIAL
        else:
            result = protocol.RESULT_WHITE_WINS if winner == "w" else protocol.RESULT_BLACK_WINS
            reason = protocol.REASON_CAPTURE

        rating_changes = self._rating_service.finalize_game(
            self._usernames.get("w"), self._usernames.get("b"), result
        )

        await self._send_to_all(
            protocol.encode(
                protocol.MSG_GAME_ENDED,
                {"result": result, "reason": reason, "rating_changes": rating_changes},
            )
        )

    async def _send_to_all(self, raw_message):
        for websocket in list(self._sockets.values()):
            await websocket.send(raw_message)