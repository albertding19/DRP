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
