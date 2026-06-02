"""Smoke tests for communities views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.communities.models import Community, CommunityMembership
from apps.communities.services import create_community


def _authed(nick: str) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=nick)
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


@pytest.mark.django_db
class TestListView:
    def test_unauthed_redirected(self) -> None:
        r = Client().get("/communities/")
        assert r.status_code == 302

    def test_renders_empty(self) -> None:
        client, _ = _authed("listempty")
        r = client.get("/communities/")
        assert r.status_code == 200
        assert b"No communities yet" in r.content

    def test_renders_with_communities(self) -> None:
        client, u = _authed("listfull")
        create_community(creator=u, name="Renderable", category=Community.CATEGORY_INTEREST)
        r = client.get("/communities/")
        assert r.status_code == 200
        assert b"Renderable" in r.content

    def test_category_filter(self) -> None:
        client, u = _authed("listcatfilter")
        create_community(creator=u, name="Course A", category=Community.CATEGORY_COURSE)
        create_community(creator=u, name="Interest B", category=Community.CATEGORY_INTEREST)
        r = client.get("/communities/?category=course")
        assert r.status_code == 200
        body = r.content
        assert b"Course A" in body
        assert b"Interest B" not in body

    def test_search_filter(self) -> None:
        client, u = _authed("listsearch")
        create_community(
            creator=u, name="Specific Search Target", category=Community.CATEGORY_INTEREST
        )
        create_community(creator=u, name="Other Thing", category=Community.CATEGORY_INTEREST)
        r = client.get("/communities/?q=specific")
        assert r.status_code == 200
        body = r.content
        assert b"Specific Search Target" in body
        assert b"Other Thing" not in body


@pytest.mark.django_db
class TestDetailView:
    def test_unauthed_redirected(self) -> None:
        r = Client().get("/communities/x/")
        assert r.status_code == 302

    def test_missing_404(self) -> None:
        client, _ = _authed("detailmissing")
        r = client.get("/communities/nonexistent-slug/")
        assert r.status_code == 404

    def test_renders_for_member(self) -> None:
        client, u = _authed("detailmember")
        c = create_community(creator=u, name="Detail Demo", category=Community.CATEGORY_INTEREST)
        r = client.get(f"/communities/{c.slug}/")
        assert r.status_code == 200
        body = r.content
        assert b"Detail Demo" in body
        # Member sees the "Find a body double here" CTA.
        assert b"Find a body double here" in body
        # Leave button shows because user IS a member.
        assert b"Leave" in body

    def test_renders_for_non_member_shows_join(self) -> None:
        owner = User.objects.create_anonymous(nickname="detailowner")
        c = create_community(
            creator=owner, name="Stranger View", category=Community.CATEGORY_INTEREST
        )
        client, _ = _authed("detailstranger")
        r = client.get(f"/communities/{c.slug}/")
        assert r.status_code == 200
        body = r.content
        assert b"Join" in body
        assert b"Find a body double here" not in body  # only members see it


@pytest.mark.django_db
class TestCreateView:
    def test_get_renders_form(self) -> None:
        client, _ = _authed("createget")
        r = client.get("/communities/new/")
        assert r.status_code == 200
        assert b"Create a community" in r.content

    def test_post_valid_creates_redirects_to_detail(self) -> None:
        client, _ = _authed("createpost")
        r = client.post(
            "/communities/new/",
            {
                "name": "Brand New",
                "category": "interest",
                "description": "Hi.",
            },
        )
        assert r.status_code == 302
        c = Community.objects.get(name="Brand New")
        assert r.url == f"/communities/{c.slug}/"

    def test_post_missing_name_re_renders_with_error(self) -> None:
        client, _ = _authed("createmissingname")
        r = client.post(
            "/communities/new/",
            {"name": "", "category": "interest"},
        )
        assert r.status_code == 200
        assert b"Give your community a name" in r.content
        assert Community.objects.count() == 0

    def test_post_invalid_category_rejected(self) -> None:
        client, _ = _authed("createbadcat")
        r = client.post(
            "/communities/new/",
            {"name": "Foo", "category": "bogus"},
        )
        assert r.status_code == 200
        assert b"Pick one of the available categories" in r.content
        assert Community.objects.count() == 0


@pytest.mark.django_db
class TestJoinLeave:
    def test_join_adds_membership_and_redirects(self) -> None:
        owner = User.objects.create_anonymous(nickname="joinowner")
        c = create_community(creator=owner, name="Joinable", category=Community.CATEGORY_INTEREST)
        client, user = _authed("joinerview")
        r = client.post(f"/communities/{c.slug}/join/")
        assert r.status_code == 302
        assert CommunityMembership.objects.filter(user=user, community=c).exists()

    def test_leave_removes_membership(self) -> None:
        client, user = _authed("leaverview")
        c = create_community(creator=user, name="Leavable", category=Community.CATEGORY_INTEREST)
        # User is auto-joined as creator. Now leave.
        r = client.post(f"/communities/{c.slug}/leave/")
        assert r.status_code == 302
        assert not CommunityMembership.objects.filter(user=user, community=c).exists()

    def test_join_missing_404(self) -> None:
        client, _ = _authed("join404")
        r = client.post("/communities/no-such-slug/join/")
        assert r.status_code == 404

    def test_join_idempotent(self) -> None:
        client, user = _authed("joinidempview")
        c = create_community(creator=user, name="Idemp", category=Community.CATEGORY_INTEREST)
        # Already a member; another POST should not duplicate.
        client.post(f"/communities/{c.slug}/join/")
        assert CommunityMembership.objects.filter(user=user, community=c).count() == 1
