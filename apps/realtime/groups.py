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


def signin_group(token_id: int) -> str:
    """Per-magic-link group for the check-email page. The browser that
    requested the link subscribes; the verify view signals the group the
    moment the link is redeemed (possibly on another device)."""
    return f"signin_{token_id}"
