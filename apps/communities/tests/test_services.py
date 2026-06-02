"""Tests for communities services + member_count denormalisation signals."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.communities.models import Community, CommunityMembership
from apps.communities.services import (
    communities_for_category,
    create_community,
    join_community,
    leave_community,
    user_communities,
)


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


@pytest.mark.django_db
class TestCreateCommunity:
    def test_creates_with_slug_from_name(self) -> None:
        u = _user("creator1")
        c = create_community(creator=u, name="Imperial CS", category=Community.CATEGORY_COURSE)
        assert c.slug == "imperial-cs"
        assert c.name == "Imperial CS"
        assert c.category == Community.CATEGORY_COURSE
        assert c.creator == u

    def test_creator_is_auto_joined(self) -> None:
        u = _user("autojoiner")
        c = create_community(creator=u, name="Auto Join", category=Community.CATEGORY_INTEREST)
        assert CommunityMembership.objects.filter(user=u, community=c).exists()
        c.refresh_from_db()
        assert c.member_count == 1

    def test_slug_collision_adds_suffix(self) -> None:
        u1 = _user("creator_a")
        u2 = _user("creator_b")
        c1 = create_community(creator=u1, name="Maths", category=Community.CATEGORY_INTEREST)
        c2 = create_community(creator=u2, name="maths", category=Community.CATEGORY_INTEREST)
        assert c1.slug == "maths"
        assert c2.slug != c1.slug
        assert c2.slug.startswith("maths-")

    def test_empty_name_rejected(self) -> None:
        u = _user("emptyname")
        with pytest.raises(ValueError):
            create_community(creator=u, name="   ", category=Community.CATEGORY_COURSE)

    def test_unknown_category_rejected(self) -> None:
        u = _user("badcat")
        with pytest.raises(ValueError):
            create_community(creator=u, name="X", category="bogus")

    def test_anonymous_creator_persisted_as_null(self) -> None:
        class _Anon:
            is_authenticated = False

        c = create_community(
            creator=_Anon(), name="Anon Owned", category=Community.CATEGORY_INTEREST
        )
        assert c.creator_id is None
        # And not auto-joined.
        assert c.member_count == 0


@pytest.mark.django_db
class TestJoinLeaveCommunity:
    def _setup(self) -> tuple[User, Community]:
        owner = _user("owner_joinleave")
        c = create_community(
            creator=owner, name="JoinLeave Co", category=Community.CATEGORY_INTEREST
        )
        return _user("joiner"), c

    def test_join_creates_membership_and_increments_count(self) -> None:
        joiner, c = self._setup()
        join_community(user=joiner, community=c)
        c.refresh_from_db()
        # Owner + joiner = 2
        assert c.member_count == 2
        assert CommunityMembership.objects.filter(user=joiner, community=c).exists()

    def test_join_is_idempotent(self) -> None:
        joiner, c = self._setup()
        join_community(user=joiner, community=c)
        join_community(user=joiner, community=c)
        c.refresh_from_db()
        assert c.member_count == 2  # not 3
        assert CommunityMembership.objects.filter(user=joiner, community=c).count() == 1

    def test_leave_deletes_and_decrements(self) -> None:
        joiner, c = self._setup()
        join_community(user=joiner, community=c)
        n = leave_community(user=joiner, community=c)
        assert n == 1
        c.refresh_from_db()
        assert c.member_count == 1  # owner remains
        assert not CommunityMembership.objects.filter(user=joiner, community=c).exists()

    def test_leave_when_not_member_is_noop(self) -> None:
        joiner, c = self._setup()
        n = leave_community(user=joiner, community=c)
        assert n == 0
        c.refresh_from_db()
        assert c.member_count == 1  # owner still


@pytest.mark.django_db
class TestUserCommunities:
    def test_returns_only_joined_communities(self) -> None:
        u = _user("multiowner")
        c1 = create_community(creator=u, name="A", category=Community.CATEGORY_INTEREST)
        # u is auto-joined to c1. Create c2 owned by someone else; u is NOT a member.
        other = _user("other_owner")
        create_community(creator=other, name="B", category=Community.CATEGORY_COURSE)
        comms = list(user_communities(u))
        assert comms == [c1]

    def test_anonymous_user_returns_empty(self) -> None:
        class _Anon:
            is_authenticated = False

        assert user_communities(_Anon()).count() == 0


@pytest.mark.django_db
class TestCommunitiesForCategory:
    def test_filters_and_orders_by_popularity(self) -> None:
        u = _user("popularowner")
        big = create_community(creator=u, name="Big", category=Community.CATEGORY_INTEREST)
        small = create_community(creator=u, name="Small", category=Community.CATEGORY_INTEREST)
        other_cat = create_community(creator=u, name="Course X", category=Community.CATEGORY_COURSE)
        # Pump up big's member count
        for i in range(5):
            joiner = _user(f"popjoiner_{i}")
            join_community(user=joiner, community=big)

        result = list(communities_for_category(Community.CATEGORY_INTEREST))
        assert other_cat not in result
        # `big` should come before `small` because of higher member_count.
        assert result.index(big) < result.index(small)
