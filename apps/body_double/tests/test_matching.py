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
