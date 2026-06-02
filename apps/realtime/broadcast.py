"""Public broadcast API — the only module that touches the channel layer.

Each function:
1. Renders the relevant HTML partial server-side (so the client doesn't
   need to do a second roundtrip to fetch the fragment).
2. Sends the rendered HTML in the payload alongside a small JSON envelope.

Frontend (`static/js/realtime.js`) dispatches a `CustomEvent` per message
type; templates listen via `x-on:ws:<type>.window` and swap the HTML into
the appropriate DOM target.

These are all sync-safe (wrapped in `async_to_sync`) so they can be
called from Django signal handlers.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.template.loader import render_to_string

from .groups import FEED_GROUP, post_group


def _send(group: str, event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(group, {"type": event_type, "payload": payload})


def broadcast_new_post(post) -> None:  # noqa: ANN001
    html = render_to_string("posts/_post_card.html", {"post": post})
    _send(
        FEED_GROUP,
        "post_created",
        {"id": post.id, "html": html},
    )


def broadcast_new_comment(comment) -> None:  # noqa: ANN001
    html = render_to_string(
        "comments/_comment.html",
        {"comment": comment, "post": comment.post, "thread_root": comment.parent_id is None},
    )
    _send(
        post_group(comment.post_id),
        "comment_created",
        {
            "id": comment.id,
            "post_id": comment.post_id,
            "parent_id": comment.parent_id,
            "html": html,
        },
    )


def broadcast_vote_change(target, new_score: int) -> None:  # noqa: ANN001
    cls = target.__class__.__name__.lower()
    payload = {"target_type": cls, "id": target.id, "score": new_score}
    if cls == "post":
        # Two groups — anyone watching the feed AND anyone viewing this post.
        _send(FEED_GROUP, "score_changed", payload)
        _send(post_group(target.id), "score_changed", payload)
    elif cls == "comment":
        _send(post_group(target.post_id), "score_changed", payload)


def broadcast_comment_hidden(comment) -> None:  # noqa: ANN001
    """Sent when a comment crosses the L3 auto-hide threshold.

    Live viewers on the post-detail page (joined to `post_<id>`) receive
    the event; the Alpine handler removes the comment node from the DOM
    so reporters don't see stale state until they refresh.
    """
    _send(
        post_group(comment.post_id),
        "comment_hidden",
        {"id": comment.id, "post_id": comment.post_id},
    )


def broadcast_post_hidden(post) -> None:  # noqa: ANN001
    """Sent when a post crosses the L3 auto-hide threshold.

    Two groups receive the event: the feed (so post cards disappear from
    the home page) and `post_<id>` (so anyone on the detail page sees the
    content vanish without a refresh).
    """
    payload = {"id": post.id}
    _send(FEED_GROUP, "post_hidden", payload)
    _send(post_group(post.id), "post_hidden", payload)
