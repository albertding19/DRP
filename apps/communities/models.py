"""Community + CommunityMembership models.

Communities are joinable groups categorised by `module` (e.g. a single
class/unit), `course` (a degree programme), `interest` (a topic), or
`institution` (a university). Anyone can create one; everything is
public and open-join at MVP. The category is a fixed enum so the browse
page can group / filter naturally.

`Community.member_count` is denormalised for fast browse-list rendering.
It's maintained by signals in `apps/communities/signals.py`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Community(TimeStampedModel):
    """A joinable group with a category."""

    CATEGORY_MODULE = "module"
    CATEGORY_COURSE = "course"
    CATEGORY_INTEREST = "interest"
    CATEGORY_INSTITUTION = "institution"
    CATEGORY_CHOICES = [
        (CATEGORY_MODULE, "Module"),
        (CATEGORY_COURSE, "Course"),
        (CATEGORY_INTEREST, "Interest"),
        (CATEGORY_INSTITUTION, "Institution"),
    ]

    name = models.CharField(max_length=120)
    # Slug is unique across the whole table — the URL is /communities/<slug>/.
    # Auto-derived from name on creation; admin can edit.
    slug = models.SlugField(max_length=140, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField(blank=True)

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communities_created",
    )
    member_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["-member_count"]),
        ]
        verbose_name_plural = "communities"

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"


class CommunityMembership(TimeStampedModel):
    """One row per (user, community) — the join. `joined_at` is captured
    in the inherited `created_at` (TimeStampedModel)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "community"],
                name="one_membership_per_user_per_community",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.community_id}"
