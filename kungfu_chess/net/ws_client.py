"""The real networked-client transport (see KFChess_Server_Plan.md
Stage 2): owns a background thread running its own asyncio event loop and
the actual `websockets` connection, so the existing synchronous, blocking
cv2-based GameLoop.run() (driver/game_loop.py) never has to become
asyncio-aware. Decoded (type, payload) messages are pushed onto a plain
thread-safe queue.Queue that RemoteEngine.wait() drains every tick;
outbound sends are handed to the background loop via
asyncio.run_coroutine_threadsafe.

This class is intentionally thin glue over a real socket/thread and is
exercised by the integration test (server/tests/integration/) rather than
heavily unit-tested in isolation - RemoteEngine (the class with actual
decision logic) is unit-tested against a plain queue.Queue + fake sender
instead, per KFChess_Server_Plan.md Sec 8's DI mandate.
"""

import asyncio
import queue
import threading

import websockets

from server import protocol


class WsClient:
    def __init__(self, uri):
        self.incoming = queue.Queue()
        self._uri = uri
        self._loop = None
        self._websocket = None
        self._connect_error = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._connect_error is not None:
            raise self._connect_error

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_listen())

    async def _connect_and_listen(self):
        try:
            async with websockets.connect(self._uri) as websocket:
                self._websocket = websocket
                self._ready.set()
                async for raw in websocket:
                    try:
                        msg_type, payload = protocol.decode(raw)
                    except protocol.ProtocolError:
                        continue
                    self.incoming.put((msg_type, payload))
        except Exception as error:  # surfaced to the constructor via _connect_error
            self._connect_error = error
            self._ready.set()

    def send(self, msg_type, payload):
        raw = protocol.encode(msg_type, payload)
        asyncio.run_coroutine_threadsafe(self._websocket.send(raw), self._loop)

    def close(self):
        if self._websocket is not None:
            asyncio.run_coroutine_threadsafe(self._websocket.close(), self._loop)