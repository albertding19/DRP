"""Body-double services — pool enqueue, scheduled bookings, session end.

This module orchestrates the matchmaking flows but never touches the
LiveKit SDK or the channel layer directly. It delegates:

  - live matching → `settings.BODY_DOUBLE_MATCHING_STRATEGY` (Protocol)
  - booking matching → `apps.body_double.matching.scheduled`
  - video provider → `settings.BODY_DOUBLE_VIDEO_PROVIDER` (Protocol)
  - WS broadcast → `apps.realtime.broadcast.broadcast_*`

so each pluggable extension point can be swapped via Django settings
without changes here.

Race control: all of `enqueue` runs inside `transaction.atomic` with
`select_for_update` in the matching strategy. Two simultaneous enqueues
on an empty pool serialise into one becoming the partner of the other.
A user who double-clicks "Find a body double" hits the partial-unique
constraint on `PoolTicket` and gets `AlreadyInPoolError`.

Bookings have no DB uniqueness to lean on (a user may hold several), so
`book` / `cancel_booking` / `activate_booking` serialise on
`select_for_update` over the affected rows instead — pairs are always
locked in pk order so concurrent Join + Cancel can't deadlock. There is
NO background scheduler: bookings expire lazily on read paths
(`expire_stale_bookings`), and the session room is created by whichever
participant joins first (`activate_booking`).
"""

from __future__ import annotations

import contextlib
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import DateTimeField, ExpressionWrapper, F
from django.utils import timezone
from django.utils.module_loading import import_string

from apps.realtime import broadcast

from .matching.base import MatchingStrategy
from .matching.scheduled import find_booking_match, overlap_window
from .models import BodyDoubleSession, PoolTicket, ScheduledBooking
from .video.base import VideoProvider


class AlreadyInPoolError(Exception):
    """Raised when a user tries to enqueue while already holding an
    active (waiting or matched) ticket."""


class NotInSessionError(Exception):
    """Raised when ending a session the requesting user isn't part of."""


class InvalidBookingTimeError(Exception):
    """Raised when a booking's start time is in the past or beyond the
    booking horizon."""


class OverlappingBookingError(Exception):
    """Raised when a new booking would overlap one of the user's own
    active bookings."""


class BookingNotJoinableError(Exception):
    """Raised when joining a booking outside its join window, or one
    that isn't matched yet."""


class BookingNotCancellableError(Exception):
    """Raised when cancelling a booking whose session already exists —
    end it from the room instead."""


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
    friends_only: bool = False,
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
            friends_only=friends_only,
            status=PoolTicket.STATUS_WAITING,
        )
    except IntegrityError as exc:
        raise AlreadyInPoolError("You already have an active body-double request.") from exc

    partner = _strategy().find_match(ticket)
    if partner is None:
        return ticket, None

    # A waiting ticket that still points at an ACTIVE session is a REFILL
    # ticket — its holder is alone in a room whose partner left. Join
    # their room instead of opening a new one; the new user's POST
    # response redirects them straight in, and the survivor just sees a
    # tile appear. (A stale pointer to an ended session falls through to
    # the normal fresh-room path below.)
    if partner.session_id is not None:
        existing = (
            BodyDoubleSession.objects.select_for_update()
            .filter(pk=partner.session_id, status=BodyDoubleSession.STATUS_ACTIVE)
            .first()
        )
        if existing is not None:
            _attach_refill(session=existing, refill_ticket=partner, joining_ticket=ticket)
            return ticket, existing

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

    # Retire the LEAVER's attachments (matched ticket, waiting refill
    # ticket, matched booking) so they can re-enqueue. COMPLETED is a
    # terminal status NOT in ACTIVE_STATUSES, so `get_active_ticket`
    # returns None and the landing CTA reappears.
    now = timezone.now()
    PoolTicket.objects.filter(
        session=session, user=user, status__in=PoolTicket.ACTIVE_STATUSES
    ).update(status=PoolTicket.STATUS_COMPLETED, updated_at=now)
    ScheduledBooking.objects.filter(
        session=session, user=user, status=ScheduledBooking.STATUS_MATCHED
    ).update(status=ScheduledBooking.STATUS_COMPLETED, updated_at=now)

    # If the partner is still attached, the session (and LiveKit room)
    # lives on — their client notices the departure and quietly calls
    # `request_refill` so a new body double can drop into the same room.
    partner_attached = (
        PoolTicket.objects.filter(session=session, status__in=PoolTicket.ACTIVE_STATUSES)
        .exclude(user=user)
        .exists()
        or ScheduledBooking.objects.filter(session=session, status=ScheduledBooking.STATUS_MATCHED)
        .exclude(user=user)
        .exists()
    )
    if partner_attached:
        return

    session.status = BodyDoubleSession.STATUS_ENDED
    session.ended_at = now
    session.save(update_fields=["status", "ended_at", "updated_at"])

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


