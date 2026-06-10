"""Tests for `TimetableAwareStrategy`.

The new dimension: a candidate whose timetable says they're busy (or
about to be) is skipped in phases 1–3 and only becomes eligible at the
last-resort phase. Everything else must behave exactly like
`PreferenceMatchingStrategy` — especially the "silence is freedom"
cases (empty timetable, outside work hours), which cover the default
user who never opens the tasks page.

Timetable fixtures anchor on real wall-clock "now" because the strategy
reads `timezone.now()` internally; `_force_work_window` widens the work
window so runs outside 9–21 local don't neutralise the check.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.matching.timetable import TimetableAwareStrategy
from apps.body_double.models import PoolTicket
from apps.tasks.models import BusyBlock


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _ticket(
    user: User,
    *,
    duration: int = 30,
    chattiness: str = PoolTicket.CHATTINESS_FLEXIBLE,
    work_mode: str = PoolTicket.WORK_MODE_ANY,
) -> PoolTicket:
    return PoolTicket.objects.create(
        user=user,
        status=PoolTicket.STATUS_WAITING,
        duration_minutes=duration,
        chattiness=chattiness,
        work_mode=work_mode,
    )


def _backdate(ticket: PoolTicket, seconds_ago: int) -> None:
    PoolTicket.objects.filter(pk=ticket.pk).update(
        created_at=timezone.now() - timedelta(seconds=seconds_ago)
    )


def _busy_now(user: User, *, minutes: int = 120) -> BusyBlock:
    """Mark `user` busy from 10 minutes ago for `minutes`."""
    start = timezone.now() - timedelta(minutes=10)
    return BusyBlock.objects.create(
        user=user, name="lecture", start_at=start, end_at=start + timedelta(minutes=minutes)
    )


@pytest.fixture
def _force_work_window(settings):
    """Make 'now' always fall inside the planning work window so the
    timetable check is live regardless of when the suite runs."""
    settings.TASKS_WORK_START_HOUR = 0
    settings.TASKS_WORK_END_HOUR = 23
    if timezone.localtime().hour >= 23:  # pragma: no cover
        pytest.skip("23:00–00:00 local — hour-based work window can't contain now")


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_force_work_window")
class TestTimetableAwareStrategy:
    def test_empty_timetable_candidate_matches_immediately(self) -> None:
        partner = _ticket(_user("tt_free"))
        caller = _ticket(_user("tt_caller"))
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_busy_candidate_skipped_in_strict_phases(self) -> None:
        busy_user = _user("tt_busy")
        _busy_now(busy_user)
        _ticket(busy_user)
        caller = _ticket(_user("tt_caller2"))
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is None

    def test_busy_candidate_matches_at_last_resort_phase(self, settings) -> None:
        settings.BODY_DOUBLE_LOOSE_S = 10
        busy_user = _user("tt_busy2")
        _busy_now(busy_user)
        partner = _ticket(busy_user)
        _backdate(partner, 30)  # past LOOSE_S → phase 4, timetable check dropped
        caller = _ticket(_user("tt_caller3"))
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_free_candidate_preferred_over_older_busy_one(self) -> None:
        busy_user = _user("tt_busy3")
        _busy_now(busy_user)
        busy_partner = _ticket(busy_user)
        _backdate(busy_partner, 20)  # older, would win on FIFO
        free_partner = _ticket(_user("tt_free3"))
        caller = _ticket(_user("tt_caller4"))
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == free_partner.pk

    def test_candidate_free_long_enough_for_agreed_overlap(self) -> None:
        # Candidate is free for 40 min then busy. Agreed duration is
        # min(30, 45) = 30 ≤ 40, so they fit even though the caller
        # asked for 45 (and |Δduration| = 15 keeps phase 1 in play).
        partner_user = _user("tt_gap")
        gap_start = timezone.now() + timedelta(minutes=40)
        BusyBlock.objects.create(
            user=partner_user,
            name="seminar",
            start_at=gap_start,
            end_at=gap_start + timedelta(minutes=60),
        )
        partner = _ticket(partner_user, duration=30)
        caller = _ticket(_user("tt_caller5"), duration=45)
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_candidate_with_commitment_too_soon_skipped(self) -> None:
        # Free for only 15 min, but the agreed duration would be 30.
        partner_user = _user("tt_soon")
        gap_start = timezone.now() + timedelta(minutes=15)
        BusyBlock.objects.create(
            user=partner_user,
            name="meeting",
            start_at=gap_start,
            end_at=gap_start + timedelta(minutes=60),
        )
        _ticket(partner_user, duration=30)
        caller = _ticket(_user("tt_caller6"), duration=30)
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is None

    def test_requesters_own_timetable_ignored(self) -> None:
        # The caller is busy per their timetable — but they clicked
        # "match me now", so only the candidate's timetable matters.
        partner = _ticket(_user("tt_free4"))
        caller_user = _user("tt_busy_caller")
        _busy_now(caller_user)
        caller = _ticket(caller_user)
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_outside_work_window_timetable_is_silent(self, settings) -> None:
        # Shrink the work window to the past: now is outside it, so even
        # a busy-looking timetable can't block the match.
        settings.TASKS_WORK_START_HOUR = 0
        settings.TASKS_WORK_END_HOUR = 1
        if timezone.localtime().hour < 1:  # pragma: no cover — 00:00–01:00 runs
            settings.TASKS_WORK_END_HOUR = 0
        busy_user = _user("tt_evening")
        _busy_now(busy_user)
        partner = _ticket(busy_user)
        caller = _ticket(_user("tt_caller7"))
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_chattiness_still_hard_even_at_last_phase(self, settings) -> None:
        settings.BODY_DOUBLE_LOOSE_S = 10
        partner = _ticket(_user("tt_quiet"), chattiness=PoolTicket.CHATTINESS_QUIET)
        _backdate(partner, 600)
        caller = _ticket(_user("tt_chatty"), chattiness=PoolTicket.CHATTINESS_CHATTY)
        with transaction.atomic():
            match = TimetableAwareStrategy().find_match(caller)
        assert match is None
