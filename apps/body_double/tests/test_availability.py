"""Tests for `apps.body_double.availability`.

Every test passes an explicit `now` / window anchored at noon local time
so results don't depend on when the suite runs. Core invariant under
test: the timetable only ever says "busy" — silence (empty timetable,
outside the work window) must read as fully free.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.availability import (
    UNCONSTRAINED_MINUTES,
    availability_for,
    free_minutes_from,
)
from apps.tasks.models import BusyBlock, Task


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _noon():
    """Today at 12:00 local — safely inside the 9–21 work window."""
    return timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)


def _task(user: User, *, minutes_from_noon: int, duration: int = 30, **kwargs) -> Task:
    noon = _noon()
    return Task.objects.create(
        user=user,
        name="t",
        duration_minutes=duration,
        scheduled_start=noon + timedelta(minutes=minutes_from_noon),
        **kwargs,
    )


def _block(user: User, *, minutes_from_noon: int, duration: int = 30) -> BusyBlock:
    noon = _noon()
    start = noon + timedelta(minutes=minutes_from_noon)
    return BusyBlock.objects.create(
        user=user, name="b", start_at=start, end_at=start + timedelta(minutes=duration)
    )


@pytest.mark.django_db
class TestAvailabilityFor:
    def test_empty_timetable_is_one_full_slot(self) -> None:
        u = _user("av_empty")
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=2))
        assert len(slots) == 1
        assert slots[0].start == noon
        assert slots[0].end == noon + timedelta(hours=2)

    def test_busy_block_splits_window(self) -> None:
        u = _user("av_block")
        _block(u, minutes_from_noon=30, duration=30)  # 12:30–13:00
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=2))
        assert [(s.start, s.end) for s in slots] == [
            (noon, noon + timedelta(minutes=30)),
            (noon + timedelta(minutes=60), noon + timedelta(hours=2)),
        ]

    def test_scheduled_task_counts_as_busy(self) -> None:
        u = _user("av_task")
        _task(u, minutes_from_noon=0, duration=45)  # 12:00–12:45
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=1))
        assert len(slots) == 1
        assert slots[0].start == noon + timedelta(minutes=45)

    def test_done_and_skipped_tasks_ignored(self) -> None:
        u = _user("av_done")
        _task(u, minutes_from_noon=0, status=Task.STATUS_DONE)
        _task(u, minutes_from_noon=30, status=Task.STATUS_SKIPPED)
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=1))
        assert len(slots) == 1
        assert slots[0].start == noon

    def test_partially_spent_task_uses_remaining_minutes(self) -> None:
        u = _user("av_spent")
        _task(u, minutes_from_noon=0, duration=60, time_spent_minutes=40)  # 20 min remain
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=1))
        assert len(slots) == 1
        assert slots[0].start == noon + timedelta(minutes=20)

    def test_other_users_timetable_irrelevant(self) -> None:
        u, other = _user("av_me"), _user("av_other")
        _block(other, minutes_from_noon=0, duration=120)
        noon = _noon()
        slots = availability_for(u, window_start=noon, window_end=noon + timedelta(hours=2))
        assert len(slots) == 1


@pytest.mark.django_db
class TestFreeMinutesFrom:
    def test_empty_timetable_unconstrained(self) -> None:
        assert free_minutes_from(_user("fm_empty"), now=_noon()) == UNCONSTRAINED_MINUTES

    def test_busy_right_now_is_zero(self) -> None:
        u = _user("fm_busy")
        _block(u, minutes_from_noon=-10, duration=30)  # 11:50–12:20
        assert free_minutes_from(u, now=_noon()) == 0

    def test_minutes_until_next_commitment(self) -> None:
        u = _user("fm_next")
        _block(u, minutes_from_noon=40)
        assert free_minutes_from(u, now=_noon()) == 40

    def test_nothing_ahead_today_unconstrained(self) -> None:
        # A commitment that already ended says nothing about the rest of
        # the day — and the work-window end is not a commitment.
        u = _user("fm_past")
        _block(u, minutes_from_noon=-60, duration=30)  # 11:00–11:30
        assert free_minutes_from(u, now=_noon()) == UNCONSTRAINED_MINUTES

    def test_outside_work_window_unconstrained(self, settings) -> None:
        u = _user("fm_late")
        _block(u, minutes_from_noon=40)
        late = _noon().replace(hour=settings.TASKS_WORK_END_HOUR)
        assert free_minutes_from(u, now=late) == UNCONSTRAINED_MINUTES
        early = _noon().replace(hour=settings.TASKS_WORK_START_HOUR - 1)
        assert free_minutes_from(u, now=early) == UNCONSTRAINED_MINUTES

    def test_in_progress_task_is_busy_now(self) -> None:
        u = _user("fm_prog")
        Task.objects.create(user=u, name="t", duration_minutes=30, status=Task.STATUS_IN_PROGRESS)
        assert free_minutes_from(u, now=_noon()) == 0