# ---------------------------------------------------------------------------
# Refill — replace a departed partner without disturbing the survivor
# ---------------------------------------------------------------------------
def _attach_refill(
    *, session: BodyDoubleSession, refill_ticket: PoolTicket, joining_ticket: PoolTicket
) -> None:
    """Pair `joining_ticket`'s user into `session`, taking the slot the
    departed partner vacated. The refill holder keeps their slot, their
    connection, and their concentration — the newcomer just appears."""
    if session.user_a_id == refill_ticket.user_id:
        session.user_b = joining_ticket.user
    else:
        session.user_a = joining_ticket.user
    session.agreed_duration_minutes = min(
        refill_ticket.duration_minutes or 30, joining_ticket.duration_minutes or 30
    )
    session.save(update_fields=["user_a", "user_b", "agreed_duration_minutes", "updated_at"])

    PoolTicket.objects.filter(pk=refill_ticket.pk).update(
        status=PoolTicket.STATUS_MATCHED,
        matched_with=joining_ticket,
        updated_at=timezone.now(),
    )
    PoolTicket.objects.filter(pk=joining_ticket.pk).update(
        status=PoolTicket.STATUS_MATCHED,
        matched_with=refill_ticket,
        session=session,
        updated_at=timezone.now(),
    )


def find_hoppable_room(*, user) -> PoolTicket | None:  # type: ignore[no-untyped-def]
    """Another survivor's refill ticket `user` could join — i.e. a
    WAITING ticket anchored to someone else's ACTIVE session, chattiness-
    compatible with `user`'s current ticket. Oldest wait first."""
    from .matching.preferences import _chattiness_compatible

    mine = get_active_ticket(user=user)
    chattiness = mine.chattiness if mine else PoolTicket.CHATTINESS_FLEXIBLE
    qs = (
        PoolTicket.objects.filter(
            status=PoolTicket.STATUS_WAITING,
            session__isnull=False,
            session__status=BodyDoubleSession.STATUS_ACTIVE,
        )
        .exclude(user=user)
        .select_related("session")
    )
    return _chattiness_compatible(qs, chattiness).order_by("created_at").first()


@transaction.atomic
def hop_to_room(*, session: BodyDoubleSession, user) -> BodyDoubleSession | None:  # type: ignore[no-untyped-def]
    """Leave `session` and join another survivor's room instead.

    The counterpart to the auto-refill: two lonely survivors are never
    paired automatically (each is anchored to their own room), but either
    may CHOOSE to abandon their room and hop into the other's. Leaving
    reuses `end_session` semantics — the abandoned room ends if the
    hopper was the last one attached.

    Returns the target session, or None if no compatible room exists
    (the button shouldn't have been shown; harmless race).
    """
    if not session.includes(user):
        raise NotInSessionError("Only the session participants can hop.")

    candidate = find_hoppable_room(user=user)
    if candidate is None:
        return None
    # Re-lock the target under FOR UPDATE and re-verify it's still open.
    target_ticket = (
        PoolTicket.objects.select_for_update()
        .filter(pk=candidate.pk, status=PoolTicket.STATUS_WAITING)
        .first()
    )
    if target_ticket is None:
        return None
    target_session = (
        BodyDoubleSession.objects.select_for_update()
        .filter(pk=target_ticket.session_id, status=BodyDoubleSession.STATUS_ACTIVE)
        .first()
    )
    if target_session is None:
        return None

    # Carry my preferences over before leaving retires my ticket.
    mine = get_active_ticket(user=user)
    end_session(session=session, user=user)
    new_ticket = PoolTicket.objects.create(
        user=user,
        status=PoolTicket.STATUS_WAITING,
        duration_minutes=mine.duration_minutes if mine else 30,
        chattiness=mine.chattiness if mine else PoolTicket.CHATTINESS_FLEXIBLE,
        work_mode=mine.work_mode if mine else PoolTicket.WORK_MODE_ANY,
        community=mine.community if mine else None,
    )
    _attach_refill(session=target_session, refill_ticket=target_ticket, joining_ticket=new_ticket)
    # No broadcast: the target survivor is in the room, not on the
    # waiting page — the hopper simply appears as a new tile.
    return target_session


