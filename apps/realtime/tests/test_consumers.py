"""Consumer tests via Channels' WebsocketCommunicator + InMemoryChannelLayer."""

from __future__ import annotations

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from config.asgi import application


@pytest.mark.asyncio
async def test_feed_consumer_connect_and_receive_post_created() -> None:
    comm = WebsocketCommunicator(application, "/ws/feed/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "feed",
        {"type": "post_created", "payload": {"id": 1, "html": "<li>fake</li>"}},
    )

    msg = await comm.receive_json_from()
    assert msg == {"type": "post_created", "payload": {"id": 1, "html": "<li>fake</li>"}}

    await comm.disconnect()


@pytest.mark.asyncio
async def test_feed_consumer_score_changed() -> None:
    comm = WebsocketCommunicator(application, "/ws/feed/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "feed",
        {
            "type": "score_changed",
            "payload": {"target_type": "post", "id": 42, "score": 7},
        },
    )

    msg = await comm.receive_json_from()
    assert msg["type"] == "score_changed"
    assert msg["payload"]["id"] == 42
    assert msg["payload"]["score"] == 7

    await comm.disconnect()


@pytest.mark.asyncio
async def test_post_consumer_subscribes_to_post_group() -> None:
    comm = WebsocketCommunicator(application, "/ws/posts/123/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "post_123",
        {
            "type": "comment_created",
            "payload": {"id": 5, "post_id": 123, "html": "<article>c</article>"},
        },
    )

    msg = await comm.receive_json_from()
    assert msg["type"] == "comment_created"
    assert msg["payload"]["post_id"] == 123

    await comm.disconnect()


@pytest.mark.asyncio
async def test_post_consumer_ignores_other_posts() -> None:
    """A consumer subscribed to post_123 should NOT receive post_456 events."""
    comm = WebsocketCommunicator(application, "/ws/posts/123/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "post_456",
        {"type": "score_changed", "payload": {"target_type": "post", "id": 456, "score": 1}},
    )

    # Should time out — no message expected
    assert await comm.receive_nothing(timeout=0.5)

    await comm.disconnect()


@pytest.mark.asyncio
async def test_matchmaking_consumer_receives_match_event() -> None:
    """A waiting user connects to /ws/matchmaking/<their-id>/ and receives
    the `match_found` event when their group is signalled."""
    comm = WebsocketCommunicator(application, "/ws/matchmaking/42/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "matchmaking_42",
        {
            "type": "match_found",
            "payload": {"session_id": 7, "room_url": "/body-double/room/7/"},
        },
    )

    msg = await comm.receive_json_from()
    assert msg["type"] == "match_found"
    assert msg["payload"]["session_id"] == 7
    assert msg["payload"]["room_url"] == "/body-double/room/7/"

    await comm.disconnect()


@pytest.mark.asyncio
async def test_matchmaking_consumer_ignores_other_users() -> None:
    """Subscriber for user 42 must not receive user 99's match events."""
    comm = WebsocketCommunicator(application, "/ws/matchmaking/42/")
    connected, _ = await comm.connect()
    assert connected

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "matchmaking_99",
        {"type": "match_found", "payload": {"session_id": 1, "room_url": "/x/"}},
    )

    assert await comm.receive_nothing(timeout=0.5)
    await comm.disconnect()
