"""Task + BusyBlock models for the auto-generated timetable feature.

Two tables hold the planning state:

  `Task`       — a to-do item with a duration estimate and optional metadata
                 (priority, energy, deadline, body-double preference).
                 `scheduled_start` is populated by the auto-planner; tasks
                 without one live in the backlog. `time_spent_minutes`
                 accumulates across pauses so a partially-completed task
                 can be re-planned with its remaining duration.
  `BusyBlock`  — manually-added time the user can't work in (lecture,
                 meeting). Breaks created by "I need a break" use the
                 same model with `kind="break"` so the scheduler treats
                 them identically when computing free slots.

A partial unique constraint prevents more than one in-progress task per
user — Start clicks are serialised by the DB.
"""

from __future__ import annotations

import math
from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, F, Index, Q, UniqueConstraint
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Task(TimeStampedModel):
    """A single to-do item with optional planning metadata."""

    PRIORITY_LOW = "low"
    PRIORITY_MED = "med"
    PRIORITY_HIGH = "high"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MED, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    ENERGY_LOW = "low"
    ENERGY_MED = "med"
    ENERGY_HIGH = "high"
    ENERGY_CHOICES = [
        (ENERGY_LOW, "Low"),
        (ENERGY_MED, "Medium"),
        (ENERGY_HIGH, "High"),
    ]

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_DONE, "Done"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    DURATION_MIN = 5
    DURATION_MAX = 600

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    name = models.CharField(max_length=200)
    duration_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(DURATION_MIN), MaxValueValidator(DURATION_MAX)],
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MED)
    energy = models.CharField(max_length=10, choices=ENERGY_CHOICES, default=ENERGY_MED)
    deadline = models.DateTimeField(null=True, blank=True)
    body_double_preferred = models.BooleanField(default=False)

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    # Populated by the planner; NULL means "in the backlog, not on the timetable".
    scheduled_start = models.DateTimeField(null=True, blank=True)
    # Set when the user clicks Start, cleared on pause / done.
    actual_start_at = models.DateTimeField(null=True, blank=True)
    # Accumulates across pauses so re-planning uses remaining_minutes.
    time_spent_minutes = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_start", "created_at"]
        indexes = [
            Index(fields=["user", "status"], name="task_user_status_idx"),
            Index(fields=["user", "scheduled_start"], name="task_user_sched_idx"),
        ]
        constraints = [
            # At most one in-progress task per user. Inlined status value
            # because class attrs aren't visible inside Meta. Keep in sync
            # with STATUS_IN_PROGRESS above.
            UniqueConstraint(
                fields=["user"],
                condition=Q(status="in_progress"),
                name="one_task_in_progress_per_user",
            ),
            # Enforce duration bounds at the DB level too — Django's
            # validators only fire on full_clean(), which services don't
            # always call.
            CheckConstraint(
                condition=Q(duration_minutes__gte=5) & Q(duration_minutes__lte=600),
                name="task_duration_bounds",
            ),
        ]

    def __str__(self) -> str:
        return f"task #{self.pk} {self.name!r} ({self.status})"

    @property
    def remaining_minutes(self) -> int:
        """Minutes still needed to finish the task. The planner uses this
        (not `duration_minutes`) so a paused-and-resumed task takes only
        its remaining time."""
        return max(0, self.duration_minutes - self.time_spent_minutes)

    @property
    def is_continued(self) -> bool:
        """True for the remaining slice of a task that was paused by a break
        and is waiting to be resumed (partially done, back in the pending
        queue). The timetable labels this row "(continued)"."""
        return self.status == self.STATUS_PENDING and self.time_spent_minutes > 0

    @property
    def in_progress_ends_at(self):
        """When the current in-progress interval is due to finish:
        `actual_start_at` + the minutes that were left when it started. None
        unless the task is actively running."""
        if self.actual_start_at is None:
            return None
        return self.actual_start_at + timedelta(minutes=self.remaining_minutes)

    @property
    def live_remaining_minutes(self) -> int:
        """Minutes to go *right now* — `remaining_minutes` less the time
        already elapsed in the current in-progress interval. Mirrors the
        client-side countdown (`realtime.js`) so the first paint matches it."""
        end = self.in_progress_ends_at
        if end is None:
            return self.remaining_minutes
        return max(0, math.ceil((end - timezone.now()).total_seconds() / 60))


class BusyBlock(TimeStampedModel):
    """A blocked-out interval the planner must avoid.

    Two flavours, distinguished by `kind`:
      manual — user-added lecture / meeting / appointment.
      break  — created by the "I need a break" action.
    """

    KIND_MANUAL = "manual"
    KIND_BREAK = "break"
    KIND_CHOICES = [
        (KIND_MANUAL, "Manual"),
        (KIND_BREAK, "Break"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="busy_blocks",
    )
    name = models.CharField(max_length=200)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_MANUAL)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            Index(fields=["user", "start_at"], name="bblock_user_start_idx"),
        ]
        constraints = [
            CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="busy_block_positive_duration",
            ),
        ]

    def __str__(self) -> str:
        return f"busy #{self.pk} {self.name!r} ({self.kind})"
