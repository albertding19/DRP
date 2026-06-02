"""Channel group naming helpers — keeps group names consistent across the codebase."""

from __future__ import annotations

FEED_GROUP = "feed"


def post_group(post_id: int) -> str:
    return f"post_{post_id}"


def matchmaking_group(user_id: int) -> str:
    """Per-user group for body-double matchmaking events. Each waiting
    user joins their own group via `MatchmakingConsumer`; the broadcaster
    targets the partner's group when a match is made."""
    return f"matchmaking_{user_id}"
