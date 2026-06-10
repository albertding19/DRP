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

from .groups import FEED_GROUP, matchmaking_group, post_group, signin_group


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


class MatchmakingConsumer(AsyncJsonWebsocketConsumer):
    """Per-user channel for body-double matchmaking notifications.

    The waiting page / schedule page / dashboard connect to
    `/ws/matchmaking/<user_id>/` and listen for:
      - match_found       → a session is live; carries the room URL
      - booking_matched   → a scheduled booking found a partner
      - booking_cancelled → a matched partner cancelled; booking re-opened

    Authorisation: trusts the URL kwarg. In a hostile threat model we'd
    cross-check `self.scope["user"]`, but the same nickname-based auth
    invariants from the rest of the app apply: room access is gated by
    the room view's participant check, so the worst a forged WS gives
    you is the knowledge that someone with that user_id got matched,
    not the room itself.
    """

    async def connect(self) -> None:
        try:
            self.user_id = int(self.scope["url_route"]["kwargs"]["user_id"])
        except (KeyError, ValueError, TypeError):
            await self.close(code=4000)
            return
        self.group = matchmaking_group(self.user_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:  # noqa: ARG002
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def match_found(self, event: dict) -> None:
        await self.send_json({"type": "match_found", "payload": event["payload"]})

    async def booking_matched(self, event: dict) -> None:
        await self.send_json({"type": "booking_matched", "payload": event["payload"]})

    async def booking_cancelled(self, event: dict) -> None:
        await self.send_json({"type": "booking_cancelled", "payload": event["payload"]})


class SignInConsumer(AsyncJsonWebsocketConsumer):
    """Per-magic-link channel for the check-email page.

    The browser that requested a sign-in / claim / email-change link
    connects to `/ws/signin/<token_id>/` and receives one event type —
    `signin_redeemed` — the instant the link is clicked anywhere (other
    tab, other device). The poll on the same page stays as the fallback.

    Authorisation: trusts the URL kwarg, like `MatchmakingConsumer`.
    Token pks are guessable ints, so the event deliberately carries NO
    payload — the page re-checks state via the session-gated poll
    endpoint rather than trusting the push. A snooper on someone else's
    group learns only that some token got redeemed.
    """

    async def connect(self) -> None:
        try:
            self.token_id = int(self.scope["url_route"]["kwargs"]["token_id"])
        except (KeyError, ValueError, TypeError):
            await self.close(code=4000)
            return
        self.group = signin_group(self.token_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:  # noqa: ARG002
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def signin_redeemed(self, event: dict) -> None:
        await self.send_json({"type": "signin_redeemed", "payload": event["payload"]})
