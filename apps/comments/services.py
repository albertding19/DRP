"""Comment services."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.posts.models import Post

from .models import Comment


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
