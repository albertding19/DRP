"""Service-layer for posts. Keeps views thin and tests cheap."""

from __future__ import annotations

from django.db import transaction
from django.db.models import QuerySet

from apps.tags.services import get_or_create_tags

from .models import Post, PostReport

# Threshold above which a post auto-hides pending admin review.
# Kept aligned with apps.comments.services.REPORT_AUTO_HIDE_THRESHOLD so
# the community experiences consistent moderation thresholds across both
# content types.
REPORT_AUTO_HIDE_THRESHOLD = 3


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

    Eagerly prefetches tags so card rendering doesn't N+1. Filters out
    soft-deleted AND L3-hidden posts so neither shows in the public feed.
    """
    fields = _SORT_FIELDS.get(sort, _SORT_FIELDS["new"])
    return (
        Post.objects.select_related("author")
        .prefetch_related("tags")
        .filter(is_deleted=False, is_hidden=False)
        .order_by(*fields)
        .distinct()  # m2m filters can duplicate
    )


@transaction.atomic
def report_post(*, post: Post, reporter) -> tuple[int, bool]:  # type: ignore[no-untyped-def]
    """Record a report against `post` by `reporter`.

    Mirrors `apps.comments.services.report_comment`. Returns
    `(new_report_count, just_hidden)`. Idempotent per (post, reporter).
    """
    locked = Post.objects.select_for_update().get(pk=post.pk)

    _, created = PostReport.objects.get_or_create(post=locked, reporter=reporter)
    if not created:
        return locked.report_count, False

    locked.report_count = locked.reports.count()
    just_hidden = (not locked.is_hidden) and (locked.report_count >= REPORT_AUTO_HIDE_THRESHOLD)
    if just_hidden:
        locked.is_hidden = True
    locked.save(update_fields=["report_count", "is_hidden", "updated_at"])

    return locked.report_count, just_hidden
