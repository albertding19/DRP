"""Service-layer for posts. Keeps views thin and tests cheap."""

from __future__ import annotations

from django.db import transaction
from django.db.models import QuerySet

from .models import Post


@transaction.atomic
def create_post(
    *,
    author,  # type: ignore[no-untyped-def]
    title: str,
    body: str,
    post_type: str = Post.STRATEGY,
) -> Post:
    """Create a post. Wraps the model save so signals and any later
    side-effects (tag attachment, broadcast) happen in a single transaction.
    """
    return Post.objects.create(
        author=author,
        title=title,
        body=body,
        post_type=post_type,
    )


# Map sort key → order_by argument(s)
_SORT_FIELDS: dict[str, tuple[str, ...]] = {
    "new": ("-created_at",),
    "top": ("-score", "-created_at"),
    # Cheap "hot" — score weighted by recency. Real hotness lands at M3 with
    # a proper time-decay function in SQL.
    "hot": ("-score", "-created_at"),
}


def feed_queryset(sort: str = "new") -> QuerySet[Post]:
    """Return a Post queryset for the feed page, ordered by `sort`."""
    fields = _SORT_FIELDS.get(sort, _SORT_FIELDS["new"])
    return Post.objects.select_related("author").filter(is_deleted=False).order_by(*fields)
