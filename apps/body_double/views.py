"""Body-double views — landing, find/cancel, waiting, room, end.

The flow:
  GET  /body-double/                       → landing CTA
  POST /body-double/find/                  → enqueue; redirect to room or waiting
  GET  /body-double/waiting/               → waiting page (WS-driven redirect)
  GET  /body-double/room/<int:session_id>/ → call page (issues LiveKit token)
  POST /body-double/leave/                 → cancel waiting ticket
  POST /body-double/sessions/<int>/end/    → mark session ended

Most views require a logged-in user; the auth middleware already redirects
anonymous visits to the nickname picker, so we use `@login_required` for
clarity but the middleware is the real enforcer.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET, require_POST

from .models import BodyDoubleSession, PoolTicket
from .services import (
    AlreadyInPoolError,
    NotInSessionError,
    cancel_waiting,
    end_session,
    enqueue,
    get_active_ticket,
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
    if ticket is not None and ticket.status == PoolTicket.STATUS_MATCHED and ticket.session_id:
        return redirect("body_double:room", session_id=ticket.session_id)
    if ticket is not None and ticket.status == PoolTicket.STATUS_WAITING:
        return redirect("body_double:waiting")

    # Local import — avoids loading the communities app at module-load
    # time and keeps the import graph stable.
    from apps.communities.services import user_communities

    return render(
        request,
        "body_double/index.html",
        {"user_communities": user_communities(request.user)},
    )


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
    if ticket.status == PoolTicket.STATUS_MATCHED and ticket.session_id:
        # Already matched (race: WS push arrived but user reloaded the
        # waiting URL anyway). Redirect to room.
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
        from django.http import Http404

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
    """Mark the session as ended. Either participant can end."""
    session = get_object_or_404(BodyDoubleSession, pk=session_id)
    try:
        end_session(session=session, user=request.user)
    except NotInSessionError:
        from django.http import Http404

        raise Http404("No such session.") from None
    return redirect("body_double:index")
