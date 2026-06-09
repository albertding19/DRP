"""Body-double services — pool enqueue, cancel, session end.

This module orchestrates the matchmaking flow but never touches the
LiveKit SDK or the channel layer directly. It delegates:

  - matching logic → `settings.BODY_DOUBLE_MATCHING_STRATEGY` (Protocol)
  - video provider → `settings.BODY_DOUBLE_VIDEO_PROVIDER` (Protocol)
  - WS broadcast → `apps.realtime.broadcast.broadcast_match_found`

so each pluggable extension point can be swapped via Django settings
without changes here.

Race control: all of `enqueue` runs inside `transaction.atomic` with
`select_for_update` in the matching strategy. Two simultaneous enqueues
on an empty pool serialise into one becoming the partner of the other.
A user who double-clicks "Find a body double" hits the partial-unique
constraint on `PoolTicket` and gets `AlreadyInPoolError`.
"""

from __future__ import annotations

import contextlib
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.realtime import broadcast

from .matching.base import MatchingStrategy
from .models import BodyDoubleSession, PoolTicket
from .video.base import VideoProvider


class AlreadyInPoolError(Exception):
    """Raised when a user tries to enqueue while already holding an
    active (waiting or matched) ticket."""


class NotInSessionError(Exception):
    """Raised when ending a session the requesting user isn't part of."""


def _strategy() -> MatchingStrategy:
    """Resolve the configured matching strategy. Instantiated fresh per
    call so tests can monkeypatch a different class via override_settings."""
    return import_string(settings.BODY_DOUBLE_MATCHING_STRATEGY)()


def _video_provider() -> VideoProvider:
    """Resolve the configured video provider. Instantiated fresh per call."""
    return import_string(settings.BODY_DOUBLE_VIDEO_PROVIDER)()


@transaction.atomic
def enqueue(  # type: ignore[no-untyped-def]
    *,
    user,
    community=None,
    duration_minutes: int = 30,
    chattiness: str = PoolTicket.CHATTINESS_FLEXIBLE,
    work_mode: str = PoolTicket.WORK_MODE_ANY,
) -> tuple[PoolTicket, BodyDoubleSession | None]:
    """Add `user` to the matchmaking pool with their stated preferences.

    Args:
      user — the requesting user.
      community — optional Community scope (matcher prefers same community).
      duration_minutes — 15/30/45/60/90; how long they expect to work.
      chattiness — "chatty" / "quiet" / "flexible". Hard rule in matcher:
        chatty × quiet never pair.
      work_mode — "deep_focus" / "busywork" / "admin" / "any". Soft pref.

    Returns `(ticket, session)` where `session` is non-None if a match
    happened immediately. The session's `agreed_duration_minutes` is
    populated with `min(my_duration, partner_duration)` so both leave
    when the shorter user is done.

    Side effects on immediate match:
      - both tickets transition WAITING → MATCHED
      - `BodyDoubleSession` row created with provider room_id
      - `broadcast_match_found` is sent to the OTHER user's matchmaking
        WS group, so their waiting page client redirects

    Raises:
      AlreadyInPoolError — user already has a waiting or matched ticket.
    """
    try:
        ticket = PoolTicket.objects.create(
            user=user,
            community=community,
            duration_minutes=duration_minutes,
            chattiness=chattiness,
            work_mode=work_mode,
            status=PoolTicket.STATUS_WAITING,
        )
    except IntegrityError as exc:
        raise AlreadyInPoolError("You already have an active body-double request.") from exc

    partner = _strategy().find_match(ticket)
    if partner is None:
        return ticket, None

    # Found a waiting partner — create the session, mark both matched.
    room_id = uuid4().hex
    _video_provider().create_room(room_id=room_id, max_participants=2)

    # Agreed duration = MIN of the two declared durations. Both leave when
    # the shorter user is done. Falls back to the requester's duration if
    # the partner row is missing it (legacy data).
    partner_duration = partner.duration_minutes or duration_minutes
    agreed = min(duration_minutes, partner_duration)

    session = BodyDoubleSession.objects.create(
        room_id=room_id,
        user_a=partner.user,  # whoever was waiting first
        user_b=user,
        status=BodyDoubleSession.STATUS_ACTIVE,
        agreed_duration_minutes=agreed,
    )

    # Both tickets transition to MATCHED with backrefs.
    PoolTicket.objects.filter(pk__in=[ticket.pk, partner.pk]).update(
        status=PoolTicket.STATUS_MATCHED,
        session=session,
    )
    # The cross-references (matched_with) need separate updates since each
    # row's value is different.
    ticket.matched_with_id = partner.pk
    ticket.status = PoolTicket.STATUS_MATCHED
    ticket.session = session
    ticket.save(update_fields=["matched_with", "status", "session", "updated_at"])

    PoolTicket.objects.filter(pk=partner.pk).update(matched_with=ticket)

    # Push the WS event to the OTHER user — they're the one sitting on
    # the waiting page. The current user is about to be redirected to the
    # room by the view, so they don't need a WS message.
    broadcast.broadcast_match_found(notify_user_id=partner.user_id, session=session)

    return ticket, session


@transaction.atomic
def cancel_waiting(*, user) -> int:  # type: ignore[no-untyped-def]
    """Cancel `user`'s waiting ticket (if any). Returns count cancelled (0 or 1).

    Matched tickets are not affected — once paired, the user must end
    the session via `end_session`, not cancel.
    """
    return PoolTicket.objects.filter(user=user, status=PoolTicket.STATUS_WAITING).update(
        status=PoolTicket.STATUS_CANCELLED, updated_at=timezone.now()
    )


@transaction.atomic
def end_session(*, session: BodyDoubleSession, user) -> None:  # type: ignore[no-untyped-def]
    """Mark `session` as ended. Idempotent on already-ended sessions.

    Auth: only one of the two participants may end the session.

    Side effect: both participants' tickets transition MATCHED → COMPLETED.
    Without this, a user who ends a session and then tries to enqueue
    again would still have a "matched" ticket lingering — the index view
    would redirect them at the (now-ended) room, the room view would
    redirect them back to index, and Safari shows "can't open this page"
    after the loop trips its redirect-count cap.
    """
    if not session.includes(user):
        raise NotInSessionError("Only the session participants can end the call.")

    if session.status == BodyDoubleSession.STATUS_ENDED:
        return  # idempotent

    session.status = BodyDoubleSession.STATUS_ENDED
    session.ended_at = timezone.now()
    session.save(update_fields=["status", "ended_at", "updated_at"])

    # Retire both tickets so the users can re-enqueue. COMPLETED is a
    # terminal status NOT in ACTIVE_STATUSES, so `get_active_ticket`
    # returns None and the landing CTA reappears.
    PoolTicket.objects.filter(session=session, status=PoolTicket.STATUS_MATCHED).update(
        status=PoolTicket.STATUS_COMPLETED, updated_at=timezone.now()
    )

    # Best-effort: ask the provider to tear down. LiveKit auto-cleans
    # empty rooms, so this is a no-op there; other providers may need it.
    # Provider failures must not block the user's UX — the session row is
    # already marked ended, which is what the views check.
    with contextlib.suppress(Exception):
        _video_provider().end_room(room_id=session.room_id)


def get_active_ticket(*, user) -> PoolTicket | None:  # type: ignore[no-untyped-def]
    """Return this user's currently-active (waiting or matched) ticket, if any."""
    return (
        PoolTicket.objects.filter(user=user, status__in=PoolTicket.ACTIVE_STATUSES)
        .order_by("-created_at")
        .first()
    )
