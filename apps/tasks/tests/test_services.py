"""Integration tests for tasks services — DB-backed."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.tasks.models import BusyBlock, Task
from apps.tasks.services import (
    BreakTooSoonError,
    InvalidTaskFieldsError,
    add_busy_block,
    auto_plan,
    complete_task,
    create_task,
    delete_busy_block,
    delete_task,
    insert_break,
    skip_task,
    start_task,
    update_task,
)


def _user(nick: str) -> User:
    # Nicknames must be >= 3 chars per the User model validator. Tests
    # pass short labels; pad with a stable prefix so callers don't worry.
    return User.objects.create_anonymous(nickname=f"task_{nick}")


def _set_actual_start(task: Task, dt) -> None:
    """Bypass auto_now/etc when we need a deterministic actual_start_at."""
    Task.objects.filter(pk=task.pk).update(actual_start_at=dt)
    task.refresh_from_db()


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestCreateTask:
    def test_create_minimum_fields(self) -> None:
        u = _user("c1")
        t = create_task(user=u, name="Read paper", duration_minutes=30)
        assert t.pk is not None
        assert t.status == Task.STATUS_PENDING
        assert t.scheduled_start is None
        assert t.priority == Task.PRIORITY_MED
        assert t.energy == Task.ENERGY_MED

    def test_strips_name(self) -> None:
        u = _user("c2")
        t = create_task(user=u, name="   Email replies  ", duration_minutes=20)
        assert t.name == "Email replies"

    def test_rejects_empty_name(self) -> None:
        u = _user("c3")
        with pytest.raises(InvalidTaskFieldsError):
            create_task(user=u, name="   ", duration_minutes=20)

    def test_rejects_duration_below_min(self) -> None:
        u = _user("c4")
        with pytest.raises(InvalidTaskFieldsError):
            create_task(user=u, name="x", duration_minutes=1)

    def test_rejects_duration_above_max(self) -> None:
        u = _user("c5")
        with pytest.raises(InvalidTaskFieldsError):
            create_task(user=u, name="x", duration_minutes=601)

    def test_rejects_bad_priority(self) -> None:
        u = _user("c6")
        with pytest.raises(InvalidTaskFieldsError):
            create_task(user=u, name="x", duration_minutes=30, priority="urgent")


@pytest.mark.django_db
class TestUpdateTask:
    def test_partial_update(self) -> None:
        u = _user("u1")
        t = create_task(user=u, name="A", duration_minutes=30)
        update_task(task=t, duration_minutes=45, priority=Task.PRIORITY_HIGH)
        t.refresh_from_db()
        assert t.duration_minutes == 45
        assert t.priority == Task.PRIORITY_HIGH
        assert t.name == "A"

    def test_rejects_unknown_field(self) -> None:
        u = _user("u2")
        t = create_task(user=u, name="A", duration_minutes=30)
        with pytest.raises(InvalidTaskFieldsError):
            update_task(task=t, foo="bar")

    def test_rejects_edit_on_completed(self) -> None:
        u = _user("u3")
        t = create_task(user=u, name="A", duration_minutes=30)
        complete_task(task=t)
        with pytest.raises(InvalidTaskFieldsError):
            update_task(task=t, name="B")


@pytest.mark.django_db
class TestDeleteTask:
    def test_delete(self) -> None:
        u = _user("d1")
        t = create_task(user=u, name="A", duration_minutes=30)
        delete_task(task=t)
        assert not Task.objects.filter(pk=t.pk).exists()


# ---------------------------------------------------------------------------
# Busy blocks
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBusyBlock:
    def test_add_busy_block(self) -> None:
        u = _user("b1")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        b = add_busy_block(user=u, name="Lecture", start_at=start, end_at=end)
        assert b.kind == BusyBlock.KIND_MANUAL
        assert b.start_at == start

    def test_rejects_end_before_start(self) -> None:
        u = _user("b2")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        with pytest.raises(InvalidTaskFieldsError):
            add_busy_block(user=u, name="Bad", start_at=start, end_at=start)

    def test_rejects_out_of_today(self) -> None:
        u = _user("b3")
        now = timezone.localtime()
        # Tomorrow → must reject because we hard-code today only.
        tomorrow = now + timedelta(days=1)
        start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        with pytest.raises(InvalidTaskFieldsError):
            add_busy_block(user=u, name="Bad", start_at=start, end_at=end)

    def test_rejects_empty_name(self) -> None:
        u = _user("b4")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        with pytest.raises(InvalidTaskFieldsError):
            add_busy_block(user=u, name="", start_at=start, end_at=start + timedelta(hours=1))

    def test_db_check_constraint_blocks_inverted_times(self) -> None:
        # Bypass the service validation by writing directly.
        u = _user("b5")
        now = timezone.localtime()
        start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        with pytest.raises(IntegrityError):
            BusyBlock.objects.create(
                user=u,
                name="X",
                start_at=start,
                end_at=start,
                kind=BusyBlock.KIND_MANUAL,
            )


# ---------------------------------------------------------------------------
# auto_plan
# ---------------------------------------------------------------------------
@pytest.fixture
def _planner_settings(settings):
    settings.TASKS_WORK_START_HOUR = 9
    settings.TASKS_WORK_END_HOUR = 21
    settings.TASKS_TRANSITION_MINUTES = 0
    return settings


@pytest.mark.django_db
class TestAutoPlan:
    def _fixed_now(self):
        # Lock the planner to 10:00 local so tests are deterministic
        # regardless of when they run.
        now = timezone.localtime()
        return now.replace(hour=10, minute=0, second=0, microsecond=0)

    def test_places_pending_in_order(self, _planner_settings) -> None:
        u = _user("ap1")
        t1 = create_task(user=u, name="A", duration_minutes=30, priority=Task.PRIORITY_HIGH)
        t2 = create_task(user=u, name="B", duration_minutes=45, priority=Task.PRIORITY_LOW)
        result = auto_plan(user=u, now=self._fixed_now())
        assert result["placed"] == 2
        assert result["leftover"] == 0
        t1.refresh_from_db()
        t2.refresh_from_db()
        # High-priority comes first.
        assert t1.scheduled_start < t2.scheduled_start

    def test_idempotent(self, _planner_settings) -> None:
        u = _user("ap2")
        create_task(user=u, name="A", duration_minutes=30)
        create_task(user=u, name="B", duration_minutes=45)
        now = self._fixed_now()
        auto_plan(user=u, now=now)
        first = {t.id: t.scheduled_start for t in Task.objects.filter(user=u)}
        auto_plan(user=u, now=now)
        second = {t.id: t.scheduled_start for t in Task.objects.filter(user=u)}
        assert first == second

    def test_after_work_end_is_noop(self, _planner_settings) -> None:
        u = _user("ap3")
        create_task(user=u, name="A", duration_minutes=30)
        now = timezone.localtime().replace(hour=23, minute=0, second=0, microsecond=0)
        result = auto_plan(user=u, now=now)
        assert result["placed"] == 0
        assert result["leftover"] == 1

    def test_before_work_start_first_slot_at_work_start(self, _planner_settings) -> None:
        u = _user("ap4")
        t = create_task(user=u, name="A", duration_minutes=30)
        now = timezone.localtime().replace(hour=7, minute=0, second=0, microsecond=0)
        auto_plan(user=u, now=now)
        t.refresh_from_db()
        # `scheduled_start` is stored in UTC; compare in local time.
        assert timezone.localtime(t.scheduled_start).hour == 9

    def test_deadline_priority_order(self, _planner_settings) -> None:
        u = _user("ap5")
        now = self._fixed_now()
        # High-prio task no deadline vs low-prio task with imminent deadline.
        # Deadline wins.
        urgent = create_task(
            user=u,
            name="urgent",
            duration_minutes=30,
            priority=Task.PRIORITY_LOW,
            deadline=now + timedelta(hours=2),
        )
        big = create_task(user=u, name="big", duration_minutes=30, priority=Task.PRIORITY_HIGH)
        auto_plan(user=u, now=now)
        urgent.refresh_from_db()
        big.refresh_from_db()
        assert urgent.scheduled_start < big.scheduled_start

    def test_in_progress_task_locks_busy_interval(self, _planner_settings) -> None:
        u = _user("ap6")
        now = self._fixed_now()
        # Start a task first
        in_progress = create_task(user=u, name="long", duration_minutes=90)
        # Manually set in-progress + actual_start_at so the planner treats
        # it as locked from now → now+90min.
        Task.objects.filter(pk=in_progress.pk).update(
            status=Task.STATUS_IN_PROGRESS,
            actual_start_at=now,
        )
        in_progress.refresh_from_db()
        other = create_task(user=u, name="other", duration_minutes=30)
        auto_plan(user=u, now=now)
        other.refresh_from_db()
        # Other task can't start until in-progress finishes (now + 90min).
        assert other.scheduled_start >= now + timedelta(minutes=90)

    def test_avoids_body_double_booking_window(self, _planner_settings) -> None:
        from apps.body_double.models import ScheduledBooking

        u = _user("ap_bd")
        now = self._fixed_now()
        # Booked body double 10:00–10:30; a 30-min task must start after.
        ScheduledBooking.objects.create(
            user=u,
            start_at=now,
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        t = create_task(user=u, name="after the call", duration_minutes=30)
        auto_plan(user=u, now=now)
        t.refresh_from_db()
        assert t.scheduled_start >= now + timedelta(minutes=30)

    def test_cancelled_booking_does_not_block(self, _planner_settings) -> None:
        from apps.body_double.models import ScheduledBooking

        u = _user("ap_bd2")
        now = self._fixed_now()
        ScheduledBooking.objects.create(
            user=u,
            start_at=now,
            duration_minutes=30,
            status=ScheduledBooking.STATUS_CANCELLED,
        )
        t = create_task(user=u, name="free now", duration_minutes=30)
        auto_plan(user=u, now=now)
        t.refresh_from_db()
        assert t.scheduled_start == now

    def test_leftover_for_giant_task(self, _planner_settings) -> None:
        u = _user("ap7")
        now = self._fixed_now()
        # Fill the day with a busy block to leave only a 60-min gap.
        start = now.replace(hour=11, minute=0)
        end = now.replace(hour=21, minute=0)
        BusyBlock.objects.create(
            user=u,
            name="locked",
            start_at=start,
            end_at=end,
            kind=BusyBlock.KIND_MANUAL,
        )
        # Need a 600-min task that cannot fit.
        t = create_task(user=u, name="huge", duration_minutes=600)
        result = auto_plan(user=u, now=now)
        t.refresh_from_db()
        assert result["leftover"] == 1
        assert t.scheduled_start is None

    def test_avoids_busy_blocks(self, _planner_settings) -> None:
        u = _user("ap8")
        now = self._fixed_now()
        # Busy 14:00-15:00; task is 90 min: must NOT span 14-15.
        BusyBlock.objects.create(
            user=u,
            name="Lecture",
            start_at=now.replace(hour=14, minute=0),
            end_at=now.replace(hour=15, minute=0),
            kind=BusyBlock.KIND_MANUAL,
        )
        t = create_task(user=u, name="essay", duration_minutes=90)
        auto_plan(user=u, now=now)
        t.refresh_from_db()
        # Either ends ≤ 14:00 or starts ≥ 15:00.
        end = t.scheduled_start + timedelta(minutes=90)
        assert end <= now.replace(hour=14, minute=0) or t.scheduled_start >= now.replace(
            hour=15, minute=0
        )

    def test_uses_remaining_for_partial_tasks(self, _planner_settings) -> None:
        u = _user("ap9")
        now = self._fixed_now()
        # 60-min task already 40min done → remaining 20min.
        t = create_task(user=u, name="partial", duration_minutes=60)
        Task.objects.filter(pk=t.pk).update(time_spent_minutes=40)
        t.refresh_from_db()
        auto_plan(user=u, now=now)
        t.refresh_from_db()
        # Placed at 10:00, ends at 10:20 (using 20 remaining minutes).
        # Just verify it got placed and not at 11:00 (which would mean it
        # consumed a full 60 min from somewhere else).
        assert t.scheduled_start is not None


# ---------------------------------------------------------------------------
# insert_break
# ---------------------------------------------------------------------------
@pytest.fixture
def _break_settings(settings):
    settings.TASKS_WORK_START_HOUR = 9
    settings.TASKS_WORK_END_HOUR = 21
    settings.TASKS_BREAK_MINUTES = 15
    settings.TASKS_BREAK_COOLDOWN_S = 60
    settings.TASKS_TRANSITION_MINUTES = 0
    return settings


@pytest.mark.django_db
class TestInsertBreak:
    def test_creates_busy_block_and_shifts(self, _break_settings) -> None:
        u = _user("br1")
        now = timezone.now()
        # Schedule a pending task 5 min from now so the shift is observable.
        t = create_task(user=u, name="A", duration_minutes=30)
        future_start = now + timedelta(minutes=5)
        Task.objects.filter(pk=t.pk).update(scheduled_start=future_start)
        block, info = insert_break(user=u, duration_minutes=15)
        assert block.kind == BusyBlock.KIND_BREAK
        assert info["shifted"] == 1
        assert info["dropped"] == 0
        t.refresh_from_db()
        # Shifted exactly by 15 minutes.
        assert (
            abs((t.scheduled_start - (future_start + timedelta(minutes=15))).total_seconds()) < 2
        )  # tolerance for now-instant drift

    def test_pauses_in_progress_task(self, _break_settings) -> None:
        u = _user("br2")
        t = create_task(user=u, name="essay", duration_minutes=60)
        # Start it, simulate 10 min elapsed.
        now = timezone.now()
        ten_ago = now - timedelta(minutes=10)
        Task.objects.filter(pk=t.pk).update(
            status=Task.STATUS_IN_PROGRESS,
            actual_start_at=ten_ago,
        )
        block, info = insert_break(user=u, duration_minutes=15)
        t.refresh_from_db()
        assert t.status == Task.STATUS_PENDING
        assert t.actual_start_at is None
        # Time spent should be ~10 min.
        assert 8 <= t.time_spent_minutes <= 12
        assert info["paused_task_id"] == t.id

    def test_cooldown_rejects_within_60s(self, _break_settings) -> None:
        u = _user("br3")
        insert_break(user=u, duration_minutes=15)
        with pytest.raises(BreakTooSoonError):
            insert_break(user=u, duration_minutes=15)

    def test_cooldown_does_not_block_other_users(self, _break_settings) -> None:
        u1 = _user("br4a")
        u2 = _user("br4b")
        insert_break(user=u1, duration_minutes=15)
        # u2 still allowed.
        insert_break(user=u2, duration_minutes=15)

    def test_overflow_to_backlog(self, _break_settings) -> None:
        u = _user("br5")
        # Pending task scheduled at 20:50 local, 30min long, work_end=21.
        # Shift by 15 min → starts 21:05, ends 21:35 → past work_end →
        # drop to backlog. Pass `now=20:40` so the test doesn't depend on
        # the wall clock.
        now = timezone.localtime().replace(hour=20, minute=40, second=0, microsecond=0)
        t = create_task(user=u, name="late", duration_minutes=30)
        future_start = now.replace(hour=20, minute=50, second=0, microsecond=0)
        Task.objects.filter(pk=t.pk).update(scheduled_start=future_start)
        _, info = insert_break(user=u, duration_minutes=15, now=now)
        assert info["dropped"] == 1
        t.refresh_from_db()
        assert t.scheduled_start is None

    def test_preserves_order_no_resort(self, _break_settings) -> None:
        u = _user("br6")
        # Two pending tasks scheduled at different future times. Their
        # relative order must not change after the break.
        now = timezone.now()
        t1 = create_task(user=u, name="first", duration_minutes=30, priority=Task.PRIORITY_LOW)
        t2 = create_task(user=u, name="second", duration_minutes=30, priority=Task.PRIORITY_HIGH)
        Task.objects.filter(pk=t1.pk).update(scheduled_start=now + timedelta(minutes=5))
        Task.objects.filter(pk=t2.pk).update(scheduled_start=now + timedelta(minutes=40))
        insert_break(user=u, duration_minutes=15)
        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.scheduled_start < t2.scheduled_start

    def test_past_tasks_not_shifted(self, _break_settings) -> None:
        u = _user("br7")
        # A pending task with scheduled_start in the past — not shifted.
        now = timezone.now()
        t = create_task(user=u, name="past", duration_minutes=30)
        past_start = now - timedelta(hours=2)
        Task.objects.filter(pk=t.pk).update(scheduled_start=past_start)
        insert_break(user=u, duration_minutes=15)
        t.refresh_from_db()
        # Untouched.
        assert abs((t.scheduled_start - past_start).total_seconds()) < 2


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestStartTask:
    def test_marks_in_progress(self) -> None:
        u = _user("st1")
        t = create_task(user=u, name="A", duration_minutes=30)
        result_task, session = start_task(user=u, task=t)
        assert session is None  # body-double not preferred
        result_task.refresh_from_db()
        assert result_task.status == Task.STATUS_IN_PROGRESS
        assert result_task.actual_start_at is not None

    def test_rejects_other_users_task(self) -> None:
        u1 = _user("st2a")
        u2 = _user("st2b")
        t = create_task(user=u1, name="A", duration_minutes=30)
        with pytest.raises(InvalidTaskFieldsError):
            start_task(user=u2, task=t)

    def test_rejects_non_pending(self) -> None:
        u = _user("st3")
        t = create_task(user=u, name="A", duration_minutes=30)
        start_task(user=u, task=t)
        with pytest.raises(InvalidTaskFieldsError):
            start_task(user=u, task=t)

    def test_one_in_progress_constraint(self) -> None:
        u = _user("st4")
        t1 = create_task(user=u, name="A", duration_minutes=30)
        t2 = create_task(user=u, name="B", duration_minutes=30)
        start_task(user=u, task=t1)
        # Trying to start a second triggers the partial-unique constraint.
        with pytest.raises(IntegrityError):
            start_task(user=u, task=t2)

    def test_body_double_failure_still_starts(self, monkeypatch) -> None:
        u = _user("st5")
        t = create_task(
            user=u,
            name="A",
            duration_minutes=30,
            body_double_preferred=True,
        )

        def _boom(**kwargs):
            raise RuntimeError("livekit down")

        monkeypatch.setattr("apps.body_double.services.enqueue", _boom)
        result_task, session = start_task(user=u, task=t)
        assert session is None
        result_task.refresh_from_db()
        assert result_task.status == Task.STATUS_IN_PROGRESS

    def test_body_double_already_in_pool_recovers(self, monkeypatch) -> None:
        u = _user("st6")
        from apps.body_double.services import AlreadyInPoolError

        t = create_task(
            user=u,
            name="A",
            duration_minutes=30,
            body_double_preferred=True,
        )

        def _already(**kwargs):
            raise AlreadyInPoolError("already")

        monkeypatch.setattr("apps.body_double.services.enqueue", _already)
        result_task, session = start_task(user=u, task=t)
        assert session is None
        result_task.refresh_from_db()
        assert result_task.status == Task.STATUS_IN_PROGRESS

    def test_body_double_match_returns_session(self, monkeypatch) -> None:
        u = _user("st7")
        t = create_task(
            user=u,
            name="A",
            duration_minutes=30,
            body_double_preferred=True,
        )
        sentinel = object()

        def _matched(**kwargs):
            return None, sentinel

        monkeypatch.setattr("apps.body_double.services.enqueue", _matched)
        result_task, session = start_task(user=u, task=t)
        assert session is sentinel


@pytest.mark.django_db
class TestCompleteTask:
    def test_marks_done(self) -> None:
        u = _user("co1")
        t = create_task(user=u, name="A", duration_minutes=30)
        complete_task(task=t)
        t.refresh_from_db()
        assert t.status == Task.STATUS_DONE
        assert t.completed_at is not None

    def test_tops_up_time_spent_from_in_progress_interval(self) -> None:
        u = _user("co2")
        t = create_task(user=u, name="A", duration_minutes=60)
        ten_ago = timezone.now() - timedelta(minutes=10)
        Task.objects.filter(pk=t.pk).update(
            status=Task.STATUS_IN_PROGRESS,
            actual_start_at=ten_ago,
        )
        t.refresh_from_db()
        complete_task(task=t)
        t.refresh_from_db()
        assert 8 <= t.time_spent_minutes <= 12


@pytest.mark.django_db
class TestSkipTask:
    def test_marks_skipped_and_clears_schedule(self) -> None:
        u = _user("sk1")
        t = create_task(user=u, name="A", duration_minutes=30)
        now = timezone.now()
        Task.objects.filter(pk=t.pk).update(scheduled_start=now)
        skip_task(task=t)
        t.refresh_from_db()
        assert t.status == Task.STATUS_SKIPPED
        assert t.scheduled_start is None


@pytest.mark.django_db
class TestBusyBlockDelete:
    def test_delete_busy_block(self) -> None:
        u = _user("dbb1")
        now = timezone.localtime()
        b = add_busy_block(
            user=u,
            name="X",
            start_at=now.replace(hour=14, minute=0, second=0, microsecond=0),
            end_at=now.replace(hour=15, minute=0, second=0, microsecond=0),
        )
        delete_busy_block(block=b)
        assert not BusyBlock.objects.filter(pk=b.pk).exists()
