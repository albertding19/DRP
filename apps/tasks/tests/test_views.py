"""Smoke tests for tasks views — HTTP layer."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.tasks.models import BusyBlock, Task
from apps.tasks.services import create_task


def _authed(nick: str) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=f"vw_{nick}")
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


@pytest.mark.django_db
class TestIndex:
    def test_unauthed_redirected(self) -> None:
        r = Client().get("/tasks/")
        assert r.status_code == 302

    def test_renders_empty_state(self) -> None:
        client, _ = _authed("empty")
        r = client.get("/tasks/")
        assert r.status_code == 200
        # Empty state copy varies; just confirm the page rendered.
        assert b"task" in r.content.lower()


@pytest.mark.django_db
class TestAddTask:
    def test_add_succeeds(self) -> None:
        client, user = _authed("add1")
        r = client.post("/tasks/add/", {"name": "Read paper", "duration_minutes": "30"})
        # Non-HTMX redirects to index.
        assert r.status_code == 302
        assert Task.objects.filter(user=user, name="Read paper").exists()

    def test_add_with_htmx_returns_partial(self) -> None:
        client, user = _authed("add2")
        r = client.post(
            "/tasks/add/",
            {"name": "Essay", "duration_minutes": "45", "priority": "high"},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert Task.objects.filter(user=user, name="Essay", priority=Task.PRIORITY_HIGH).exists()

    def test_validation_error_htmx_returns_form_with_retarget(self) -> None:
        client, _ = _authed("add3")
        r = client.post(
            "/tasks/add/",
            {"name": "", "duration_minutes": "abc"},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 422
        assert r.headers.get("HX-Retarget") == "#add-task-form"
        assert r.headers.get("HX-Reswap") == "outerHTML"


@pytest.mark.django_db
class TestPlanEndpoint:
    def test_plan_returns_timetable(self) -> None:
        client, user = _authed("pl1")
        create_task(user=user, name="A", duration_minutes=30)
        r = client.post("/tasks/plan/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200


@pytest.mark.django_db
class TestBreakEndpoint:
    def test_break_creates_block(self) -> None:
        client, user = _authed("br1")
        r = client.post("/tasks/break/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert BusyBlock.objects.filter(user=user, kind=BusyBlock.KIND_BREAK).exists()


@pytest.mark.django_db
class TestStartTask:
    def test_start_without_body_double(self) -> None:
        client, user = _authed("st1")
        t = create_task(user=user, name="A", duration_minutes=30)
        r = client.post(f"/tasks/{t.id}/start/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        t.refresh_from_db()
        assert t.status == Task.STATUS_IN_PROGRESS

    def test_start_with_match_returns_hx_redirect(self, monkeypatch) -> None:
        client, user = _authed("st2")
        t = create_task(
            user=user,
            name="A",
            duration_minutes=30,
            body_double_preferred=True,
        )

        class _Sess:
            id = 99
            room_id = "abc123"

        def _matched(**kwargs):
            return None, _Sess()

        monkeypatch.setattr("apps.body_double.services.enqueue", _matched)
        r = client.post(f"/tasks/{t.id}/start/", HTTP_HX_REQUEST="true")
        assert r.status_code == 204
        assert "/body-double/room/99/" in r.headers.get("HX-Redirect", "")


@pytest.mark.django_db
class TestLifecycle:
    def test_done(self) -> None:
        client, user = _authed("li1")
        t = create_task(user=user, name="A", duration_minutes=30)
        r = client.post(f"/tasks/{t.id}/done/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        t.refresh_from_db()
        assert t.status == Task.STATUS_DONE

    def test_skip(self) -> None:
        client, user = _authed("li2")
        t = create_task(user=user, name="A", duration_minutes=30)
        r = client.post(f"/tasks/{t.id}/skip/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        t.refresh_from_db()
        assert t.status == Task.STATUS_SKIPPED

    def test_delete_removes_and_returns_full_region(self) -> None:
        client, user = _authed("li3")
        t = create_task(user=user, name="A", duration_minutes=30)
        r = client.post(f"/tasks/{t.id}/delete/", HTTP_HX_REQUEST="true")
        # Now returns the re-flowed schedule (200) instead of a bare 204,
        # because auto-plan runs after delete and the remaining tasks may
        # have shifted into the freed slot.
        assert r.status_code == 200
        assert not Task.objects.filter(pk=t.id).exists()

    def test_delete_from_timetable_works(self) -> None:
        # Scheduled tasks now expose a delete button too, not just backlog.
        client, user = _authed("li4")
        t = create_task(user=user, name="A", duration_minutes=30)
        # auto_plan would normally place it, but we don't need that to test delete.
        r = client.post(f"/tasks/{t.id}/delete/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert not Task.objects.filter(pk=t.id).exists()


@pytest.mark.django_db
class TestBusyEndpoint:
    def test_add_busy(self) -> None:
        client, user = _authed("bu1")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        r = client.post(
            "/tasks/busy/add/",
            {"name": "Lecture", "start_at": start.isoformat(), "end_at": end.isoformat()},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert BusyBlock.objects.filter(user=user, name="Lecture").exists()

    def test_delete_busy(self) -> None:
        client, user = _authed("bu2")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        b = BusyBlock.objects.create(
            user=user,
            name="X",
            start_at=start,
            end_at=start + timedelta(hours=1),
            kind=BusyBlock.KIND_MANUAL,
        )
        r = client.post(f"/tasks/busy/{b.id}/delete/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert not BusyBlock.objects.filter(pk=b.id).exists()


@pytest.mark.django_db
class TestNonHtmxFallback:
    def test_add_redirects_to_index(self) -> None:
        client, _ = _authed("nh1")
        r = client.post("/tasks/add/", {"name": "A", "duration_minutes": "30"})
        assert r.status_code == 302
        assert r.url == "/tasks/"


@pytest.mark.django_db
class TestRegionPartial:
    """GET /tasks/region/ serves the bare #full-region partial so other
    pages (the body-double room) can embed the live timetable."""

    def test_returns_partial_without_page_chrome(self, client_with_session) -> None:
        client, user = client_with_session
        from django.utils import timezone

        from apps.tasks.models import Task

        Task.objects.create(
            user=user, name="Embedded task", duration_minutes=30, scheduled_start=timezone.now()
        )
        r = client.get("/tasks/region/")
        assert r.status_code == 200
        assert b"Embedded task" in r.content
        # Partial only — no <html> shell.
        assert b"<html" not in r.content

    def test_anon_redirected(self) -> None:
        from django.test import Client

        assert Client().get("/tasks/region/").status_code == 302


@pytest.mark.django_db
class TestFreeWorkMode:
    """Start work = open-ended focus block; End work = replan every
    remaining task starting from the click."""

    def test_start_shows_end_button(self, client_with_session) -> None:
        client, _ = client_with_session
        r = client.post("/tasks/work/start/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert b"Working freely since" in r.content
        assert b"End work" in r.content

    def test_end_replans_remaining_tasks_from_now(self, client_with_session) -> None:
        client, user = client_with_session
        from django.utils import timezone

        from apps.tasks.models import Task

        # A stale plan from earlier in the day.
        morning = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        t1 = Task.objects.create(
            user=user, name="Leftover A", duration_minutes=30, scheduled_start=morning
        )
        t2 = Task.objects.create(user=user, name="Leftover B", duration_minutes=30)
        client.post("/tasks/work/start/", HTTP_HX_REQUEST="true")
        before = timezone.now()
        r = client.post("/tasks/work/end/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert b"Start work" in r.content  # toggled back
        t1.refresh_from_db()
        t2.refresh_from_db()
        # Both pending tasks re-laid-out from the click onwards (when the
        # work window allows; outside it they fall to the backlog).
        now_local = timezone.localtime(before)
        if 9 <= now_local.hour < 21:
            assert t1.scheduled_start is not None
            assert t1.scheduled_start >= before - timezone.timedelta(seconds=5)
            if t2.scheduled_start is not None:
                assert t2.scheduled_start >= before - timezone.timedelta(seconds=5)

    def test_room_embed_region_carries_the_button(self, client_with_session) -> None:
        client, _ = client_with_session
        r = client.get("/tasks/region/")
        assert b"Start work" in r.content