@transaction.atomic
def requeue_from_room(  # type: ignore[no-untyped-def]
    *, session: BodyDoubleSession, user
) -> tuple[PoolTicket, BodyDoubleSession | None]:
    """Leave `session` and rejoin the general pool with the same
    preferences — the always-available alternative to waiting alone for
    a refill (the hop button only exists when another half-empty room
    does). May match instantly, including into another survivor's room."""
    if not session.includes(user):
        raise NotInSessionError("Only the session participants can requeue.")
    mine = get_active_ticket(user=user)
    end_session(session=session, user=user)
    return enqueue(
        user=user,
        community=mine.community if mine else None,
        duration_minutes=mine.duration_minutes if mine else 30,
        chattiness=mine.chattiness if mine else PoolTicket.CHATTINESS_FLEXIBLE,
        work_mode=mine.work_mode if mine else PoolTicket.WORK_MODE_ANY,
    )


@transaction.atomic
def request_refill(  # type: ignore[no-untyped-def]
    *, session: BodyDoubleSession, user
) -> tuple[PoolTicket | None, bool]:
    """The survivor's client reports their partner has left; put the
    survivor back in the matching pool WITHOUT leaving the room.

    Their ticket flips MATCHED → WAITING but KEEPS its session FK — a
    waiting ticket pointing at an active session is the "refill" marker
    that `enqueue` recognises: the next compatible user to enqueue is
    routed into this room instead of a fresh one. Preferences carry over
    automatically since it's the same ticket.

    The departed partner's attachments are retired here (covers the
    closed-tab case where they never clicked End — requesting a refill
    formally evicts them; if they reload they're no longer a participant).

    Returns `(ticket, matched_now)`:
      (None,   False) — session is no longer active; client should leave.
      (ticket, True)  — someone waiting in the pool joined immediately.
      (ticket, False) — waiting; the next enqueue may join.
    """
    if not session.includes(user):
        raise NotInSessionError("Only the session participants can request a refill.")

    session = (
        BodyDoubleSession.objects.select_for_update()
        .filter(pk=session.pk, status=BodyDoubleSession.STATUS_ACTIVE)
        .first()
    )
    if session is None:
        return None, False

    now = timezone.now()
    tickets = list(
        PoolTicket.objects.select_for_update().filter(
            session=session, status__in=PoolTicket.ACTIVE_STATUSES
        )
    )
    mine = next((t for t in tickets if t.user_id == user.id), None)

    # Evict the departed partner's leftovers (tab-close case).
    PoolTicket.objects.filter(session=session, status__in=PoolTicket.ACTIVE_STATUSES).exclude(
        user=user
    ).update(status=PoolTicket.STATUS_COMPLETED, updated_at=now)
    ScheduledBooking.objects.filter(
        session=session, status=ScheduledBooking.STATUS_MATCHED
    ).exclude(user=user).update(status=ScheduledBooking.STATUS_COMPLETED, updated_at=now)

    if mine is None:
        # Booking-born session — the survivor has no live ticket. Mint a
        # refill ticket from their booking's preferences.
        booking = ScheduledBooking.objects.filter(
            session=session, user=user, status=ScheduledBooking.STATUS_MATCHED
        ).first()
        try:
            mine = PoolTicket.objects.create(
                user=user,
                session=session,
                status=PoolTicket.STATUS_WAITING,
                duration_minutes=booking.duration_minutes if booking else 30,
                chattiness=booking.chattiness if booking else PoolTicket.CHATTINESS_FLEXIBLE,
                work_mode=booking.work_mode if booking else PoolTicket.WORK_MODE_ANY,
            )
        except IntegrityError as exc:
            raise AlreadyInPoolError("You already have an active body-double request.") from exc
    elif mine.status == PoolTicket.STATUS_MATCHED:
        mine.status = PoolTicket.STATUS_WAITING
        mine.matched_with = None
        mine.save(update_fields=["status", "matched_with", "updated_at"])
    # else: already WAITING with session set — idempotent re-request.

    partner = _strategy().find_match(mine)
    # Never pair two refill tickets — each is anchored to its own room,
    # and neither survivor should be teleported into the other's.
    if partner is None or partner.session_id is not None:
        return mine, False

    _attach_refill(session=session, refill_ticket=mine, joining_ticket=partner)
    # The joiner is sitting on the WAITING page — push them the room URL.
    broadcast.broadcast_match_found(notify_user_id=partner.user_id, session=session)
    return mine, True


