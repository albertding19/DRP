"""Tests for matching strategies."""

from __future__ import annotations

import pytest
from django.db import transaction

from apps.accounts.models import User
from apps.body_double.matching.fifo import FIFOStrategy
from apps.body_double.models import PoolTicket


@pytest.mark.django_db(transaction=True)
class TestFIFOStrategy:
    """First-two-in-pool gets paired. Order is by `created_at`."""

    def _make_ticket(self, nickname: str) -> PoolTicket:
        u = User.objects.create_anonymous(nickname=nickname)
        return PoolTicket.objects.create(user=u, status=PoolTicket.STATUS_WAITING)

    def test_empty_pool_returns_none(self) -> None:
        ticket = self._make_ticket("solo_caller")
        with transaction.atomic():
            assert FIFOStrategy().find_match(ticket) is None

    def test_one_waiting_partner_gets_paired(self) -> None:
        first = self._make_ticket("first_waiter")
        second = self._make_ticket("second_caller")
        with transaction.atomic():
            match = FIFOStrategy().find_match(second)
        assert match is not None
        assert match.pk == first.pk

    def test_self_is_excluded(self) -> None:
        """A ticket should never match itself even if it's the only one waiting."""
        ticket = self._make_ticket("only_caller")
        with transaction.atomic():
            assert FIFOStrategy().find_match(ticket) is None

    def test_oldest_waiter_is_chosen(self) -> None:
        a = self._make_ticket("oldest_waiter")
        self._make_ticket("middle_waiter")
        self._make_ticket("newest_waiter")
        caller = self._make_ticket("the_caller")
        with transaction.atomic():
            match = FIFOStrategy().find_match(caller)
        assert match is not None
        assert match.pk == a.pk

    def test_non_waiting_tickets_skipped(self) -> None:
        cancelled = self._make_ticket("former_waiter")
        cancelled.status = PoolTicket.STATUS_CANCELLED
        cancelled.save(update_fields=["status"])

        caller = self._make_ticket("seeking_partner")
        with transaction.atomic():
            assert FIFOStrategy().find_match(caller) is None


@pytest.mark.django_db(transaction=True)
class TestRematchOnAging:
    """`find_match` only runs at enqueue; `try_rematch` re-runs it for a
    waiting ticket so the time-based phase loosening can fire for two users
    who were stuck waiting — the WS-driven recheck path."""

    def test_stuck_pair_matches_after_aging(self, settings) -> None:
        from datetime import timedelta

        from django.utils import timezone

        from apps.body_double.services import enqueue, try_rematch

        # Exercise the preference phases directly (no timetable dimension)
        # with deterministic thresholds.
        settings.BODY_DOUBLE_MATCHING_STRATEGY = (
            "apps.body_double.matching.preferences.PreferenceMatchingStrategy"
        )
        settings.BODY_DOUBLE_STRICT_S = 30
        settings.BODY_DOUBLE_FALLBACK_S = 60
        settings.BODY_DOUBLE_LOOSE_S = 120

        a = User.objects.create_anonymous(nickname="rm_partner")
        b = User.objects.create_anonymous(nickname="rm_caller")

        # A waits (60 min). B joins (30 min): the ±15 duration gate excludes
        # A at phase 1, and A has only just arrived, so the looser phase 2
        # (needs A to have waited STRICT_S) doesn't apply yet → no match.
        ta, _ = enqueue(user=a, duration_minutes=60)
        tb, session = enqueue(user=b, duration_minutes=30)
        assert session is None  # genuinely stuck — the bug's symptom

        # Time passes: A has now waited past STRICT_S.
        PoolTicket.objects.filter(pk=ta.pk).update(
            created_at=timezone.now() - timedelta(seconds=35)
        )

        # The WS recheck re-runs the matcher for B → they pair at phase 2.
        session = try_rematch(user_id=b.id)
        assert session is not None
        ta.refresh_from_db()
        tb.refresh_from_db()
        assert ta.status == PoolTicket.STATUS_MATCHED
        assert tb.status == PoolTicket.STATUS_MATCHED
        assert ta.session_id == tb.session_id == session.id

    def test_rematch_noop_without_waiting_ticket(self) -> None:
        from apps.body_double.services import try_rematch

        u = User.objects.create_anonymous(nickname="rm_none")
        assert try_rematch(user_id=u.id) is None
