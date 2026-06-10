"""Timetable-derived availability for body-double matchmaking.

The tasks app already holds each user's day plan (scheduled Tasks +
BusyBlocks). This module turns that plan into answers the matchmaking
layer can use:

  `availability_for`    — free intervals inside a window, for showing
                          "you're free 13:00–15:00" hints on the booking
                          form.
  `free_minutes_from`   — minutes until the user's next timetabled
                          commitment, for the timetable-aware live-pool
                          strategy ("does this candidate actually have
                          time for a 30-minute session right now?").

Philosophy: the timetable can only ever say "this user is busy" — it
never *blocks* on silence. A user with an empty timetable is fully free
(UNCONSTRAINED), and outside the planning work window the timetable has
no opinion at all. Most users won't maintain a timetable; they must
match exactly as before.

Import graph note: `apps.tasks.scheduler` is a pure module (no Django /
model imports), so importing it here is safe. Model imports stay
function-level — `apps.tasks.services` already imports from
`apps.body_double.services`, so a module-level model import here would
be one step from a cycle.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.tasks.scheduler import BusyInterval, Slot, free_slots

# "The timetable has nothing to say" — large enough that any session
# duration check passes (max duration choice is 90 minutes).
UNCONSTRAINED_MINUTES = 24 * 60


def booking_intervals(
    user,  # type: ignore[no-untyped-def]
    window_start: datetime,
    window_end: datetime,
) -> list[BusyInterval]:
    """The user's active scheduled bookings as busy intervals — the
    agreed overlap once matched, the requested window while still open."""
    from apps.body_double.models import ScheduledBooking  # lazy: keep import style uniform

    out: list[BusyInterval] = []
    bookings = ScheduledBooking.objects.filter(
        user=user,
        status__in=ScheduledBooking.ACTIVE_STATUSES,
        start_at__lt=window_end,
    )
    for b in bookings:
        start = b.agreed_start_at or b.start_at
        end = b.agreed_end_at or b.end_at
        if start < window_end and end > window_start:
            out.append(BusyInterval(start=start, end=end))
    return out


def _busy_intervals(
    user,  # type: ignore[no-untyped-def]
    window_start: datetime,
    window_end: datetime,
    *,
    now: datetime | None = None,
) -> list[BusyInterval]:
    """Every interval in [window_start, window_end) the user's timetable
    marks as occupied: busy blocks, scheduled pending tasks (for their
    remaining duration), the in-progress task from `now`, and active
    body-double bookings.

    Intervals may poke out past the window — `free_slots` clips them.
    """
    from apps.tasks.models import BusyBlock, Task  # lazy: see module docstring

    busy: list[BusyInterval] = booking_intervals(user, window_start, window_end)

    blocks = BusyBlock.objects.filter(user=user, start_at__lt=window_end, end_at__gt=window_start)
    busy.extend(BusyInterval(start=b.start_at, end=b.end_at) for b in blocks)

    scheduled = Task.objects.filter(
        user=user,
        status=Task.STATUS_PENDING,
        scheduled_start__isnull=False,
        scheduled_start__lt=window_end,
    )
    for t in scheduled:
        end = t.scheduled_start + timedelta(minutes=t.remaining_minutes)
        if end > window_start:
            busy.append(BusyInterval(start=t.scheduled_start, end=end))

    # The in-progress task occupies now → now + remaining, same treatment
    # as auto_plan gives it.
    in_progress = Task.objects.filter(user=user, status=Task.STATUS_IN_PROGRESS).first()
    if in_progress is not None and in_progress.remaining_minutes > 0:
        anchor = now if now is not None else timezone.now()
        end = anchor + timedelta(minutes=in_progress.remaining_minutes)
        if anchor < window_end and end > window_start:
            busy.append(BusyInterval(start=anchor, end=end))

    return busy


def availability_for(user, *, window_start: datetime, window_end: datetime) -> list[Slot]:  # type: ignore[no-untyped-def]
    """Free intervals inside [window_start, window_end) according to the
    user's timetable. Empty timetable → one slot spanning the window."""
    busy = _busy_intervals(user, window_start, window_end)
    return free_slots(now=window_start, work_start=window_start, work_end=window_end, busy=busy)


def free_minutes_from(user, *, now: datetime | None = None) -> int:  # type: ignore[no-untyped-def]
    """Minutes from `now` until the user's next timetabled commitment.

    Returns:
      UNCONSTRAINED_MINUTES — `now` is outside the planning work window
        (the timetable only describes TASKS_WORK_START/END_HOUR), or the
        user has nothing scheduled ahead of `now` today. The work-window
        end is a planning boundary, not a commitment — a user with an
        empty timetable at 20:50 is still fully free.
      0 — the timetable says the user is busy right now.
      N — free for N minutes, then a commitment starts.
    """
    now_local = timezone.localtime(now) if now is not None else timezone.localtime()
    work_start = now_local.replace(
        hour=settings.TASKS_WORK_START_HOUR, minute=0, second=0, microsecond=0
    )
    work_end = now_local.replace(
        hour=settings.TASKS_WORK_END_HOUR, minute=0, second=0, microsecond=0
    )
    if now_local < work_start or now_local >= work_end:
        return UNCONSTRAINED_MINUTES

    upcoming = sorted(
        (
            iv
            for iv in _busy_intervals(user, now_local, work_end, now=now_local)
            if iv.end > now_local
        ),
        key=lambda iv: iv.start,
    )
    if not upcoming:
        return UNCONSTRAINED_MINUTES
    first = upcoming[0]
    if first.start <= now_local:
        return 0
    return int((first.start - now_local).total_seconds() // 60)
