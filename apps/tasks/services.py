"""Tasks services — CRUD, auto-planning, break insertion, start hand-off.

All public functions are `@transaction.atomic`, take kwarg-only params,
and live behind named exceptions defined at the top of the module.

The scheduler (`apps.tasks.scheduler`) does the slot math as pure
functions. This module is the bridge between the DB and the scheduler:

  - `auto_plan`     builds slot + task inputs, calls scheduler.place_tasks,
                    writes back the resulting `scheduled_start` values.
  - `insert_break`  creates a `BusyBlock(kind=break)`, optionally pauses
                    the currently in-progress task, and shifts every
                    pending task with `scheduled_start >= now` later by
                    the break duration (preserving order — does NOT
                    re-sort).
  - `start_task`    flips `status = in_progress` and (if the task is
                    body-double preferred) hands off to
                    `apps.body_double.services.enqueue`. Body-double
                    failures are caught and the task still starts solo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BusyBlock, Task
from .scheduler import BusyInterval, Placement, TaskInput, free_slots, place_tasks

logger = logging.getLogger(__name__)


class InvalidTaskFieldsError(ValueError):
    """Raised when create_task / update_task / add_busy_block reject input."""


class BreakTooSoonError(Exception):
    """Raised by `insert_break` when the cooldown hasn't elapsed yet.

    Carries `seconds_remaining` so the view can render a friendly message.
    """

    def __init__(self, seconds_remaining: int):
        self.seconds_remaining = seconds_remaining
        super().__init__(f"Take a longer break — {seconds_remaining}s until you can break again.")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def _today_window(now: datetime | None = None) -> tuple[datetime, datetime, datetime]:
    """Returns (now_local, work_start_local, work_end_local) all in TIME_ZONE."""
    now = timezone.localtime(now) if now is not None else timezone.localtime()
    work_start = now.replace(hour=settings.TASKS_WORK_START_HOUR, minute=0, second=0, microsecond=0)
    work_end = now.replace(hour=settings.TASKS_WORK_END_HOUR, minute=0, second=0, microsecond=0)
    return now, work_start, work_end


def _today_local_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Start and end of the local calendar day containing `now`."""
    now = timezone.localtime(now) if now is not None else timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start, day_start + timedelta(days=1)


