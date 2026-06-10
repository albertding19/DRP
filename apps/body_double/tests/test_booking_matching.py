"""Tests for `matching.scheduled.find_booking_match` — overlap rules,
the hard chattiness rule, and the soft-preference ranking."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.matching.scheduled import find_booking_match, overlap_window
from apps.body_double.models import PoolTicket, ScheduledBooking
from apps.communities.models import Community
from apps.communities.services import create_community


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _booking(
    user: User,
    *,
    start_in_min: int = 60,
    duration: int = 30,
    chattiness: str = PoolTicket.CHATTINESS_FLEXIBLE,
    work_mode: str = PoolTicket.WORK_MODE_ANY,
    community: Community | None = None,
    base=None,
) -> ScheduledBooking:
    # Tests asserting exact-overlap boundaries must pass a shared `base` —
    # two raw timezone.now() calls differ by microseconds, which turns
    # "exactly 15 min overlap" into 15 min minus epsilon.
    return ScheduledBooking.objects.create(
        user=user,
        community=community,
        start_at=(base or timezone.now()) + timedelta(minutes=start_in_min),
        duration_minutes=duration,
        chattiness=chattiness,
        work_mode=work_mode,
        status=ScheduledBooking.STATUS_OPEN,
    )


def _find(booking: ScheduledBooking) -> ScheduledBooking | None:
    with transaction.atomic():
        return find_booking_match(booking)


@pytest.mark.django_db(transaction=True)
class TestFindBookingMatch:
    # ----- Overlap rules -----

    def test_identical_windows_match(self) -> None:
        first = _booking(_user("bk_a"))
        match = _find(_booking(_user("bk_b")))
        assert match is not None
        assert match.pk == first.pk

    def test_partial_overlap_above_minimum_matches(self) -> None:
        # 60–90 vs 75–105 → overlap 75–90 = 15 min = the minimum.
        base = timezone.now()
        first = _booking(_user("bk_c"), start_in_min=60, duration=30, base=base)
        match = _find(_booking(_user("bk_d"), start_in_min=75, duration=30, base=base))
        assert match is not None
        assert match.pk == first.pk

    def test_overlap_below_minimum_does_not_match(self) -> None:
        # 60–90 vs 80–110 → overlap 10 min < 15.
        _booking(_user("bk_e"), start_in_min=60, duration=30)
        assert _find(_booking(_user("bk_f"), start_in_min=80, duration=30)) is None

    def test_disjoint_windows_do_not_match(self) -> None:
        _booking(_user("bk_g"), start_in_min=60, duration=30)
        assert _find(_booking(_user("bk_h"), start_in_min=120, duration=30)) is None

    def test_non_open_bookings_ignored(self) -> None:
        stale = _booking(_user("bk_i"))
        stale.status = ScheduledBooking.STATUS_CANCELLED
        stale.save(update_fields=["status"])
        assert _find(_booking(_user("bk_j"))) is None

    def test_own_bookings_excluded(self) -> None:
        u = _user("bk_self")
        _booking(u)
        mine = ScheduledBooking.objects.create(
            user=u,
            start_at=timezone.now() + timedelta(minutes=60),
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        assert _find(mine) is None

    # ----- Chattiness: hard rule, same as the live pool -----

    def test_chatty_never_matches_quiet(self) -> None:
        _booking(_user("bk_quiet"), chattiness=PoolTicket.CHATTINESS_QUIET)
        assert _find(_booking(_user("bk_chatty"), chattiness=PoolTicket.CHATTINESS_CHATTY)) is None

    def test_flexible_matches_named_values(self) -> None:
        first = _booking(_user("bk_flex"), chattiness=PoolTicket.CHATTINESS_FLEXIBLE)
        match = _find(_booking(_user("bk_chatty2"), chattiness=PoolTicket.CHATTINESS_CHATTY))
        assert match is not None
        assert match.pk == first.pk

    # ----- Ranking -----

    def test_work_mode_compatible_outranks_bigger_overlap(self) -> None:
        # Incompatible work mode but perfect overlap...
        _booking(_user("bk_admin"), work_mode=PoolTicket.WORK_MODE_ADMIN)
        # ...loses to a compatible candidate with a smaller overlap.
        compat = _booking(_user("bk_deep"), start_in_min=75, work_mode=PoolTicket.WORK_MODE_DEEP)
        match = _find(
            _booking(_user("bk_caller"), duration=45, work_mode=PoolTicket.WORK_MODE_DEEP)
        )
        assert match is not None
        assert match.pk == compat.pk

    def test_same_community_outranks_bigger_overlap(self) -> None:
        owner = _user("bk_owner")
        comm = create_community(creator=owner, name="BkComm", category=Community.CATEGORY_INTEREST)
        _booking(_user("bk_nocomm"))  # perfect overlap, no community
        same = _booking(_user("bk_comm"), start_in_min=75, community=comm)
        match = _find(_booking(_user("bk_caller2"), duration=45, community=comm))
        assert match is not None
        assert match.pk == same.pk

    def test_bigger_overlap_wins_when_otherwise_equal(self) -> None:
        _booking(_user("bk_short"), start_in_min=75, duration=30)  # 15 min overlap
        bigger = _booking(_user("bk_long"), start_in_min=60, duration=30)  # full 30
        match = _find(_booking(_user("bk_caller3"), start_in_min=60, duration=30))
        assert match is not None
        assert match.pk == bigger.pk

    def test_incompatible_work_mode_still_matches_when_alone(self) -> None:
        # Work mode is ranking-only for bookings — never a blocker.
        first = _booking(_user("bk_solo_admin"), work_mode=PoolTicket.WORK_MODE_ADMIN)
        match = _find(_booking(_user("bk_solo_deep"), work_mode=PoolTicket.WORK_MODE_DEEP))
        assert match is not None
        assert match.pk == first.pk

    # ----- Helpers -----

    def test_overlap_window_is_max_start_min_end(self) -> None:
        a = _booking(_user("bk_w1"), start_in_min=60, duration=60)
        b = _booking(_user("bk_w2"), start_in_min=90, duration=60)
        start, end = overlap_window(a, b)
        assert start == b.start_at
        assert end == a.end_at
