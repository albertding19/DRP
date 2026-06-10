"""Project-wide views — ops endpoints + the personal-dashboard homepage.

Ops endpoints (`healthz`, `version`) intentionally don't touch the DB so
they stay green during outages.

`home` is the authenticated landing page at `/`. It composes four panels
from existing service helpers and renders them server-side. Each panel is
built behind `_safe()`, which swallows DB exceptions and returns None —
the template renders an empty-state per panel so a single broken query
can't 500 the whole page.
"""

from __future__ import annotations

import logging
import os

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe. Render's health-check pings this."""
    return JsonResponse({"status": "ok"})


def version(request: HttpRequest) -> JsonResponse:
    """Show the current commit SHA — proves CD pipeline updated."""
    commit = os.getenv("RENDER_GIT_COMMIT", "dev")
    return JsonResponse({"commit": commit[:7] if commit else "dev"})


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------
@login_required
@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Personal dashboard — first thing a logged-in user sees at `/`.

    Composes four panels from existing services. Each panel runs behind
    `_safe()`; if any one raises, that panel renders its empty state and
    the page still 200s.
    """
    user = request.user
    return render(
        request,
        "core/home.html",
        {
            "tasks_panel": _safe(_build_tasks_panel, user),
            "body_double_panel": _safe(_build_body_double_panel, user),
            "communities_panel": _safe(_build_communities_panel, user),
            "feed_panel": _safe(_build_feed_panel),
        },
    )


def _safe(fn, *args):
    """Run `fn(*args)`; on exception log + return None so the caller
    template can render an empty-state instead of 500-ing the page."""
    try:
        return fn(*args)
    except Exception:  # pragma: no cover — defensive log path
        logger.exception("dashboard panel %s failed", fn.__name__)
        return None


def _build_tasks_panel(user) -> dict:
    """Today's plan snapshot — uses the dedicated helper in apps.tasks."""
    from apps.tasks.services import dashboard_today_context

    return dashboard_today_context(user)


def _build_body_double_panel(user) -> dict:
    """Four-state CTA: idle / waiting / matched / upcoming.

    Priority matched > waiting > upcoming > idle — a live session always
    wins; a scheduled booking only surfaces when nothing's live. The
    pre-existing three states keep their exact markup contract."""
    from apps.body_double.models import PoolTicket, ScheduledBooking
    from apps.body_double.services import get_active_ticket, upcoming_bookings

    ticket = get_active_ticket(user=user)
    if ticket is not None and ticket.status == PoolTicket.STATUS_MATCHED and ticket.session_id:
        return {"state": "matched", "session_id": ticket.session_id}
    if ticket is not None:
        return {"state": "waiting", "ticket_id": ticket.id}

    bookings = upcoming_bookings(user=user)
    if bookings:
        nxt = bookings[0]
        # A booking whose partner already opened the room counts as
        # matched — same "Rejoin your room" button.
        if nxt.session_id is not None:
            return {"state": "matched", "session_id": nxt.session_id}
        return {
            "state": "upcoming",
            "booking_id": nxt.id,
            "start_at": nxt.agreed_start_at or nxt.start_at,
            "matched": nxt.status == ScheduledBooking.STATUS_MATCHED,
            "partner_nickname": nxt.matched_with.user.nickname if nxt.matched_with_id else None,
        }
    return {"state": "idle"}


def _build_communities_panel(user) -> dict:
    """Up to 5 communities the user has joined, most-recent first."""
    from apps.communities.services import user_communities

    return {"communities": list(user_communities(user)[:5])}


def _build_feed_panel() -> dict:
    """5 newest posts + 5 trending tags. Global; not user-scoped."""
    from apps.posts.services import feed_queryset
    from apps.tags.models import Tag

    return {
        "posts": list(feed_queryset(sort="new")[:5]),
        "tags": list(Tag.objects.order_by("-post_count")[:5]),
    }