# ---------------------------------------------------------------------------
# Dashboard helper
# ---------------------------------------------------------------------------
def dashboard_today_context(user) -> dict:
    """Trimmed snapshot of today's plan for the homepage's tasks panel.

    Separate from `apps.tasks.views._today_context` because the dashboard
    needs only the top of the schedule + a couple of counters, not the
    full backlog / busy-blocks / completed lists. Lives in services (not
    views) so the homepage view can import without a circular dependency.

    Returns:
        {
            "in_progress_task": Task | None,
            "next_tasks":       list[Task],   # next 3 scheduled today
            "total_scheduled":  int,
            "backlog_count":    int,
            "default_break_minutes": int,
        }
    """
    day_start, day_end = _today_local_bounds()

    today_qs = (
        Task.objects.filter(user=user, scheduled_start__gte=day_start, scheduled_start__lt=day_end)
        .exclude(status__in=[Task.STATUS_DONE, Task.STATUS_SKIPPED])
        .order_by("scheduled_start")
    )

    in_progress = Task.objects.filter(user=user, status=Task.STATUS_IN_PROGRESS).first()
    backlog_count = Task.objects.filter(
        user=user, status=Task.STATUS_PENDING, scheduled_start__isnull=True
    ).count()

    return {
        "in_progress_task": in_progress,
        "next_tasks": list(today_qs[:3]),
        "total_scheduled": today_qs.count(),
        "backlog_count": backlog_count,
        "default_break_minutes": settings.TASKS_BREAK_MINUTES,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_choice(value: str, choices, field: str) -> str:
    valid = {c[0] for c in choices}
    if value not in valid:
        raise InvalidTaskFieldsError(f"{field}: must be one of {sorted(valid)}, got {value!r}")
    return value


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------
@transaction.atomic
def create_task(
    *,
    user,
    name: str,
    duration_minutes: int,
    priority: str = Task.PRIORITY_MED,
    energy: str = Task.ENERGY_MED,
    deadline: datetime | None = None,
    body_double_preferred: bool = False,
) -> Task:
    """Create a pending task in the backlog. Does NOT auto-schedule."""
    name = (name or "").strip()
    if not name:
        raise InvalidTaskFieldsError("name: required")
    if not isinstance(duration_minutes, int) or not (
        Task.DURATION_MIN <= duration_minutes <= Task.DURATION_MAX
    ):
        raise InvalidTaskFieldsError(
            f"duration_minutes: must be between {Task.DURATION_MIN} and {Task.DURATION_MAX}"
        )
    _validate_choice(priority, Task.PRIORITY_CHOICES, "priority")
    _validate_choice(energy, Task.ENERGY_CHOICES, "energy")

    return Task.objects.create(
        user=user,
        name=name,
        duration_minutes=duration_minutes,
        priority=priority,
        energy=energy,
        deadline=deadline,
        body_double_preferred=bool(body_double_preferred),
    )


@transaction.atomic
def update_task(*, task: Task, **fields) -> Task:
    """Partial update. Only `pending` / `in_progress` tasks are editable —
    completed / skipped are immutable for retro accuracy.
    """
    if task.status in {Task.STATUS_DONE, Task.STATUS_SKIPPED}:
        raise InvalidTaskFieldsError("task: cannot edit a completed or skipped task")

    allowed = {
        "name",
        "duration_minutes",
        "priority",
        "energy",
        "deadline",
        "body_double_preferred",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise InvalidTaskFieldsError(f"fields: cannot update {sorted(unknown)}")

    if "name" in fields:
        v = (fields["name"] or "").strip()
        if not v:
            raise InvalidTaskFieldsError("name: required")
        task.name = v
    if "duration_minutes" in fields:
        v = fields["duration_minutes"]
        if not isinstance(v, int) or not (Task.DURATION_MIN <= v <= Task.DURATION_MAX):
            raise InvalidTaskFieldsError(
                f"duration_minutes: must be between {Task.DURATION_MIN} and {Task.DURATION_MAX}"
            )
        task.duration_minutes = v
    if "priority" in fields:
        _validate_choice(fields["priority"], Task.PRIORITY_CHOICES, "priority")
        task.priority = fields["priority"]
    if "energy" in fields:
        _validate_choice(fields["energy"], Task.ENERGY_CHOICES, "energy")
        task.energy = fields["energy"]
    if "deadline" in fields:
        task.deadline = fields["deadline"]
    if "body_double_preferred" in fields:
        task.body_double_preferred = bool(fields["body_double_preferred"])
    task.save()
    return task


@transaction.atomic
def delete_task(*, task: Task) -> None:
    task.delete()


# ---------------------------------------------------------------------------
# BusyBlock CRUD
# ---------------------------------------------------------------------------
@transaction.atomic
def add_busy_block(*, user, name: str, start_at: datetime, end_at: datetime) -> BusyBlock:
    """Add a manual busy block. Must lie inside today's local calendar day
    and have positive duration."""
    name = (name or "").strip()
    if not name:
        raise InvalidTaskFieldsError("name: required")
    if end_at <= start_at:
        raise InvalidTaskFieldsError("end_at: must be after start_at")
    day_start, day_end = _today_local_bounds()
    s_local = timezone.localtime(start_at)
    e_local = timezone.localtime(end_at)
    if s_local < day_start or e_local > day_end:
        raise InvalidTaskFieldsError("busy block must lie within today")
    return BusyBlock.objects.create(
        user=user,
        name=name,
        start_at=start_at,
        end_at=end_at,
        kind=BusyBlock.KIND_MANUAL,
    )


@transaction.atomic
def delete_busy_block(*, block: BusyBlock) -> None:
    block.delete()


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
_PRIORITY_RANK = {Task.PRIORITY_HIGH: 0, Task.PRIORITY_MED: 1, Task.PRIORITY_LOW: 2}
_ENERGY_RANK = {Task.ENERGY_HIGH: 0, Task.ENERGY_MED: 1, Task.ENERGY_LOW: 2}


def _sort_for_planning(tasks: Iterable[Task]) -> list[Task]:
    """Sort tasks for greedy placement:
    1. Deadline asc (NULLs last)
    2. Priority high → low
    3. Energy high → low (high-energy earlier in the day)
    4. created_at asc (stable tiebreak)
    """
    return sorted(
        tasks,
        key=lambda t: (
            t.deadline is None,
            t.deadline or datetime.max,
            _PRIORITY_RANK.get(t.priority, 99),
            _ENERGY_RANK.get(t.energy, 99),
            t.created_at,
        ),
    )


@transaction.atomic
def auto_plan(*, user, now: datetime | None = None) -> dict:
    """Sort the user's pending tasks and place them into today's free slots.

    Sets `Task.scheduled_start` for placed tasks; clears it for leftovers
    (they fall back into the backlog).

    A task with status `in_progress` is treated as locked-in-place starting
    NOW for its remaining duration — added to the busy-interval set so
    the planner won't try to overlap it.

    Returns `{"placed": N, "leftover": M}`.
    """
    now_local, work_start, work_end = _today_window(now)
    day_start, day_end = _today_local_bounds(now_local)

    # Lock the user's tasks. select_for_update is a no-op on sqlite, which
    # matches our test environment — the cost of dropping race protection
    # there is acceptable.
    pending_qs = Task.objects.select_for_update().filter(user=user, status=Task.STATUS_PENDING)
    in_progress = (
        Task.objects.select_for_update().filter(user=user, status=Task.STATUS_IN_PROGRESS).first()
    )

    busy_qs = BusyBlock.objects.filter(user=user, start_at__lt=day_end, end_at__gt=day_start)
    busy: list[BusyInterval] = [BusyInterval(start=b.start_at, end=b.end_at) for b in busy_qs]
    # Treat in-progress task as a locked busy interval from now → now+remaining.
    if in_progress is not None and in_progress.remaining_minutes > 0:
        busy.append(
            BusyInterval(
                start=now_local,
                end=now_local + timedelta(minutes=in_progress.remaining_minutes),
            )
        )

    slots = free_slots(now=now_local, work_start=work_start, work_end=work_end, busy=busy)

    pending = list(pending_qs)
    ordered = _sort_for_planning(pending)
    inputs = [TaskInput(id=t.id, remaining_minutes=t.remaining_minutes) for t in ordered]

    placements, leftovers = place_tasks(
        ordered=inputs,
        slots=slots,
        transition_minutes=settings.TASKS_TRANSITION_MINUTES,
    )

    # Apply placements; clear scheduled_start on leftovers.
    placement_by_id: dict[int, Placement] = {p.task_id: p for p in placements}
    to_update: list[Task] = []
    for t in pending:
        p = placement_by_id.get(t.id)
        new_start = p.start if p is not None else None
        if t.scheduled_start != new_start:
            t.scheduled_start = new_start
            to_update.append(t)
    if to_update:
        Task.objects.bulk_update(to_update, ["scheduled_start"])

    return {"placed": len(placements), "leftover": len(leftovers)}


# ---------------------------------------------------------------------------
# Break insertion
# ---------------------------------------------------------------------------
@transaction.atomic
def insert_break(
    *,
    user,
    duration_minutes: int | None = None,
    now: datetime | None = None,
) -> tuple[BusyBlock, dict]:
    """Insert a break starting NOW and shift later tasks back.

    Semantics:
      - If a task is currently `in_progress`, it's paused: elapsed time is
        added to `time_spent_minutes`, `actual_start_at` cleared, status
        set back to `pending`, and `scheduled_start` set to NOW so it
        will be shifted into the post-break slot.
      - A `BusyBlock(kind=break)` is created from NOW to NOW + duration.
      - Every pending task with `scheduled_start >= now` is shifted later
        by the break duration, preserving order. Tasks that would end
        past `work_end` drop back to the backlog (`scheduled_start = NULL`).
      - Cooldown: rejects if the most recent break was created within
        `TASKS_BREAK_COOLDOWN_S` seconds, so a spammed click can't stack
        multiple breaks.
    """
    now, _, work_end = _today_window(now)
    duration = duration_minutes if duration_minutes is not None else settings.TASKS_BREAK_MINUTES
    if not isinstance(duration, int) or duration <= 0:
        raise InvalidTaskFieldsError("duration_minutes: must be a positive integer")

    cooldown_s = settings.TASKS_BREAK_COOLDOWN_S
    recent = (
        BusyBlock.objects.select_for_update()
        .filter(
            user=user,
            kind=BusyBlock.KIND_BREAK,
            created_at__gte=now - timedelta(seconds=cooldown_s),
        )
        .order_by("-created_at")
        .first()
    )
    if recent is not None:
        elapsed = (now - recent.created_at).total_seconds()
        raise BreakTooSoonError(seconds_remaining=max(1, int(cooldown_s - elapsed)))

    # Lock pending tasks for shift.
    pending = list(
        Task.objects.select_for_update()
        .filter(user=user, status=Task.STATUS_PENDING)
        .order_by("scheduled_start", "created_at")
    )
    in_progress = (
        Task.objects.select_for_update().filter(user=user, status=Task.STATUS_IN_PROGRESS).first()
    )

    paused_task_id = None
    if in_progress is not None:
        # Pause: increment elapsed (whole minutes), set back to pending,
        # schedule for the moment the break starts so the shift puts it
        # right after the break.
        elapsed_minutes = 0
        if in_progress.actual_start_at is not None:
            elapsed_minutes = max(
                0,
                int((now - in_progress.actual_start_at).total_seconds() // 60),
            )
        in_progress.time_spent_minutes = min(
            in_progress.duration_minutes,
            in_progress.time_spent_minutes + elapsed_minutes,
        )
        in_progress.actual_start_at = None
        in_progress.status = Task.STATUS_PENDING
        in_progress.scheduled_start = now
        in_progress.save(
            update_fields=[
                "time_spent_minutes",
                "actual_start_at",
                "status",
                "scheduled_start",
                "updated_at",
            ]
        )
        paused_task_id = in_progress.id
        # Include in the shift target so it lands after the break.
        pending.append(in_progress)
        pending.sort(key=lambda t: (t.scheduled_start or datetime.max, t.created_at))

    block = BusyBlock.objects.create(
        user=user,
        name="Break",
        start_at=now,
        end_at=now + timedelta(minutes=duration),
        kind=BusyBlock.KIND_BREAK,
    )

    shifted = 0
    dropped = 0
    to_update: list[Task] = []
    for t in pending:
        if t.scheduled_start is None or t.scheduled_start < now:
            continue
        new_start = t.scheduled_start + timedelta(minutes=duration)
        new_end = new_start + timedelta(minutes=t.remaining_minutes)
        if new_end > work_end:
            t.scheduled_start = None
            dropped += 1
        else:
            t.scheduled_start = new_start
        to_update.append(t)
        shifted += 1
    if to_update:
        Task.objects.bulk_update(to_update, ["scheduled_start"])

    return block, {"shifted": shifted, "dropped": dropped, "paused_task_id": paused_task_id}


# ---------------------------------------------------------------------------
# Lifecycle: start / complete / skip
# ---------------------------------------------------------------------------
def _enqueue_body_double(user):
    """Wrapper around `body_double.services.enqueue` that swallows errors —
    a task should always be startable even if the body-double layer is
    offline."""
    from apps.body_double.services import AlreadyInPoolError, enqueue

    try:
        _ticket, session = enqueue(user=user)
        return session
    except AlreadyInPoolError:
        # User is already in the pool from /body-double/ directly. Start
        # the task solo; they're already getting matched some other way.
        return None
    except Exception:  # pragma: no cover — defensive logging
        logger.exception("body-double enqueue failed during task start; degrading to solo")
        return None


@transaction.atomic
def start_task(*, user, task: Task):
    """Flip the task to in-progress. If body-double preferred, also enqueue.

    Returns `(task, session)`. `session` is non-None only when the
    body-double layer matched immediately — the view uses that to send
    the user straight to the call room.
    """
    if task.user_id != user.id:
        raise InvalidTaskFieldsError("task: not owned by this user")
    if task.status != Task.STATUS_PENDING:
        raise InvalidTaskFieldsError(f"task: only pending tasks can be started ({task.status})")

    task.status = Task.STATUS_IN_PROGRESS
    task.actual_start_at = timezone.now()
    task.save(update_fields=["status", "actual_start_at", "updated_at"])

    session = None
    if task.body_double_preferred:
        session = _enqueue_body_double(user)
    return task, session


@transaction.atomic
def complete_task(*, task: Task) -> Task:
    """Mark task done. If it was in-progress, top up time_spent_minutes with
    the active interval so retros see the true total."""
    now = timezone.now()
    if task.status == Task.STATUS_IN_PROGRESS and task.actual_start_at is not None:
        elapsed = max(0, int((now - task.actual_start_at).total_seconds() // 60))
        task.time_spent_minutes = min(
            task.duration_minutes,
            task.time_spent_minutes + elapsed,
        )
    task.status = Task.STATUS_DONE
    task.completed_at = now
    task.actual_start_at = None
    task.save(
        update_fields=[
            "status",
            "completed_at",
            "actual_start_at",
            "time_spent_minutes",
            "updated_at",
        ]
    )
    return task


@transaction.atomic
def skip_task(*, task: Task) -> Task:
    """Mark task skipped and drop it from the timetable."""
    task.status = Task.STATUS_SKIPPED
    task.scheduled_start = None
    task.actual_start_at = None
    task.save(update_fields=["status", "scheduled_start", "actual_start_at", "updated_at"])
    return task