# ---------------------------------------------------------------------------
# Scheduled bookings
# ---------------------------------------------------------------------------
def _mark_pair_matched(
    booking: ScheduledBooking, partner: ScheduledBooking
) -> tuple[ScheduledBooking, ScheduledBooking]:
    """Transition `booking` + `partner` OPEN → MATCHED with cross-refs and
    the agreed overlap window on both rows. Returns the refreshed pair."""
    agreed_start, agreed_end = overlap_window(booking, partner)
    now = timezone.now()
    ScheduledBooking.objects.filter(pk=booking.pk).update(
        status=ScheduledBooking.STATUS_MATCHED,
        matched_with=partner,
        agreed_start_at=agreed_start,
        agreed_end_at=agreed_end,
        updated_at=now,
    )
    ScheduledBooking.objects.filter(pk=partner.pk).update(
        status=ScheduledBooking.STATUS_MATCHED,
        matched_with=booking,
        agreed_start_at=agreed_start,
        agreed_end_at=agreed_end,
        updated_at=now,
    )
    booking.refresh_from_db()
    partner.refresh_from_db()
    return booking, partner


@transaction.atomic
def book(  # type: ignore[no-untyped-def]
    *,
    user,
    start_at,
    duration_minutes: int = 30,
    chattiness: str = PoolTicket.CHATTINESS_FLEXIBLE,
    work_mode: str = PoolTicket.WORK_MODE_ANY,
    community=None,
) -> tuple[ScheduledBooking, ScheduledBooking | None]:
    """Create a scheduled booking and try to match it immediately.

    Returns `(booking, partner_booking)` — `partner_booking` is non-None
    if an overlapping compatible booking was waiting. Matching creates NO
    session yet; the room is created by whoever joins first inside the
    join window (`activate_booking`).

    Side effect on match: the partner user gets a `booking_matched` WS
    event. The booker learns from their own POST response.

    Raises:
      InvalidBookingTimeError — start in the past / beyond the horizon.
      OverlappingBookingError — clashes with the user's own active booking.
    """
    now = timezone.now()
    if start_at <= now:
        raise InvalidBookingTimeError("Pick a time in the future.")
    horizon = now + timedelta(days=settings.BODY_DOUBLE_BOOKING_HORIZON_DAYS)
    if start_at > horizon:
        raise InvalidBookingTimeError(
            f"Bookings open up to {settings.BODY_DOUBLE_BOOKING_HORIZON_DAYS} days ahead."
        )

    end_at = start_at + timedelta(minutes=duration_minutes)
    # Self-overlap guard. No DB exclusion constraint (needs btree_gist),
    # so lock the user's own active bookings and check in Python — the
    # same accepted select_for_update trade-off as the rest of the app.
    mine = ScheduledBooking.objects.select_for_update().filter(
        user=user,
        status__in=ScheduledBooking.ACTIVE_STATUSES,
        start_at__lt=end_at,
    )
    for other in mine:
        if other.end_at > start_at:
            raise OverlappingBookingError("You already have a booking overlapping that time.")

    booking = ScheduledBooking.objects.create(
        user=user,
        community=community,
        start_at=start_at,
        duration_minutes=duration_minutes,
        chattiness=chattiness,
        work_mode=work_mode,
        status=ScheduledBooking.STATUS_OPEN,
    )

    partner = find_booking_match(booking)
    if partner is None:
        return booking, None

    booking, partner = _mark_pair_matched(booking, partner)
    broadcast.broadcast_booking_matched(notify_user_id=partner.user_id, booking=partner)
    return booking, partner


