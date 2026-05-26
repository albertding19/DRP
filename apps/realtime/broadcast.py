"""Public broadcast API — the only module that touches the channel layer.

Other apps emit domain signals and call these functions; they never import
`channels.layers` directly. This is what keeps the import graph one-way:

    apps.posts / comments / votes  →  apps.realtime.broadcast  →  Channels

Consumer implementations land Thu 28 May. Until then these are no-ops in
test/dev (the InMemoryChannelLayer just queues them).
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import FEED_GROUP, post_group


def _send(group: str, event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group, {"type": event_type, "payload": payload})


def broadcast_new_post(post) -> None:  # noqa: ANN001
    _send(FEED_GROUP, "post_created", {"id": post.id, "title": post.title})


def broadcast_new_comment(comment) -> None:  # noqa: ANN001
    _send(
        post_group(comment.post_id),
        "comment_created",
        {"id": comment.id, "post_id": comment.post_id},
    )


def broadcast_vote_change(target, new_score: int) -> None:  # noqa: ANN001
    cls = target.__class__.__name__.lower()
    payload = {"target_type": cls, "id": target.id, "score": new_score}
    if cls == "post":
        _send(FEED_GROUP, "score_changed", payload)
        _send(post_group(target.id), "score_changed", payload)
    elif cls == "comment":
        _send(post_group(target.post_id), "score_changed", payload)
