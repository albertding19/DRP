"""Moderation models.

`ModerationLog` is an audit row written every time L1 (keyword) or L2 (Claude)
rejects user-submitted content. It captures what was blocked, why, and by
which layer — so admins can review for false positives and tune the
wordlist or the L2 rubric without flying blind.

No user-target table (Post / Comment) is touched when L1/L2 blocks — the
log row is the only persistent trace, and the user's content is never
published.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ModerationLog(TimeStampedModel):
    """One row per L1 / L2 block decision."""

    LAYER_L1 = "L1"
    LAYER_L2 = "L2"
    LAYER_CHOICES = [
        (LAYER_L1, "Keyword (L1)"),
        (LAYER_L2, "Claude (L2)"),
    ]

    SURFACE_COMMENT = "comment"
    SURFACE_POST_BODY = "post_body"
    SURFACE_POST_TITLE = "post_title"
    SURFACE_CHOICES = [
        (SURFACE_COMMENT, "Comment body"),
        (SURFACE_POST_BODY, "Post body"),
        (SURFACE_POST_TITLE, "Post title"),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderation_blocks",
        null=True,
        blank=True,
        help_text="The user who tried to submit the content. May be null if "
        "the form was constructed without an author reference.",
    )
    layer = models.CharField(max_length=4, choices=LAYER_CHOICES)
    surface = models.CharField(max_length=20, choices=SURFACE_CHOICES)
    text = models.TextField(help_text="The exact content that was blocked.")
    reason = models.TextField(help_text="User-facing rejection message shown at submit time.")
    false_positive = models.BooleanField(
        default=False,
        help_text="Admin-marked: this should not have been blocked. Use to "
        "track tuning needs (e.g. add the term to an allowlist).",
    )

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["layer", "-created_at"]),
        ]
        verbose_name = "moderation log entry"
        verbose_name_plural = "moderation log"

    def __str__(self) -> str:
        return (
            f"{self.layer} block on {self.surface} "
            f"by user #{self.author_id} at {self.created_at:%Y-%m-%d %H:%M}"
        )
