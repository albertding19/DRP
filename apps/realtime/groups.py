"""Channel group naming helpers — keeps group names consistent across the codebase."""

from __future__ import annotations

FEED_GROUP = "feed"


def post_group(post_id: int) -> str:
    return f"post_{post_id}"
