"""Overlap matching for scheduled bookings.

Bookings pair on TIME, not queue order: two open bookings match when
their requested windows [start_at, start_at + duration) share at least
`BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN` minutes of future time, and their
chattiness values are compatible (the same hard rule as the live pool,
reusing the same queryset filter).

There are no loosening phases here — wait time isn't a meaningful
dimension when both parties named an absolute start time, and every new
booking re-runs the scan, so holding out for a better partner risks
stranding everyone. Instead, soft preferences RANK the candidates:

    1. work-mode compatible first (same value or either side "any")
    2. then same community
    3. then largest window overlap
    4. then oldest booking (fairness tiebreak)

This is a module-level function, not a `MatchingStrategy` — that
Protocol is typed to PoolTicket and keyed off `enqueue()`; bookings have
their own trigger points (book, cancel-and-rematch).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.body_double.models import PoolTicket, ScheduledBooking

from .preferences import _chattiness_compatible

# Largest duration choice — bounds the coarse SQL window: no booking
# starting earlier than this before ours can still overlap us.
_MAX_DURATION_MIN = max(minutes for minutes, _label in PoolTicket.DURATION_CHOICES)


def work_mode_ok(a: str, b: str) -> bool:
    """The same truth rule as `preferences._work_mode_compatible`, as a
    pure predicate: "any" pairs with everything, named modes pair with
    same-or-any."""
    return PoolTicket.WORK_MODE_ANY in (a, b) or a == b


def overlap_window(a: ScheduledBooking, b: ScheduledBooking) -> tuple[datetime, datetime]:
    """The shared portion of two requested windows (may be negative —
    callers check)."""
    return max(a.start_at, b.start_at), min(a.end_at, b.end_at)


def find_booking_match(booking: ScheduledBooking) -> ScheduledBooking | None:
    """Best open, compatible, overlapping booking for `booking`, or None.

    Must run inside `transaction.atomic` — locks candidate rows with
    `select_for_update` so two simultaneous bookers can't both claim the
    same partner.
    """
    now = timezone.now()
    min_overlap = timedelta(minutes=settings.BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN)

    qs = (
        ScheduledBooking.objects.select_for_update()
        .filter(status=ScheduledBooking.STATUS_OPEN)
        .exclude(user_id=booking.user_id)
        .filter(
            start_at__lt=booking.end_at,
            start_at__gt=booking.start_at - timedelta(minutes=_MAX_DURATION_MIN),
        )
    )
    qs = _chattiness_compatible(qs, booking.chattiness)

    best: ScheduledBooking | None = None
    best_key: tuple | None = None
    for candidate in qs:
        start, end = overlap_window(booking, candidate)
        # Only FUTURE overlap counts — a re-opened booking mid-window
        # can still pair, but not into a window that's nearly over.
        effective_start = max(start, now)
        if end - effective_start < min_overlap:
            continue
        key = (
            work_mode_ok(booking.work_mode, candidate.work_mode),
            booking.community_id is not None and candidate.community_id == booking.community_id,
            end - effective_start,
            -candidate.created_at.timestamp(),  # oldest wins on ties
        )
        if best_key is None or key > best_key:
            best, best_key = candidate, key
    return best