@transaction.atomic
def cancel_booking(*, booking: ScheduledBooking) -> None:
    """Cancel `booking`. Idempotent on terminal states.

    If the booking was matched (but the session doesn't exist yet), the
    partner's booking is re-opened and immediately re-run through the
    matcher — they may instantly re-pair with another open booking. The
    partner gets a `booking_cancelled` WS event either way (and a
    `booking_matched` one on instant re-pair).

    Raises:
      BookingNotCancellableError — the session already exists; the room's
        End button is the way out.
    """
    # Lock the pair in pk order — the same order activate_booking uses,
    # so a concurrent Join can't deadlock with a Cancel.
    pair_ids = [booking.pk]
    if booking.matched_with_id is not None:
        pair_ids.append(booking.matched_with_id)
    rows = {
        row.pk: row
        for row in ScheduledBooking.objects.select_for_update().filter(pk__in=sorted(pair_ids))
    }
    mine = rows[booking.pk]

    if mine.status not in ScheduledBooking.ACTIVE_STATUSES:
        return  # idempotent
    if mine.session_id is not None:
        raise BookingNotCancellableError("The session has started — end it from the room.")

    now = timezone.now()
    mine.status = ScheduledBooking.STATUS_CANCELLED
    mine.save(update_fields=["status", "updated_at"])

    partner = rows.get(mine.matched_with_id) if mine.matched_with_id else None
    if partner is None or partner.status != ScheduledBooking.STATUS_MATCHED:
        return

    # Re-open the partner's booking: clear the pairing, keep their ask.
    partner.status = ScheduledBooking.STATUS_OPEN
    partner.matched_with = None
    partner.agreed_start_at = None
    partner.agreed_end_at = None
    partner.save(
        update_fields=["status", "matched_with", "agreed_start_at", "agreed_end_at", "updated_at"]
    )
    broadcast.broadcast_booking_cancelled(notify_user_id=partner.user_id, booking_id=partner.pk)

    # Give them another shot right now — another open booking may fit.
    # Skip if their own window can no longer hold the minimum overlap.
    min_overlap = timedelta(minutes=settings.BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN)
    if partner.end_at - min_overlap <= now:
        partner.status = ScheduledBooking.STATUS_EXPIRED
        partner.save(update_fields=["status", "updated_at"])
        return
    rematch = find_booking_match(partner)
    if rematch is not None:
        partner, rematch = _mark_pair_matched(partner, rematch)
        # Unlike `book`, nobody's POST response carries the news — both
        # users learn over WS (or the schedule page's poll).
        broadcast.broadcast_booking_matched(notify_user_id=partner.user_id, booking=partner)
        broadcast.broadcast_booking_matched(notify_user_id=rematch.user_id, booking=rematch)


