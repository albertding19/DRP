"""Body-double matchmaking models.

Two tables capture all of pool + session state:

  `BodyDoubleSession` — one row per matched pair, holds the LiveKit
    (or other provider) room ID, both participants' FKs, and lifecycle
    timestamps.
  `PoolTicket` — one row per "I want to be matched" attempt, FK to user
    and (once paired) to its partner ticket + the resulting session.

A partial unique constraint on PoolTicket prevents a user from holding
more than one active (waiting OR matched) ticket simultaneously, so the
matchmaking flow can rely on `select_for_update` + the constraint to
serialise double-click submissions without application-level locks.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class BodyDoubleSession(TimeStampedModel):
    """A 2-person video call between two matched users."""

    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
    ]

    # Opaque, unguessable identifier — used both as DB key and as the
    # video provider's room name. UUIDs are stored as 32-char hex strings
    # rather than the model's autoincrement pk so room IDs can't be
    # enumerated (`/room/1/`, `/room/2/`, …).
    room_id = models.CharField(max_length=64, unique=True)

    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="body_double_sessions_as_a",
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="body_double_sessions_as_b",
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self) -> str:
        return f"session {self.room_id[:12]} ({self.status})"

    def includes(self, user) -> bool:  # type: ignore[no-untyped-def]
        """True if `user` is one of the two session participants."""
        return user.id in {self.user_a_id, self.user_b_id}


class PoolTicket(TimeStampedModel):
    """A user's intent to be matched. Lifecycle: waiting → matched, OR
    waiting → cancelled / expired (terminal states)."""

    STATUS_WAITING = "waiting"
    STATUS_MATCHED = "matched"
    STATUS_COMPLETED = "completed"  # session ended normally
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_WAITING, "Waiting"),
        (STATUS_MATCHED, "Matched"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    # Tickets in these states block the user from creating another one
    # (enforced by the partial unique constraint below). Completed and
    # cancelled tickets are terminal — the user may enqueue again.
    ACTIVE_STATUSES = (STATUS_WAITING, STATUS_MATCHED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="body_double_tickets",
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_WAITING, db_index=True
    )
    # The other half of this match, once paired. Null while waiting.
    matched_with = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_pair",
    )
    # The session this ticket belongs to (once matched). Null while waiting.
    session = models.ForeignKey(
        BodyDoubleSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # Partial unique: at most one waiting OR matched ticket per
            # user at a time. Cancelled and expired tickets do NOT block a
            # new attempt. Enforced at the DB level so double-click on
            # "Find a body double" is a single IntegrityError that we can
            # catch + redirect, rather than an application race window.
            # Note: ACTIVE_STATUSES can't be referenced inside the class
            # body during Meta evaluation, so the values are inlined here;
            # keep this list and ACTIVE_STATUSES in sync.
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=["waiting", "matched"]),
                name="one_active_ticket_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"ticket #{self.pk} {self.user_id} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES
