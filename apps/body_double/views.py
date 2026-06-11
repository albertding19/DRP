"""Body-double views — landing, find/cancel, waiting, room, end, and the
scheduled-booking pages.

The live flow:
  GET  /body-double/                       → landing CTA
  POST /body-double/find/                  → enqueue; redirect to room or waiting
  GET  /body-double/waiting/               → waiting page (WS-driven redirect)
  GET  /body-double/room/<int:session_id>/ → call page (issues LiveKit token)
  POST /body-double/leave/                 → cancel waiting ticket
  POST /body-double/sessions/<int>/end/    → mark session ended

The booking flow:
  GET  /body-double/schedule/                  → booking form + upcoming list
  POST /body-double/schedule/book/             → create booking (matches eagerly)
  GET  /body-double/schedule/status/           → JSON poll fallback
  POST /body-double/bookings/<int>/cancel/     → cancel a booking
  POST /body-double/bookings/<int>/join/       → first join creates the room

Most views require a logged-in user; the auth middleware already redirects
anonymous visits to the nickname picker, so we use `@login_required` for
clarity but the middleware is the real enforcer.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import BodyDoubleSession, PoolTicket, ScheduledBooking
from .services import (
    AlreadyInPoolError,
    BookingNotCancellableError,
    BookingNotJoinableError,
    InvalidBookingTimeError,
    NotInSessionError,
    OverlappingBookingError,
    activate_booking,
    book,
    cancel_booking,
    cancel_waiting,
    end_session,
    enqueue,
    find_hoppable_room,
    get_active_ticket,
    hop_to_room,
    request_refill,
    requeue_from_room,
    upcoming_bookings,
)


@login_required
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    """Landing page — explains body doubling + "Find a body double" CTA.

    If the user already has an active ticket, redirect them straight into
    the waiting page (waiting) or room (matched) rather than show the CTA.

    Otherwise, show:
      - Primary CTA: "Find me anyone" (general pool)
      - One CTA per community the user is a member of, scoping to that
        community.
    """
    ticket = get_active_ticket(user=request.user)
    if ticket is not None and ticket.session_id:
        # Matched — or WAITING with a session, which means a refill ticket:
        # the user is alone in a live room awaiting a new partner. Either
        # way their place is the room, not the waiting page.
        return redirect("body_double:room", session_id=ticket.session_id)
    if ticket is not None and ticket.status == PoolTicket.STATUS_WAITING:
        return redirect("body_double:waiting")

    # Local import — avoids loading the communities app at module-load
    # time and keeps the import graph stable.
    from apps.communities.services import user_communities

    selected_tasks = _selected_tasks(request.user, request.GET.getlist("tasks"))
    return render(
        request,
        "body_double/index.html",
        {
            "user_communities": user_communities(request.user),
            "selected_tasks": selected_tasks,
            "tasks_total_minutes": _tasks_duration(selected_tasks),
            "task_ids_csv": ",".join(str(t.pk) for t in selected_tasks),
        },
    )


# Cumulative task durations are clamped to the pool's plausible range:
# at least the smallest duration choice, at most 4 hours. The matcher
# handles arbitrary values (duration is a soft, phased preference).
_TASKS_DURATION_MIN = 15
_TASKS_DURATION_MAX = 240


def _selected_tasks(user, raw_ids) -> list:  # type: ignore[no-untyped-def]
    """Resolve task ids from the timetable's checkbox form to the user's
    OWN pending tasks — foreign or bogus ids silently drop out."""
    ids = [int(raw) for raw in raw_ids if str(raw).isdigit()]
    if not ids:
        return []
    from apps.tasks.models import Task  # lazy: keeps the import graph stable

    return list(Task.objects.filter(user=user, pk__in=ids, status=Task.STATUS_PENDING))


def _tasks_duration(tasks) -> int:  # type: ignore[no-untyped-def]
    """Session length for a set of tasks: cumulative remaining minutes,
    clamped to [15, 240]."""
    if not tasks:
        return 0
    total = sum(t.remaining_minutes for t in tasks)
    return max(_TASKS_DURATION_MIN, min(_TASKS_DURATION_MAX, total))


_VALID_DURATIONS = {15, 30, 45, 60, 90}
_VALID_CHATTINESS = {c[0] for c in PoolTicket.CHATTINESS_CHOICES}
_VALID_WORK_MODES = {c[0] for c in PoolTicket.WORK_MODE_CHOICES}


@login_required
@require_POST
def find(request: HttpRequest) -> HttpResponse:
    """Enqueue the requesting user with their per-session preferences.

    POST fields (all optional, defaults applied if missing or invalid):
      duration_minutes — one of 15/30/45/60/90 (default 30)
      chattiness       — chatty / quiet / flexible (default flexible)
      work_mode        — deep_focus / busywork / admin / any (default any)
      community        — slug of a Community (default no community pref)

    Three outcomes:
      - matched immediately → redirect to room
      - waiting in pool     → redirect to waiting
      - already enqueued    → redirect to landing (which re-routes)
    """
    # --- Coerce + validate the preference inputs.
    # Silent fallback to defaults on invalid input — a user with broken
    # JS or a tampered form shouldn't get a 400, they should just get
    # the most permissive defaults and a usable match.
    try:
        duration = int(request.POST.get("duration_minutes") or 30)
    except (TypeError, ValueError):
        duration = 30
    if duration not in _VALID_DURATIONS:
        duration = 30

    # Timetable-task flow: when the form carries selected task ids, the
    # session length is their cumulative remaining time — recomputed
    # server-side from the user's own tasks, never trusted from the form.
    task_ids = (request.POST.get("task_ids") or "").split(",")
    selected_tasks = _selected_tasks(request.user, task_ids)
    if selected_tasks:
        duration = _tasks_duration(selected_tasks)

    chattiness = (request.POST.get("chattiness") or "").strip()
    if chattiness not in _VALID_CHATTINESS:
        chattiness = PoolTicket.CHATTINESS_FLEXIBLE

    work_mode = (request.POST.get("work_mode") or "").strip()
    if work_mode not in _VALID_WORK_MODES:
        work_mode = PoolTicket.WORK_MODE_ANY

    community = None
    slug = (request.POST.get("community") or "").strip()
    if slug:
        # Local import avoids a circular import at module load time.
        from apps.communities.models import Community

        community = Community.objects.filter(slug=slug).first()

    try:
        _, session = enqueue(
            user=request.user,
            community=community,
            duration_minutes=duration,
            chattiness=chattiness,
            work_mode=work_mode,
        )
    except AlreadyInPoolError:
        # User already had an active ticket — route them to the right
        # page based on its current status.
        return redirect("body_double:index")

    if session is not None:
        return redirect("body_double:room", session_id=session.id)
    return redirect("body_double:waiting")


@login_required
@require_GET
def waiting(request: HttpRequest) -> HttpResponse:
    """Show the waiting page. Client opens a WS to be notified of match."""
    ticket = get_active_ticket(user=request.user)
    if ticket is None:
        # Nothing to wait on — bounce to landing.
        return redirect("body_double:index")
    if ticket.session_id:
        # Matched (race: WS push arrived but user reloaded the waiting
        # URL anyway) — or a refill ticket, whose holder belongs in
        # their still-live room. Redirect to room.
        return redirect("body_double:room", session_id=ticket.session_id)
    return render(
        request,
        "body_double/waiting.html",
        {"ticket": ticket, "wait_timeout_s": settings.BODY_DOUBLE_WAIT_TIMEOUT_S},
    )


@login_required
@require_GET
def status(request: HttpRequest) -> JsonResponse:
    """JSON polling endpoint for the waiting page.

    The waiting page WS is the fast path (sub-100ms after match), but the
    page also polls this every 5 seconds as a fallback in case the WS
    misses the event (e.g. broadcast fires while WS is still
    handshaking). The polling guarantees the user eventually sees the
    redirect even if the WS path fails entirely.

    Returns:
      {"status": "waiting", "matched": false, "room_url": null}
      {"status": "matched", "matched": true,  "room_url": "/body-double/room/N/"}
      {"status": null,      "matched": false, "room_url": null}  ← no active ticket
    """
    ticket = get_active_ticket(user=request.user)
    if ticket is None:
        return JsonResponse({"status": None, "matched": False, "room_url": None})
    if ticket.status == PoolTicket.STATUS_MATCHED and ticket.session_id:
        return JsonResponse(
            {
                "status": PoolTicket.STATUS_MATCHED,
                "matched": True,
                "room_url": reverse("body_double:room", kwargs={"session_id": ticket.session_id}),
            }
        )
    return JsonResponse({"status": ticket.status, "matched": False, "room_url": None})


@login_required
@require_GET
def room(request: HttpRequest, session_id: int) -> HttpResponse:
    """Render the call page with a freshly-minted video-provider token.

    Auth: 404 if `request.user` is not a participant — prevents URL
    enumeration from leaking other people's room IDs / tokens.
    """
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    if not session.includes(request.user):
        # Treat as 404 rather than 403 to avoid confirming the existence
        # of sessions the user isn't part of.
        raise Http404("No such session.")
    if session.status != BodyDoubleSession.STATUS_ACTIVE:
        # Session has already ended; route back to landing.
        return redirect("body_double:index")

    # Mint the join token via the configured provider.
    provider = import_string(settings.BODY_DOUBLE_VIDEO_PROVIDER)()
    token = provider.issue_join_token(room_id=session.room_id, user=request.user)

    return render(
        request,
        "body_double/room.html",
        {
            "session": session,
            "token": token,
            "ws_url": settings.LIVEKIT_URL,
            "room_id": session.room_id,
        },
    )


@login_required
@require_POST
def leave(request: HttpRequest) -> HttpResponse:
    """Cancel the user's waiting ticket. No-op if they had none."""
    cancel_waiting(user=request.user)
    return redirect("body_double:index")


@login_required
@require_POST
def end(request: HttpRequest, session_id: int) -> HttpResponse:
    """Leave the session (the last participant out ends it)."""
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    try:
        end_session(session=session, user=request.user)
    except NotInSessionError:
        raise Http404("No such session.") from None
    return redirect("body_double:index")


@login_required
@require_POST
def refill(request: HttpRequest, session_id: int) -> JsonResponse:
    """Called by the survivor's room page when their partner has left:
    re-enter the matching pool without leaving the room. JSON because
    the caller is a background fetch — the user must NOT be navigated."""
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    try:
        ticket, matched_now = request_refill(session=session, user=request.user)
    except NotInSessionError:
        raise Http404("No such session.") from None
    except AlreadyInPoolError:
        return JsonResponse({"status": "waiting"})
    if ticket is None:
        return JsonResponse({"status": "ended"})
    return JsonResponse({"status": "matched" if matched_now else "waiting"})


@login_required
@require_http_methods(["GET", "POST"])
def hop(request: HttpRequest, session_id: int) -> HttpResponse:
    """GET: is there another survivor's room to join? (polled quietly by
    the lonely room page to decide whether to show the button.)
    POST: leave this room and join it."""
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    if not session.includes(request.user):
        raise Http404("No such session.")
    if request.method == "GET":
        return JsonResponse({"available": find_hoppable_room(user=request.user) is not None})
    try:
        target = hop_to_room(session=session, user=request.user)
    except NotInSessionError:
        raise Http404("No such session.") from None
    if target is None:
        # Raced away — stay put; the room page carries on refilling.
        return redirect("body_double:room", session_id=session.id)
    return redirect("body_double:room", session_id=target.id)


@login_required
@require_POST
def requeue(request: HttpRequest, session_id: int) -> HttpResponse:
    """Leave the room and rejoin the general queue with the same prefs."""
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    if not session.includes(request.user):
        raise Http404("No such session.")
    try:
        _ticket, new_session = requeue_from_room(session=session, user=request.user)
    except NotInSessionError:
        raise Http404("No such session.") from None
    except AlreadyInPoolError:
        return redirect("body_double:index")
    if new_session is not None:
        return redirect("body_double:room", session_id=new_session.id)
    return redirect("body_double:waiting")


# ---------------------------------------------------------------------------
# Scheduled bookings
# ---------------------------------------------------------------------------
def _booking_states(bookings: list[ScheduledBooking]) -> list[dict]:
    """Annotate bookings with the display/join state the template and the
    status poll both need. One source of truth for "joinable"."""
    now = timezone.now()
    early = timedelta(seconds=settings.BODY_DOUBLE_BOOKING_JOIN_EARLY_S)
    rows = []
    for b in bookings:
        live = b.session_id is not None
        joinable = live or (
            b.status == ScheduledBooking.STATUS_MATCHED
            and b.agreed_start_at is not None
            and b.agreed_start_at - early <= now < b.agreed_end_at
        )
        rows.append(
            {
                "booking": b,
                "live": live,
                "joinable": joinable,
                "join_opens_at": (b.agreed_start_at - early) if b.agreed_start_at else None,
                "partner_nickname": (b.matched_with.user.nickname if b.matched_with_id else None),
            }
        )
    return rows


def _schedule_context(request: HttpRequest, *, book_error=None, book_initial=None) -> dict:
    """Context for the schedule page — also used to re-render it with a
    form error after a rejected POST."""
    from apps.communities.services import user_communities

    from .availability import availability_for

    bookings = upcoming_bookings(user=request.user)

    # Free-time hints for today, derived from the tasks timetable. Pure
    # suggestion — booking a clashing time is allowed.
    now_local = timezone.localtime()
    work_end = now_local.replace(
        hour=settings.TASKS_WORK_END_HOUR, minute=0, second=0, microsecond=0
    )
    free_today = []
    if now_local < work_end:
        min_overlap = settings.BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN
        free_today = [
            slot
            for slot in availability_for(request.user, window_start=now_local, window_end=work_end)
            if slot.length_minutes >= min_overlap
        ]

    # Bookings that just expired unmatched get a "try the live pool" CTA.
    recently_expired = list(
        ScheduledBooking.objects.filter(
            user=request.user,
            status=ScheduledBooking.STATUS_EXPIRED,
            updated_at__gte=timezone.now() - timedelta(minutes=30),
        ).order_by("-updated_at")[:3]
    )

    return {
        "booking_rows": _booking_states(bookings),
        "free_today": free_today,
        "recently_expired": recently_expired,
        "user_communities": user_communities(request.user),
        "book_error": book_error,
        "book_initial": book_initial
        or {"date": now_local.date().isoformat(), "time": "", "duration_minutes": 30},
        "join_early_min": settings.BODY_DOUBLE_BOOKING_JOIN_EARLY_S // 60,
    }


@login_required
@require_GET
def schedule(request: HttpRequest) -> HttpResponse:
    """Booking form + the user's upcoming scheduled sessions."""
    return render(request, "body_double/schedule.html", _schedule_context(request))


@login_required
@require_POST
def book_view(request: HttpRequest) -> HttpResponse:
    """Create a scheduled booking from the form.

    Preference fields fall back silently like `find` — but the START TIME
    is the point of this feature, so an unparseable or invalid time
    re-renders the form with an error instead of guessing.
    """
    try:
        duration = int(request.POST.get("duration_minutes") or 30)
    except (TypeError, ValueError):
        duration = 30
    if duration not in _VALID_DURATIONS:
        duration = 30

    chattiness = (request.POST.get("chattiness") or "").strip()
    if chattiness not in _VALID_CHATTINESS:
        chattiness = PoolTicket.CHATTINESS_FLEXIBLE

    work_mode = (request.POST.get("work_mode") or "").strip()
    if work_mode not in _VALID_WORK_MODES:
        work_mode = PoolTicket.WORK_MODE_ANY

    community = None
    slug = (request.POST.get("community") or "").strip()
    if slug:
        from apps.communities.models import Community

        community = Community.objects.filter(slug=slug).first()

    date_str = (request.POST.get("date") or "").strip()
    time_str = (request.POST.get("time") or "").strip()
    initial = {"date": date_str, "time": time_str, "duration_minutes": duration}

    def _form_error(message: str) -> HttpResponse:
        return render(
            request,
            "body_double/schedule.html",
            _schedule_context(request, book_error=message, book_initial=initial),
            status=400,
        )

    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return _form_error("Pick a date and time for your session.")
    start_at = timezone.make_aware(naive)

    try:
        _booking, partner = book(
            user=request.user,
            start_at=start_at,
            duration_minutes=duration,
            chattiness=chattiness,
            work_mode=work_mode,
            community=community,
        )
    except (InvalidBookingTimeError, OverlappingBookingError) as exc:
        return _form_error(str(exc))

    return redirect("body_double:schedule")


@login_required
@require_POST
def booking_cancel(request: HttpRequest, booking_id: int) -> HttpResponse:
    """Cancel one of the user's bookings. 404 for other users' bookings."""
    booking = get_object_or_404(ScheduledBooking, pk=booking_id, user=request.user)
    # Session already live → not cancellable; the schedule page shows Join.
    with contextlib.suppress(BookingNotCancellableError):
        cancel_booking(booking=booking)
    return redirect("body_double:schedule")


@login_required
@require_POST
def booking_join(request: HttpRequest, booking_id: int) -> HttpResponse:
    """Join a matched booking inside its window. First join creates the
    room; both joins land in it."""
    booking = get_object_or_404(ScheduledBooking, pk=booking_id, user=request.user)
    try:
        session = activate_booking(booking=booking, user=request.user)
    except BookingNotJoinableError:
        return redirect("body_double:schedule")
    return redirect("body_double:room", session_id=session.id)


@login_required
@require_GET
def schedule_status(request: HttpRequest) -> JsonResponse:
    """JSON polling fallback for the schedule page — same belt-and-braces
    role as `status` plays for the waiting page. The client compares the
    fingerprint and reloads when anything changes."""
    rows = _booking_states(upcoming_bookings(user=request.user))
    payload = [
        {
            "id": r["booking"].pk,
            "status": r["booking"].status,
            "joinable": r["joinable"],
            "live": r["live"],
            "room_url": (
                reverse("body_double:room", kwargs={"session_id": r["booking"].session_id})
                if r["live"]
                else None
            ),
            "partner": r["partner_nickname"],
        }
        for r in rows
    ]
    return JsonResponse({"bookings": payload})