@transaction.atomic
def activate_booking(*, booking: ScheduledBooking, user) -> BodyDoubleSession:  # type: ignore[no-untyped-def]
    """First Join inside the window creates the session + room; every
    later Join (including the partner's, and double-clicks) returns the
    same session. The booking analogue of `enqueue`'s match block.

    Side effect on first join: the PARTNER gets the existing
    `match_found` WS event — their dashboard/schedule page flips to
    "Rejoin your room" through the same handler live matches use.

    Raises:
      BookingNotJoinableError — not matched, or outside the join window.
    """
    pair_ids = [booking.pk]
    if booking.matched_with_id is not None:
        pair_ids.append(booking.matched_with_id)
    rows = {
        row.pk: row
        for row in ScheduledBooking.objects.select_for_update().filter(pk__in=sorted(pair_ids))
    }
    mine = rows[booking.pk]

    if mine.session_id is not None:
        return BodyDoubleSession.objects.get(pk=mine.session_id)
    if mine.status != ScheduledBooking.STATUS_MATCHED or mine.matched_with_id is None:
        raise BookingNotJoinableError("This booking doesn't have a partner yet.")

    now = timezone.now()
    join_opens = mine.agreed_start_at - timedelta(seconds=settings.BODY_DOUBLE_BOOKING_JOIN_EARLY_S)
    if now < join_opens:
        raise BookingNotJoinableError("The session hasn't opened yet — come back nearer the time.")
    if now >= mine.agreed_end_at:
        raise BookingNotJoinableError("This session's window has passed.")

    partner = rows[mine.matched_with_id]

    room_id = uuid4().hex
    _video_provider().create_room(room_id=room_id, max_participants=2)

    agreed_minutes = int((mine.agreed_end_at - mine.agreed_start_at).total_seconds() // 60)
    session = BodyDoubleSession.objects.create(
        room_id=room_id,
        user_a=partner.user,
        user_b=user,
        status=BodyDoubleSession.STATUS_ACTIVE,
        agreed_duration_minutes=agreed_minutes,
    )
    ScheduledBooking.objects.filter(pk__in=[mine.pk, partner.pk]).update(
        session=session, updated_at=now
    )

    broadcast.broadcast_match_found(notify_user_id=partner.user_id, session=session)
    return session


@transaction.atomic
def expire_stale_bookings(*, user) -> int:  # type: ignore[no-untyped-def]
    """Lazily retire `user`'s bookings whose moment has passed. Called at
    the top of booking read paths — there is no background job.

      open    + window can no longer fit the minimum overlap → expired
      matched + agreed window over, session never created     → BOTH expired

    Returns the number of rows expired.
    """
    now = timezone.now()
    min_overlap = timedelta(minutes=settings.BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN)

    requested_end = ExpressionWrapper(
        F("start_at") + timedelta(minutes=1) * F("duration_minutes"),
        output_field=DateTimeField(),
    )
    expired = (
        ScheduledBooking.objects.filter(user=user, status=ScheduledBooking.STATUS_OPEN)
        .annotate(requested_end=requested_end)
        .filter(requested_end__lte=now + min_overlap)
        .update(status=ScheduledBooking.STATUS_EXPIRED, updated_at=now)
    )

    no_shows = ScheduledBooking.objects.filter(
        user=user,
        status=ScheduledBooking.STATUS_MATCHED,
        session__isnull=True,
        agreed_end_at__lte=now,
    )
    for mine in no_shows:
        # Re-lock the pair in pk order and re-check, same discipline as
        # cancel/activate, since the partner row belongs to another user.
        pair_ids = sorted(pk for pk in [mine.pk, mine.matched_with_id] if pk is not None)
        rows = list(ScheduledBooking.objects.select_for_update().filter(pk__in=pair_ids))
        for row in rows:
            if (
                row.status == ScheduledBooking.STATUS_MATCHED
                and row.session_id is None
                and row.agreed_end_at is not None
                and row.agreed_end_at <= now
            ):
                row.status = ScheduledBooking.STATUS_EXPIRED
                row.save(update_fields=["status", "updated_at"])
                expired += 1
    return expired


def upcoming_bookings(*, user) -> list[ScheduledBooking]:  # type: ignore[no-untyped-def]
    """The user's active bookings, soonest first, after a lazy expiry
    sweep. `matched_with__user` is select_related for partner nicknames."""
    expire_stale_bookings(user=user)
    return list(
        ScheduledBooking.objects.filter(user=user, status__in=ScheduledBooking.ACTIVE_STATUSES)
        .select_related("matched_with__user", "community")
        .order_by("start_at")
    )


def booking_busy_intervals(*, user, window_start, window_end) -> list[tuple]:  # type: ignore[no-untyped-def]
    """Read-only seam for the tasks app: the user's active bookings as
    (start, end) tuples clipped-relevant to the window, so `auto_plan`
    can route tasks around booked sessions without materialised
    BusyBlocks to keep in sync."""
    from .availability import booking_intervals

    return [(iv.start, iv.end) for iv in booking_intervals(user, window_start, window_end)]
