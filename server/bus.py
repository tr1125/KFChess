"""Minimal async pub/sub bus: subscribers register per topic, publish awaits
each of them in turn. One EventBus instance per game (later: per room, see
KFChess_Server_Plan.md Stage 1). This module owns no bridging to synchronous
callers - a synchronous caller wanting to publish something is responsible
for running the coroutine itself (e.g. via asyncio.run()), same as any other
asyncio API.
"""


class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, topic, callback):
        self._subscribers.setdefault(topic, []).append(callback)

    async def publish(self, topic, payload):
        for callback in self._subscribers.get(topic, []):
            await callback(payload)
