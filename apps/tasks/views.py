"""Tasks views — HTMX-aware, all login-required.

Response shape (per the plan):
  - `add`, `plan`, `break`, `busy/add`, `busy/<id>/delete`: full
    `#timetable-region` swap + OOB partials for backlog + busy blocks.
  - `<id>/start`: per-row swap of `#task-{id}`; HX-Redirect header
    if body-double matched immediately.
  - `<id>/done`, `<id>/skip`: per-row swap.
  - `<id>/delete`: 204; client uses hx-swap="delete" on the row.
  - Validation errors: re-render the form partial with HX-Retarget +
    HX-Reswap headers so the form replaces itself rather than the
    timetable.
  - Non-HTMX clients get a 303 redirect to the index page.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from .models import BusyBlock, Task
from .services import (
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


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------
def _today_context(user) -> dict:
    """Common context for the index page + full-region partials."""
    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    scheduled = list(
        Task.objects.filter(
            user=user,
            scheduled_start__gte=day_start,
            scheduled_start__lt=day_end,
        )
        .exclude(status__in=[Task.STATUS_DONE, Task.STATUS_SKIPPED])
        .order_by("scheduled_start", "created_at")
    )
    in_progress = Task.objects.filter(user=user, status=Task.STATUS_IN_PROGRESS).first()
    if in_progress and in_progress not in scheduled:
        # Surface even if not on today's schedule (e.g. started solo).
        scheduled.insert(0, in_progress)
    backlog = list(
        Task.objects.filter(
            user=user,
            status=Task.STATUS_PENDING,
            scheduled_start__isnull=True,
        ).order_by("-created_at")
    )
    completed = list(
        Task.objects.filter(
            user=user,
            status__in=[Task.STATUS_DONE, Task.STATUS_SKIPPED],
            updated_at__gte=day_start,
        ).order_by("-completed_at", "-updated_at")[:20]
    )
    busy = list(
        BusyBlock.objects.filter(
            user=user,
            start_at__lt=day_end,
            end_at__gt=day_start,
        ).order_by("start_at")
    )
    # Today's body-double bookings render read-only alongside busy blocks
    # so the user can see why auto-plan left a gap. Failure-tolerant: the
    # tasks page must work even if the body-double layer misbehaves.
    try:
        from apps.body_double.services import upcoming_bookings

        body_double_bookings = [
            b
            for b in upcoming_bookings(user=user)
            if (b.agreed_start_at or b.start_at) < day_end
            and (b.agreed_end_at or b.end_at) > day_start
        ]
    except Exception:
        body_double_bookings = []
    return {
        "today": day_start,
        "scheduled": scheduled,
        "backlog": backlog,
        "completed": completed,
        "busy_blocks": busy,
        "body_double_bookings": body_double_bookings,
        "in_progress_task": in_progress,
        "work_start_hour": settings.TASKS_WORK_START_HOUR,
        "work_end_hour": settings.TASKS_WORK_END_HOUR,
        "default_break_minutes": settings.TASKS_BREAK_MINUTES,
        "priority_choices": Task.PRIORITY_CHOICES,
        "energy_choices": Task.ENERGY_CHOICES,
    }


def _render_full_region(request: HttpRequest, *, extra: dict | None = None) -> HttpResponse:
    """Return the timetable region + OOB swaps for backlog and busy blocks.
    Mirrors the `hx-swap-oob` pattern in `apps.comments`."""
    ctx = _today_context(request.user)
    if extra:
        ctx.update(extra)
    return render(request, "tasks/_full_region.html", ctx)


def _parse_optional_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _form_error_response(request: HttpRequest, template: str, ctx: dict, *, target: str):
    """Re-render a form partial with HX-Retarget / HX-Reswap headers so
    the form replaces itself rather than the timetable region."""
    response = render(request, template, ctx)
    response.status_code = 422
    response["HX-Retarget"] = target
    response["HX-Reswap"] = "outerHTML"
    return response


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------
@login_required
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    """Tasks landing page — timetable + backlog + busy blocks + forms."""
    ctx = _today_context(request.user)
    ctx["add_task_initial"] = {"name": "", "duration_minutes": "30"}
    ctx["add_task_errors"] = {}
    return render(request, "tasks/index.html", ctx)


@login_required
@require_GET
def region(request: HttpRequest) -> HttpResponse:
    """Bare `#full-region` partial for embedding the live timetable in
    other pages (the body-double room loads it via hx-get). The row
    actions inside already hx-post to their own endpoints and re-render
    this same region, so the embed is fully interactive."""
    return render(request, "tasks/_full_region.html", _today_context(request.user))


# ---------------------------------------------------------------------------
# Add / edit / delete task
# ---------------------------------------------------------------------------
@login_required
@require_POST
def add_task(request: HttpRequest) -> HttpResponse:
    name = (request.POST.get("name") or "").strip()
    duration_raw = (request.POST.get("duration_minutes") or "").strip()
    priority = (request.POST.get("priority") or Task.PRIORITY_MED).strip()
    energy = (request.POST.get("energy") or Task.ENERGY_MED).strip()
    deadline = _parse_optional_dt(request.POST.get("deadline"))
    body_double_preferred = request.POST.get("body_double_preferred") in {"on", "true", "1"}

    errors: dict[str, str] = {}
    duration_minutes = 0
    try:
        duration_minutes = int(duration_raw)
    except (TypeError, ValueError):
        errors["duration_minutes"] = "Give a whole number of minutes."

    if not errors:
        try:
            create_task(
                user=request.user,
                name=name,
                duration_minutes=duration_minutes,
                priority=priority,
                energy=energy,
                deadline=deadline,
                body_double_preferred=body_double_preferred,
            )
            # Auto-fold the new task into today's schedule. No "Plan my day"
            # button — every list change re-flows the day implicitly.
            auto_plan(user=request.user)
        except InvalidTaskFieldsError as exc:
            errors["form"] = str(exc)

    if errors:
        ctx = {
            "add_task_initial": {
                "name": name,
                "duration_minutes": duration_raw,
                "priority": priority,
                "energy": energy,
                "deadline": request.POST.get("deadline", ""),
                "body_double_preferred": body_double_preferred,
            },
            "add_task_errors": errors,
            "priority_choices": Task.PRIORITY_CHOICES,
            "energy_choices": Task.ENERGY_CHOICES,
        }
        if request.htmx:
            return _form_error_response(
                request, "tasks/_add_task_form.html", ctx, target="#add-task-form"
            )
        return redirect("tasks:index")

    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def edit_task(request: HttpRequest, task_id: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    fields = {}
    if "name" in request.POST:
        fields["name"] = request.POST["name"]
    if "duration_minutes" in request.POST:
        raw = request.POST.get("duration_minutes", "").strip()
        try:
            fields["duration_minutes"] = int(raw)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("duration_minutes must be an integer")
    if "priority" in request.POST:
        fields["priority"] = request.POST["priority"]
    if "energy" in request.POST:
        fields["energy"] = request.POST["energy"]
    if "deadline" in request.POST:
        fields["deadline"] = _parse_optional_dt(request.POST.get("deadline"))
    if "body_double_preferred" in request.POST:
        fields["body_double_preferred"] = request.POST.get("body_double_preferred") in {
            "on",
            "true",
            "1",
        }
    try:
        update_task(task=task, **fields)
    except InvalidTaskFieldsError as exc:
        return HttpResponseBadRequest(str(exc))
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def delete(request: HttpRequest, task_id: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    delete_task(task=task)
    # Auto-plan after delete so any leftover tasks can slide forward into
    # the freed slot; the response carries the freshly re-flowed schedule.
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


# ---------------------------------------------------------------------------
# Lifecycle: start / done / skip
# ---------------------------------------------------------------------------
@login_required
@require_POST
def start(request: HttpRequest, task_id: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    try:
        task, session = start_task(user=request.user, task=task)
    except InvalidTaskFieldsError as exc:
        return HttpResponseBadRequest(str(exc))
    if session is not None and request.htmx:
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("body_double:room", args=[session.id])
        return response
    if session is not None:
        return redirect("body_double:room", session_id=session.id)
    if request.htmx:
        # Full region — starting a task changes the in-progress banner and
        # row state; cheaper to re-render the whole region than juggle OOB.
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def done(request: HttpRequest, task_id: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    complete_task(task=task)
    # Finishing early frees up time — re-flow the rest of the day.
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def skip(request: HttpRequest, task_id: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    skip_task(task=task)
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


# ---------------------------------------------------------------------------
# Planning + break
# ---------------------------------------------------------------------------
@login_required
@require_POST
def plan(request: HttpRequest) -> HttpResponse:
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def take_break(request: HttpRequest) -> HttpResponse:
    raw = (request.POST.get("duration_minutes") or "").strip()
    duration = None
    if raw:
        try:
            duration = int(raw)
        except (TypeError, ValueError):
            duration = None
    try:
        insert_break(user=request.user, duration_minutes=duration)
    except BreakTooSoonError as exc:
        if request.htmx:
            return _render_full_region(request, extra={"break_error": str(exc)})
        return redirect("tasks:index")
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


# ---------------------------------------------------------------------------
# Busy blocks
# ---------------------------------------------------------------------------
@login_required
@require_POST
def add_busy(request: HttpRequest) -> HttpResponse:
    name = (request.POST.get("name") or "").strip()
    start_at = _parse_optional_dt(request.POST.get("start_at"))
    end_at = _parse_optional_dt(request.POST.get("end_at"))
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Give it a name."
    if start_at is None:
        errors["start_at"] = "Pick a start time."
    if end_at is None:
        errors["end_at"] = "Pick an end time."
    if not errors:
        try:
            add_busy_block(user=request.user, name=name, start_at=start_at, end_at=end_at)
            # New busy block can collide with planned tasks — re-flow now.
            auto_plan(user=request.user)
        except InvalidTaskFieldsError as exc:
            errors["form"] = str(exc)
    if errors:
        ctx = {
            "add_busy_initial": {
                "name": name,
                "start_at": request.POST.get("start_at", ""),
                "end_at": request.POST.get("end_at", ""),
            },
            "add_busy_errors": errors,
        }
        if request.htmx:
            return _form_error_response(
                request, "tasks/_add_busy_form.html", ctx, target="#add-busy-form"
            )
        return redirect("tasks:index")
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")


@login_required
@require_POST
def delete_busy(request: HttpRequest, block_id: int) -> HttpResponse:
    block = get_object_or_404(BusyBlock, pk=block_id, user=request.user)
    delete_busy_block(block=block)
    # Removing a booked slot opens up time — re-flow into the gap.
    auto_plan(user=request.user)
    if request.htmx:
        return _render_full_region(request)
    return redirect("tasks:index")
