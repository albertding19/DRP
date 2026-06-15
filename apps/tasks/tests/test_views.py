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

    def test_add_leaves_task_in_backlog(self) -> None:
        # Adding does NOT schedule — the task waits in the backlog ("To do")
        # until the user clicks "Schedule my day" (tasks:plan).
        client, user = _authed("add4")
        client.post(
            "/tasks/add/",
            {"name": "Later", "duration_minutes": "30"},
            HTTP_HX_REQUEST="true",
        )
        t = Task.objects.get(user=user, name="Later")
        assert t.scheduled_start is None


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
        # Busy blocks are today-only — the form posts `HH:MM` times.
        r = client.post(
            "/tasks/busy/add/",
            {"name": "Lecture", "start_at": "14:00", "end_at": "15:00"},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert BusyBlock.objects.filter(user=user, name="Lecture").exists()

    def test_add_busy_reschedules_reflow_only(self, monkeypatch) -> None:
        # Adding a blocked time auto-reschedules, but only reflows already-
        # scheduled tasks (it never pulls the backlog onto today).
        from unittest.mock import MagicMock

        from apps.tasks import views as tasks_views

        client, user = _authed("bu3")
        fake_plan = MagicMock(return_value={"placed": 0, "leftover": 0})
        monkeypatch.setattr(tasks_views, "auto_plan", fake_plan)
        client.post(
            "/tasks/busy/add/",
            {"name": "Gym", "start_at": "16:00", "end_at": "17:00"},
            HTTP_HX_REQUEST="true",
        )
        fake_plan.assert_called_once_with(user=user, include_backlog=False)

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

    def test_end_clears_mode_and_triggers_replan(self, client_with_session, monkeypatch) -> None:
        # The view's job is wiring: clear the mode flag and invoke the
        # replanner. The replan maths itself is covered by TestAutoPlan
        # with pinned clocks — asserting on real scheduled_start values
        # here made the test fail near the 21:00 work-window end.
        from unittest.mock import MagicMock

        from apps.tasks import views as tasks_views

        client, user = client_with_session
        fake_plan = MagicMock(return_value={"placed": 0, "leftover": 0})
        monkeypatch.setattr(tasks_views, "auto_plan", fake_plan)

        client.post("/tasks/work/start/", HTTP_HX_REQUEST="true")
        r = client.post("/tasks/work/end/", HTTP_HX_REQUEST="true")
        assert r.status_code == 200
        assert b"Start work" in r.content  # toggled back
        # Reflow only — ending free-work never pulls the backlog onto today.
        fake_plan.assert_called_once_with(user=user, include_backlog=False)
        assert "free_work_started_at" not in client.session

    def test_room_embed_region_carries_the_button(self, client_with_session) -> None:
        client, _ = client_with_session
        r = client.get("/tasks/region/")
        assert b"Start work" in r.content


@pytest.mark.django_db
class TestContinuedLabel:
    """The remaining slice of a break-interrupted task is marked "(continued)"
    on the timetable."""

    def test_is_continued_property(self) -> None:
        _, user = _authed("cont_prop")
        t = create_task(user=user, name="Essay", duration_minutes=30)
        # Fresh pending task — not continued.
        assert t.is_continued is False
        # Partially done but still pending (paused by a break) — continued.
        t.time_spent_minutes = 15
        assert t.is_continued is True
        # Once it's being worked on again it's "doing now", not continued.
        t.status = Task.STATUS_IN_PROGRESS
        assert t.is_continued is False

    def test_continued_task_labelled_on_timetable(self) -> None:
        client, user = _authed("cont_row")
        t = create_task(user=user, name="Essay", duration_minutes=30)
        # 15 min already done, rescheduled onto today after a break.
        Task.objects.filter(pk=t.pk).update(time_spent_minutes=15, scheduled_start=timezone.now())
        r = client.get("/tasks/")
        assert r.status_code == 200
        assert b"Essay" in r.content
        assert b"(continued)" in r.content
        # Only the remaining 15 minutes are left to do.
        assert b"15 min" in r.content

    def test_fresh_scheduled_task_has_no_continued_label(self) -> None:
        client, user = _authed("cont_fresh")
        t = create_task(user=user, name="Fresh", duration_minutes=30)
        Task.objects.filter(pk=t.pk).update(scheduled_start=timezone.now())
        r = client.get("/tasks/")
        assert r.status_code == 200
        assert b"Fresh" in r.content
        assert b"(continued)" not in r.content
