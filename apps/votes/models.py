"""Vote model — full service layer lands Wed 27 May.

Uses a GenericForeignKey so one Vote table serves both Post and Comment.
Trade-off documented in plan §"Architectural trade-offs" #1.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class Vote(TimeStampedModel):
    UP = 1
    DOWN = -1
    VALUE_CHOICES = [(UP, "Up"), (DOWN, "Down")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    value = models.SmallIntegerField(choices=VALUE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="one_vote_per_target",
            ),
            models.CheckConstraint(
                condition=Q(value__in=[1, -1]),
                name="vote_value_range",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self) -> str:
        return f"vote {self.value:+d} by {self.user_id} on {self.content_type}#{self.object_id}"
