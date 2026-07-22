import asyncio

from server.bus import EventBus


def test_publish_invokes_subscriber_with_payload():
    bus = EventBus()
    received = []

    async def on_move_made(payload):
        received.append(payload)

    bus.subscribe("move_made", on_move_made)
    asyncio.run(bus.publish("move_made", {"from": "e2", "to": "e4"}))

    assert received == [{"from": "e2", "to": "e4"}]


def test_publish_invokes_all_subscribers_on_the_same_topic():
    bus = EventBus()
    calls = []

    async def first(payload):
        calls.append(("first", payload))

    async def second(payload):
        calls.append(("second", payload))

    bus.subscribe("game_started", first)
    bus.subscribe("game_started", second)
    asyncio.run(bus.publish("game_started", {"board_width": 8}))

    assert calls == [
        ("first", {"board_width": 8}),
        ("second", {"board_width": 8}),
    ]


def test_publish_to_topic_with_no_subscribers_does_not_raise():
    bus = EventBus()
    asyncio.run(bus.publish("score_updated", {"scores": {"w": 0, "b": 0}}))


def test_subscribers_on_other_topics_are_not_invoked():
    bus = EventBus()
    received = []

    async def on_game_ended(payload):
        received.append(payload)

    bus.subscribe("game_ended", on_game_ended)
    asyncio.run(bus.publish("move_made", {"from": "e2", "to": "e4"}))

    assert received == []