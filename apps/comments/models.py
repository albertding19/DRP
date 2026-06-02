"""Comment model — full impl lands Mon 1 Jun (M3 week).

Minimal model now so migrations are runnable from day one.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import SoftDeletableModel, TimeStampedModel


class Comment(TimeStampedModel, SoftDeletableModel):
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField()
    score = models.IntegerField(default=0)

    # L3 moderation state. `is_hidden` is set to True when `report_count`
    # crosses the auto-hide threshold; hidden comments stay in the DB but
    # are filtered out of feed/thread/permalink queries.
    is_hidden = models.BooleanField(default=False, db_index=True)
    report_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"comment by {self.author} on post #{self.post_id}"

    def clean(self) -> None:
        """Enforce one-level nesting (parent's parent must be null)."""
        super().clean()
        if self.parent_id and self.parent.parent_id is not None:
            raise ValidationError({"parent": "Comments can only be one level deep."})


class CommentReport(TimeStampedModel):
    """A single user's report against a comment. Unique constraint on
    (comment, reporter) means a given user can only report a comment once
    — prevents one user inflating the count to threshold."""

    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_reports",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "reporter"],
                name="one_report_per_user_per_comment",
            ),
        ]
        indexes = [
            models.Index(fields=["comment", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"report on comment #{self.comment_id} by user #{self.reporter_id}"
