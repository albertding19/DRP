"""Tests for `CommunityFallbackStrategy`.

These run the strategy directly — the higher-level `enqueue` orchestration
is covered by `test_services.py`."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.matching.community import CommunityFallbackStrategy
from apps.body_double.models import PoolTicket
from apps.communities.models import Community
from apps.communities.services import create_community


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _ticket(user: User, community: Community | None = None) -> PoolTicket:
    return PoolTicket.objects.create(
        user=user, community=community, status=PoolTicket.STATUS_WAITING
    )


def _backdate(ticket: PoolTicket, seconds_ago: int) -> None:
    """Shift `created_at` backwards so the strategy's fallback cutoff
    sees the ticket as 'old enough'."""
    PoolTicket.objects.filter(pk=ticket.pk).update(
        created_at=timezone.now() - timedelta(seconds=seconds_ago)
    )


@pytest.mark.django_db(transaction=True)
class TestCommunityFallbackStrategy:
    def _community(self, name: str) -> Community:
        owner = _user(f"owner_{name.lower()}")
        return create_community(
            creator=owner,
            name=name,
            category=Community.CATEGORY_INTEREST,
        )

    def test_same_community_matches_immediately(self) -> None:
        c = self._community("Alpha")
        first = _ticket(_user("alpha_first"), community=c)
        second = _ticket(_user("alpha_second"), community=c)

        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(second)
        assert match is not None
        assert match.pk == first.pk

    def test_different_community_no_match_within_fallback_window(self) -> None:
        c1 = self._community("Beta1")
        c2 = self._community("Beta2")
        first = _ticket(_user("beta1_waiter"), community=c1)
        _ = first  # newly created; created_at is "now"
        caller = _ticket(_user("beta2_caller"), community=c2)

        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(caller)
        # first has been waiting < FALLBACK_S → no fallback yet.
        assert match is None

    def test_different_community_matches_after_fallback_window(self, settings) -> None:
        settings.BODY_DOUBLE_FALLBACK_S = 60
        c1 = self._community("Gamma1")
        c2 = self._community("Gamma2")
        long_waiter = _ticket(_user("gamma1_oldwaiter"), community=c1)
        _backdate(long_waiter, seconds_ago=120)  # been waiting 2 min
        caller = _ticket(_user("gamma2_caller"), community=c2)

        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(caller)
        assert match is not None
        assert match.pk == long_waiter.pk

    def test_no_community_ticket_behaves_like_fifo(self) -> None:
        # First ticket has a community; second has none. The community-less
        # caller should still match (FIFO across the pool).
        c = self._community("Delta")
        first = _ticket(_user("delta_in_community"), community=c)
        caller = _ticket(_user("delta_general_pool"), community=None)

        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(caller)
        assert match is not None
        assert match.pk == first.pk

    def test_community_ticket_prefers_same_community_over_older_other(self, settings) -> None:
        """Even if there's an older partner in a different community
        (past the fallback cutoff), a same-community match wins."""
        settings.BODY_DOUBLE_FALLBACK_S = 60
        c_target = self._community("EpsilonTarget")
        c_other = self._community("EpsilonOther")

        very_old_other = _ticket(_user("eps_old_other"), community=c_other)
        _backdate(very_old_other, seconds_ago=300)

        fresh_same = _ticket(_user("eps_fresh_same"), community=c_target)
        # `fresh_same` is the newer ticket but in the caller's community.

        caller = _ticket(_user("eps_caller"), community=c_target)

        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(caller)
        # The same-community partner wins despite being newer than the
        # fallback-eligible cross-community one.
        assert match is not None
        assert match.pk == fresh_same.pk

    def test_excludes_self(self) -> None:
        c = self._community("Zeta")
        only = _ticket(_user("zeta_only"), community=c)
        with transaction.atomic():
            match = CommunityFallbackStrategy().find_match(only)
        assert match is None
