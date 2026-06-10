"""Tests for the homepage dashboard at `/`.

Covers:
  - Auth gate (anon → /accounts/start/)
  - All four panels render their main hook ids (#panel-tasks, etc.)
  - Each panel's content + empty state
  - Per-panel try/except: a crashing panel doesn't 500 the page
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double.models import BodyDoubleSession, PoolTicket
from apps.communities.models import Community
from apps.communities.services import create_community
from apps.posts.models import Post
from apps.tags.models import Tag
from apps.tasks.models import Task


def _authed(nick: str) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=f"hp_{nick}")
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


@pytest.mark.django_db
class TestHomeRouting:
    def test_home_url_resolves_to_root(self) -> None:
        assert reverse("home") == "/"

    def test_anon_redirects_to_picker(self) -> None:
        r = Client().get("/")
        assert r.status_code == 302
        assert r.url.startswith("/accounts/start/")

    def test_authed_renders_all_four_panels(self) -> None:
        # Hook ids the JS / tests rely on. Stable contract.
        client, _ = _authed("p4")
        r = client.get("/")
        assert r.status_code == 200
        body = r.content
        for hook in (
            b'id="panel-tasks"',
            b'id="panel-body-double"',
            b'id="panel-communities"',
            b'id="panel-feed"',
        ):
            assert hook in body, f"missing {hook!r}"


@pytest.mark.django_db
class TestTasksPanel:
    def test_in_progress_banner_when_task_running(self) -> None:
        client, user = _authed("tp1")
        Task.objects.create(
            user=user,
            name="Focus essay",
            duration_minutes=60,
            status=Task.STATUS_IN_PROGRESS,
            actual_start_at=timezone.now(),
        )
        r = client.get("/")
        assert b"Focus essay" in r.content
        assert b"Right now" in r.content

    def test_lists_next_three_scheduled(self) -> None:
        client, user = _authed("tp2")
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        for i, name in enumerate(["Alpha", "Beta", "Gamma", "Delta"]):
            Task.objects.create(
                user=user,
                name=name,
                duration_minutes=30,
                scheduled_start=now + timedelta(hours=i),
            )
        r = client.get("/")
        body = r.content
        assert b"Alpha" in body
        assert b"Beta" in body
        assert b"Gamma" in body
        # 4th task NOT in the top-3 strip.
        assert b"Delta" not in body

    def test_break_button_present(self) -> None:
        client, _ = _authed("tp3")
        r = client.get("/")
        assert b"I need a break" in r.content


@pytest.mark.django_db
class TestBodyDoublePanel:
    def test_idle_shows_find_cta(self) -> None:
        client, _ = _authed("bd1")
        r = client.get("/")
        assert b"Find me someone" in r.content

    def test_waiting_state(self) -> None:
        client, user = _authed("bd2")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        r = client.get("/")
        body = r.content
        assert b"Resume waiting" in body
        assert b"Cancel" in body
        assert b"Find me someone" not in body

    def test_matched_state_shows_rejoin(self) -> None:
        client, user = _authed("bd3")
        partner = User.objects.create_anonymous(nickname="hp_bd3_partner")
        session = BodyDoubleSession.objects.create(
            room_id="abc123",
            user_a=partner,
            user_b=user,
            status=BodyDoubleSession.STATUS_ACTIVE,
        )
        PoolTicket.objects.create(
            user=user,
            status=PoolTicket.STATUS_MATCHED,
            session=session,
        )
        r = client.get("/")
        body = r.content
        assert b"Rejoin your room" in body
        assert f"/body-double/room/{session.id}/".encode() in body

    def test_upcoming_state_shows_booking(self) -> None:
        from datetime import timedelta

        from django.utils import timezone

        from apps.body_double.models import ScheduledBooking

        client, user = _authed("bd4")
        ScheduledBooking.objects.create(
            user=user,
            start_at=timezone.now() + timedelta(hours=3),
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        r = client.get("/")
        body = r.content
        assert b"Booked for" in body
        assert b"View schedule" in body
        assert b"Find me someone" not in body

    def test_live_ticket_outranks_upcoming_booking(self) -> None:
        from datetime import timedelta

        from django.utils import timezone

        from apps.body_double.models import ScheduledBooking

        client, user = _authed("bd5")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        ScheduledBooking.objects.create(
            user=user,
            start_at=timezone.now() + timedelta(hours=3),
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        r = client.get("/")
        body = r.content
        assert b"Resume waiting" in body
        assert b"Booked for" not in body


@pytest.mark.django_db
class TestCommunitiesPanel:
    def test_empty_state(self) -> None:
        client, _ = _authed("cp1")
        r = client.get("/")
        assert b"You haven't joined any yet" in r.content

    def test_lists_joined_communities(self) -> None:
        client, user = _authed("cp2")
        create_community(creator=user, name="Imperial CS", category=Community.CATEGORY_COURSE)
        create_community(creator=user, name="ADHD Students", category=Community.CATEGORY_INTEREST)
        r = client.get("/")
        body = r.content
        assert b"Imperial CS" in body
        assert b"ADHD Students" in body


@pytest.mark.django_db
class TestFeedPanel:
    def test_lists_five_latest_posts(self) -> None:
        client, user = _authed("fp1")
        # Create 7 posts; oldest two should NOT appear.
        posts = []
        for i in range(7):
            posts.append(
                Post.objects.create(
                    author=user,
                    title=f"P{i}",
                    body=f"body {i}",
                )
            )
        r = client.get("/")
        body = r.content
        # Most recent five (P6..P2) should be present; P1 and P0 absent.
        for i in range(2, 7):
            assert f"P{i}".encode() in body, f"expected P{i} in feed pulse"
        for i in (0, 1):
            assert f">P{i}<".encode() not in body, f"P{i} should NOT be in top-5"

    def test_trending_tags_ordered_by_post_count(self) -> None:
        client, _ = _authed("fp2")
        Tag.objects.create(name="alpha", slug="alpha", post_count=10)
        Tag.objects.create(name="beta", slug="beta", post_count=5)
        Tag.objects.create(name="gamma", slug="gamma", post_count=1)
        r = client.get("/")
        body = r.content.decode()
        # All three present.
        assert "#alpha" in body and "#beta" in body and "#gamma" in body
        # Order: alpha appears before beta appears before gamma.
        assert body.index("#alpha") < body.index("#beta") < body.index("#gamma")


@pytest.mark.django_db
class TestPanelCrashIsolation:
    def test_panel_crash_does_not_500_page(self, monkeypatch) -> None:
        # Force one panel builder to blow up; the page must still 200 and
        # the other three panels must still render.
        from apps.core import views as core_views

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated DB hiccup")

        monkeypatch.setattr(core_views, "_build_communities_panel", _boom)
        client, _ = _authed("crash")
        r = client.get("/")
        assert r.status_code == 200
        assert b'id="panel-communities"' in r.content
        # The other panels are still there.
        assert b'id="panel-tasks"' in r.content
        assert b'id="panel-feed"' in r.content
