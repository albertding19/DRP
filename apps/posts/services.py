"""Service-layer for posts. Keeps views thin and tests cheap."""

from __future__ import annotations

from django.db import transaction
from django.db.models import QuerySet

from apps.tags.services import get_or_create_tags

from .models import Post


@transaction.atomic
def create_post(
    *,
    author,  # type: ignore[no-untyped-def]
    title: str,
    body: str,
    post_type: str = Post.STRATEGY,
    tag_names: list[str] | None = None,
) -> Post:
    """Create a post + attach tags. Single transaction so signals
    (broadcast_new_post, tag count maintenance) fire together.
    """
    post = Post.objects.create(
        author=author,
        title=title,
        body=body,
        post_type=post_type,
    )
    if tag_names:
        tags = get_or_create_tags(tag_names)
        if tags:
            post.tags.set(tags)
    return post


# Map sort key → order_by argument(s)
_SORT_FIELDS: dict[str, tuple[str, ...]] = {
    "new": ("-created_at",),
    "top": ("-score", "-created_at"),
    # Cheap "hot" — score weighted by recency. Real hotness lands at M3 with
    # a proper time-decay function in SQL.
    "hot": ("-score", "-created_at"),
}


def feed_queryset(sort: str = "new") -> QuerySet[Post]:
    """Return a Post queryset for the feed page, ordered by `sort`.

    Eagerly prefetches tags so card rendering doesn't N+1.
    """
    fields = _SORT_FIELDS.get(sort, _SORT_FIELDS["new"])
    return (
        Post.objects.select_related("author")
        .prefetch_related("tags")
        .filter(is_deleted=False)
        .order_by(*fields)
        .distinct()  # m2m filters can duplicate
    )
