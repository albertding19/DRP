"""WebSocket consumers.

`FeedConsumer` is subscribed by any client viewing `/`. It handles two
events sent from the broadcast layer:
  - post_created   → push the rendered post card HTML to all viewers
  - score_changed  → push the new score for a post in the feed

`PostConsumer` is subscribed by any client viewing `/posts/<id>/`. It
handles:
  - comment_created → push the rendered comment HTML
  - score_changed   → push the new score for either the post or one of
                       its comments

Neither consumer reads from the channel layer on the client's behalf —
they only proxy server-sent group_send events out to the WebSocket.

Authentication isn't enforced (read-only events with no user-identifiable
data leak), but in production we'd want to refuse unauthenticated
connections via `self.scope['user']`.
"""

from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .groups import FEED_GROUP, post_group


class FeedConsumer(AsyncJsonWebsocketConsumer):
    """Subscribers see new posts + live vote-count updates in the feed."""

    async def connect(self) -> None:
        await self.channel_layer.group_add(FEED_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:  # noqa: ARG002
        await self.channel_layer.group_discard(FEED_GROUP, self.channel_name)

    # ----- handlers — names match the `type` key in group_send envelopes -----

    async def post_created(self, event: dict) -> None:
        await self.send_json({"type": "post_created", "payload": event["payload"]})

    async def score_changed(self, event: dict) -> None:
        await self.send_json({"type": "score_changed", "payload": event["payload"]})

    async def post_hidden(self, event: dict) -> None:
        await self.send_json({"type": "post_hidden", "payload": event["payload"]})


class PostConsumer(AsyncJsonWebsocketConsumer):
    """Subscribers on a single post see new comments + vote updates."""

    async def connect(self) -> None:
        try:
            self.post_id = int(self.scope["url_route"]["kwargs"]["post_id"])
        except (KeyError, ValueError, TypeError):
            await self.close(code=4000)
            return
        self.group = post_group(self.post_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:  # noqa: ARG002
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def comment_created(self, event: dict) -> None:
        await self.send_json({"type": "comment_created", "payload": event["payload"]})

    async def score_changed(self, event: dict) -> None:
        await self.send_json({"type": "score_changed", "payload": event["payload"]})

    async def comment_hidden(self, event: dict) -> None:
        await self.send_json({"type": "comment_hidden", "payload": event["payload"]})

    async def post_hidden(self, event: dict) -> None:
        await self.send_json({"type": "post_hidden", "payload": event["payload"]})
