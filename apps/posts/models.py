"""Post model — full impl lands Wed 27 May.

For now, a minimal model exists so other apps can foreign-key to it without
the import graph breaking. Fields here will be enriched (search_vector, etc.)
on Wed.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import SoftDeletableModel, TimeStampedModel


class Post(TimeStampedModel, SoftDeletableModel):
    PROBLEM = "problem"
    STRATEGY = "strategy"
    TYPE_CHOICES = [
        (PROBLEM, "Problem"),
        (STRATEGY, "Strategy"),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="posts",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    post_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=STRATEGY)
    score = models.IntegerField(default=0, db_index=True)
    comment_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-score"]),
        ]

    def __str__(self) -> str:
        return f"{self.post_type}: {self.title}"
