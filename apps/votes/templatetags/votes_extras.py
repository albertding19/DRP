"""Template helpers for vote rendering.

Currently used only to silence Django's "load votes_extras" import — the
filter list will grow when we add things like `current_user_vote` later.
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def user_vote_for(context, target):  # type: ignore[no-untyped-def]
    """Return the request user's vote on `target` (+1 / -1 / 0)."""
    from apps.votes.services import user_vote_for as _service

    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    return _service(user, target) if user else 0
