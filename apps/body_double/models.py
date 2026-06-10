"""Body-double matchmaking models.

Three tables capture pool + booking + session state:

  `BodyDoubleSession` — one row per matched pair, holds the LiveKit
    (or other provider) room ID, both participants' FKs, and lifecycle
    timestamps.
  `PoolTicket` — one row per LIVE "match me now" attempt, FK to user
    and (once paired) to its partner ticket + the resulting session.
  `ScheduledBooking` — one row per PRE-BOOKED "match me at 15:00"
    request. Same preference fields as PoolTicket, but anchored on a
    future `start_at` rather than queue order, and matched against
    overlapping bookings at booking time. The session is created lazily
    when the first participant joins, not at match time.

A partial unique constraint on PoolTicket prevents a user from holding
more than one active (waiting OR matched) ticket simultaneously, so the
matchmaking flow can rely on `select_for_update` + the constraint to
serialise double-click submissions without application-level locks.
Bookings deliberately have NO such constraint — a user may hold several
future bookings (and a live ticket) at once; per-user overlap is
enforced in the service layer instead.
"""

from __future__ import annotations

from datetime import timedelta

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

    # Min of the two paired tickets' duration_minutes at match time. Shown
    # as a static label in the room — no countdown, no auto-end. Nullable
    # for legacy sessions that pre-date the preference-matching feature.
    agreed_duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Min of the two tickets' duration_minutes at match time. "
            "Shown as a static label in the room — no auto-end."
        ),
    )

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

    # ---- Preference choices (per-session, re-entered each time) ----
    # These are the user's stated needs for THIS particular call. They
    # live on the ticket (not the User) so each queue-up is a fresh
    # declaration of what they want right now.

    DURATION_CHOICES = [
        (15, "15 min"),
        (30, "30 min"),
        (45, "45 min"),
        (60, "60 min"),
        (90, "90 min"),
    ]

    CHATTINESS_CHATTY = "chatty"
    CHATTINESS_QUIET = "quiet"
    CHATTINESS_FLEXIBLE = "flexible"
    CHATTINESS_CHOICES = [
        (CHATTINESS_CHATTY, "Chatty — happy to talk between focus"),
        (CHATTINESS_QUIET, "Quiet — silent focus"),
        (CHATTINESS_FLEXIBLE, "Flexible — either's fine"),
    ]

    WORK_MODE_DEEP = "deep_focus"
    WORK_MODE_BUSYWORK = "busywork"
    WORK_MODE_ADMIN = "admin"
    WORK_MODE_ANY = "any"
    WORK_MODE_CHOICES = [
        (WORK_MODE_DEEP, "Deep focus"),
        (WORK_MODE_BUSYWORK, "Busywork"),
        (WORK_MODE_ADMIN, "Admin / email"),
        (WORK_MODE_ANY, "Any"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="body_double_tickets",
    )
    # Optional community preference. The configured matching strategy
    # decides what to do with it; the MVP CommunityFallbackStrategy
    # prefers same-community matches, falls back to general pool after
    # BODY_DOUBLE_FALLBACK_S seconds.
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pool_tickets",
    )

    # How long the user expects to work for. The matcher prefers nearby
    # durations so both participants leave the call at roughly the same
    # time. The SESSION row records the MIN of the two paired tickets'
    # durations as the "agreed" length — shown as a static label, no
    # countdown, no auto-end.
    duration_minutes = models.PositiveSmallIntegerField(
        choices=DURATION_CHOICES,
        default=30,
        help_text="Expected session length. Matcher prefers nearby durations.",
    )

    # Chattiness is the ONE preference the matcher treats as a hard rule:
    # chatty × quiet is NEVER paired, regardless of how long either has
    # waited. Mismatched vibes are worse than waiting longer. Flexible
    # users pair with anyone — that's the "I don't mind" path.
    chattiness = models.CharField(
        max_length=10,
        choices=CHATTINESS_CHOICES,
        default=CHATTINESS_FLEXIBLE,
        help_text="Conversational preference. Hard compat rule in the matcher.",
    )

    # Work mode is a SOFT preference. Strategy starts strict (only same
    # work_mode or 'any' pair) then loosens after BODY_DOUBLE_FALLBACK_S
    # so a niche-mode user isn't stranded forever.
    work_mode = models.CharField(
        max_length=15,
        choices=WORK_MODE_CHOICES,
        default=WORK_MODE_ANY,
        help_text="What you're working on. Soft preference; loosens over time.",
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


class ScheduledBooking(TimeStampedModel):
    """A user's intent to be matched at a FUTURE time.

    Lifecycle: open → matched → completed, OR open/matched → cancelled /
    expired (terminal). Unlike PoolTicket there is no separate "waiting"
    page — an open booking just sits on the schedule page until a
    compatible overlapping booking arrives, the user cancels, or the
    window passes (lazy expiry; there is no background job).

    Matched pairs hold identical `agreed_start_at` / `agreed_end_at` —
    the overlap of the two requested windows. The `BodyDoubleSession` is
    created only when the first participant clicks Join inside the join
    window, so `session` stays NULL between match and start.
    """

    STATUS_OPEN = "open"
    STATUS_MATCHED = "matched"
    STATUS_COMPLETED = "completed"  # session ended normally
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"  # window passed unmatched, or matched pair no-showed
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_MATCHED, "Matched"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    # Bookings in these states appear on the schedule page and count as
    # busy time for the user's timetable. Completed / cancelled / expired
    # are terminal.
    ACTIVE_STATUSES = (STATUS_OPEN, STATUS_MATCHED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="body_double_bookings",
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_bookings",
    )

    # When the user wants to start. Exact time — "flexibility" falls out
    # of overlap matching, not a separate field: two bookings pair when
    # their [start_at, end_at) windows share at least
    # BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN minutes.
    start_at = models.DateTimeField(db_index=True)

    # Same preference fields as PoolTicket, same semantics: chattiness is
    # the hard compatibility rule; work_mode and community only affect
    # partner ranking for bookings (no wait-time phases at booking time).
    duration_minutes = models.PositiveSmallIntegerField(
        choices=PoolTicket.DURATION_CHOICES,
        default=30,
        help_text="Planned session length from start_at.",
    )
    chattiness = models.CharField(
        max_length=10,
        choices=PoolTicket.CHATTINESS_CHOICES,
        default=PoolTicket.CHATTINESS_FLEXIBLE,
        help_text="Conversational preference. Hard compat rule in the matcher.",
    )
    work_mode = models.CharField(
        max_length=15,
        choices=PoolTicket.WORK_MODE_CHOICES,
        default=PoolTicket.WORK_MODE_ANY,
        help_text="What you're working on. Affects partner ranking only.",
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True
    )
    # The other half of this match, once paired. Null while open.
    matched_with = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_pair",
    )
    # Created lazily by the first Join inside the join window. Null while
    # open AND between match and first join.
    session = models.ForeignKey(
        BodyDoubleSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    # The overlap of the two requested windows, denormalised onto BOTH
    # rows at match time (mirrors matched_with / session on PoolTicket).
    agreed_start_at = models.DateTimeField(null=True, blank=True)
    agreed_end_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["user", "start_at"]),
        ]

    def __str__(self) -> str:
        return f"booking #{self.pk} {self.user_id} @ {self.start_at:%Y-%m-%d %H:%M} ({self.status})"

    @property
    def end_at(self):
        """End of the REQUESTED window (not the agreed overlap)."""
        return self.start_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES
