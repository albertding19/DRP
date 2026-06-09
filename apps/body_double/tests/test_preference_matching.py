"""Tests for `PreferenceMatchingStrategy`.

Covers the 4-phase loosening schedule + the hard chattiness rule.
Uses the same helper pattern as `test_community_matching.py`:
`_backdate` shifts a ticket's `created_at` backwards so the strategy
sees it as "old enough" to satisfy a phase's `min_wait_s` cutoff.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.matching.preferences import PreferenceMatchingStrategy
from apps.body_double.models import PoolTicket
from apps.communities.models import Community
from apps.communities.services import create_community


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _ticket(
    user: User,
    *,
    community: Community | None = None,
    duration: int = 30,
    chattiness: str = PoolTicket.CHATTINESS_FLEXIBLE,
    work_mode: str = PoolTicket.WORK_MODE_ANY,
) -> PoolTicket:
    return PoolTicket.objects.create(
        user=user,
        community=community,
        status=PoolTicket.STATUS_WAITING,
        duration_minutes=duration,
        chattiness=chattiness,
        work_mode=work_mode,
    )


def _backdate(ticket: PoolTicket, seconds_ago: int) -> None:
    PoolTicket.objects.filter(pk=ticket.pk).update(
        created_at=timezone.now() - timedelta(seconds=seconds_ago)
    )


@pytest.mark.django_db(transaction=True)
class TestPreferenceMatchingStrategy:
    def _make_community(self, name: str) -> Community:
        owner = _user(f"owner_{name.lower()}")
        return create_community(creator=owner, name=name, category=Community.CATEGORY_INTEREST)

    # ----- Chattiness rules (always applied, never loosened) -----

    def test_chatty_chatty_matches_immediately(self) -> None:
        first = _ticket(_user("alice"), chattiness=PoolTicket.CHATTINESS_CHATTY)
        caller = _ticket(_user("bob"), chattiness=PoolTicket.CHATTINESS_CHATTY)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_quiet_quiet_matches_immediately(self) -> None:
        first = _ticket(_user("eve"), chattiness=PoolTicket.CHATTINESS_QUIET)
        caller = _ticket(_user("frank"), chattiness=PoolTicket.CHATTINESS_QUIET)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_chatty_never_matches_quiet(self, settings) -> None:
        # Even backdated past every fallback window, chatty × quiet must
        # NOT pair. Hard rule.
        settings.BODY_DOUBLE_LOOSE_S = 10
        first = _ticket(_user("ana"), chattiness=PoolTicket.CHATTINESS_QUIET)
        _backdate(first, 600)  # 10 minutes — past every phase
        caller = _ticket(_user("ben"), chattiness=PoolTicket.CHATTINESS_CHATTY)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is None

    def test_flexible_matches_chatty(self) -> None:
        first = _ticket(_user("flex_a"), chattiness=PoolTicket.CHATTINESS_FLEXIBLE)
        caller = _ticket(_user("chat_a"), chattiness=PoolTicket.CHATTINESS_CHATTY)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_flexible_matches_quiet(self) -> None:
        first = _ticket(_user("flex_b"), chattiness=PoolTicket.CHATTINESS_FLEXIBLE)
        caller = _ticket(_user("quiet_b"), chattiness=PoolTicket.CHATTINESS_QUIET)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    # ----- Duration -----

    def test_duration_within_15_pairs_in_phase_1(self) -> None:
        first = _ticket(_user("dur_a"), duration=30)
        caller = _ticket(_user("dur_b"), duration=45)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_duration_30_delta_waits_for_phase_2(self, settings) -> None:
        # 30 + 60 → |Δ|=30, outside phase-1's ±15. Should wait until
        # phase 2 (when partner has been waiting strict_s).
        settings.BODY_DOUBLE_STRICT_S = 5
        first = _ticket(_user("dur_30"), duration=30)
        # Fresh partner — phase 2 needs them to have waited strict_s.
        caller = _ticket(_user("dur_60"), duration=60)
        with transaction.atomic():
            no_match = PreferenceMatchingStrategy().find_match(caller)
        assert no_match is None

        # Now backdate the partner past the strict threshold.
        _backdate(first, 30)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_duration_60_delta_waits_for_phase_4(self, settings) -> None:
        # 30 + 90 → |Δ|=60, outside even phase-3's ±30. Only matches at
        # phase 4 (after loose_s).
        settings.BODY_DOUBLE_STRICT_S = 5
        settings.BODY_DOUBLE_FALLBACK_S = 10
        settings.BODY_DOUBLE_LOOSE_S = 20
        first = _ticket(_user("dur_30b"), duration=30)
        _backdate(first, 15)  # past fallback but before loose
        caller = _ticket(_user("dur_90b"), duration=90)
        with transaction.atomic():
            no_match = PreferenceMatchingStrategy().find_match(caller)
        assert no_match is None
        # Push past loose threshold.
        _backdate(first, 30)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None

    # ----- Community -----

    def test_same_community_preferred(self) -> None:
        c1 = self._make_community("Comm1")
        c2 = self._make_community("Comm2")
        # Cross-community partner exists (newer, but in a different community)
        _ticket(_user("c2_user"), community=c2)
        # Same-community partner
        same_partner = _ticket(_user("c1_user"), community=c1)
        caller = _ticket(_user("c1_caller"), community=c1)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == same_partner.pk

    def test_cross_community_only_after_fallback(self, settings) -> None:
        settings.BODY_DOUBLE_FALLBACK_S = 10
        c1 = self._make_community("CommA")
        c2 = self._make_community("CommB")
        other = _ticket(_user("other_a"), community=c2)
        caller = _ticket(_user("self_a"), community=c1)
        with transaction.atomic():
            no_match = PreferenceMatchingStrategy().find_match(caller)
        assert no_match is None
        # Backdate the partner past the fallback threshold.
        _backdate(other, 30)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == other.pk

    # ----- Work mode -----

    def test_work_mode_compat_required_in_strict_phase(self, settings) -> None:
        settings.BODY_DOUBLE_FALLBACK_S = 10
        # deep_focus + admin = incompatible at phase 1-3.
        partner = _ticket(_user("deep"), work_mode=PoolTicket.WORK_MODE_DEEP)
        caller = _ticket(_user("admin"), work_mode=PoolTicket.WORK_MODE_ADMIN)
        with transaction.atomic():
            no_match = PreferenceMatchingStrategy().find_match(caller)
        assert no_match is None
        # After loose_s they pair anyway.
        settings.BODY_DOUBLE_LOOSE_S = 5
        _backdate(partner, 30)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_any_work_mode_matches_anything_immediately(self) -> None:
        partner = _ticket(_user("wm_any"), work_mode=PoolTicket.WORK_MODE_ANY)
        caller = _ticket(_user("wm_deep"), work_mode=PoolTicket.WORK_MODE_DEEP)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    def test_same_work_mode_matches_immediately(self) -> None:
        partner = _ticket(_user("busy_a"), work_mode=PoolTicket.WORK_MODE_BUSYWORK)
        caller = _ticket(_user("busy_b"), work_mode=PoolTicket.WORK_MODE_BUSYWORK)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is not None
        assert match.pk == partner.pk

    # ----- Empty pool -----

    def test_empty_pool_returns_none(self) -> None:
        caller = _ticket(_user("solo"))
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(caller)
        assert match is None

    def test_excludes_self(self) -> None:
        u = _user("self_match")
        only = _ticket(u)
        with transaction.atomic():
            match = PreferenceMatchingStrategy().find_match(only)
        assert match is None
