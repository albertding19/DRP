"""Comment services."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.posts.models import Post

from .models import Comment, CommentReport

# Threshold above which a comment auto-hides pending admin review.
REPORT_AUTO_HIDE_THRESHOLD = 3


@transaction.atomic
def create_comment(
    *,
    author,  # type: ignore[no-untyped-def]
    post: Post,
    body: str,
    parent: Comment | None = None,
) -> Comment:
    """Create a comment, optionally as a reply.

    Enforces the one-level nesting rule (parent's parent must be null).
    """
    if parent is not None:
        if parent.post_id != post.pk:
            raise ValidationError("Parent comment belongs to a different post.")
        if parent.parent_id is not None:
            raise ValidationError("Replies can only be one level deep.")
        if parent.is_deleted:
            raise ValidationError("Can't reply to a deleted comment.")

    return Comment.objects.create(
        author=author,
        post=post,
        parent=parent,
        body=body,
    )


def soft_delete_comment(*, comment: Comment, requesting_user) -> None:  # type: ignore[no-untyped-def]
    """Soft-delete a comment. Only its author can delete it."""
    if comment.author_id != requesting_user.id:
        raise PermissionError("You can only delete your own comments.")
    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])


@transaction.atomic
def report_comment(*, comment: Comment, reporter) -> tuple[int, bool]:  # type: ignore[no-untyped-def]
    """Record a report against `comment` by `reporter`.

    Returns `(new_report_count, just_hidden)`. `just_hidden` is True iff
    this report pushed the comment over the auto-hide threshold (so callers
    know whether to broadcast a WebSocket hide event).

    Idempotent: the same user reporting the same comment twice returns the
    existing count without incrementing. Enforced both at the DB level
    (unique constraint) and via `get_or_create`.

    Self-reporting is not blocked — author may legitimately want to flag
    their own comment as needing review. Use the admin to investigate.
    """
    locked = Comment.objects.select_for_update().get(pk=comment.pk)

    _, created = CommentReport.objects.get_or_create(comment=locked, reporter=reporter)
    if not created:
        return locked.report_count, False

    locked.report_count = locked.reports.count()
    just_hidden = (not locked.is_hidden) and (locked.report_count >= REPORT_AUTO_HIDE_THRESHOLD)
    if just_hidden:
        locked.is_hidden = True
    locked.save(update_fields=["report_count", "is_hidden", "updated_at"])

    return locked.report_count, just_hidden
