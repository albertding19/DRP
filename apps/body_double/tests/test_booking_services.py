"""Tests for the scheduled-booking services — book, cancel (with
re-open + re-match), activate (lazy session creation), lazy expiry, and
the end_session extension.

Video provider + broadcast layer are mocked like `test_services.py`.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double import services
from apps.body_double.models import BodyDoubleSession, ScheduledBooking
from apps.body_double.services import (
    BookingNotCancellableError,
    BookingNotJoinableError,
    InvalidBookingTimeError,
    OverlappingBookingError,
    activate_booking,
    book,
    booking_busy_intervals,
    cancel_booking,
    end_session,
    expire_stale_bookings,
    upcoming_bookings,
)


@pytest.fixture(autouse=True)
def _mock_video_provider():
    fake = MagicMock()
    fake.issue_join_token.return_value = "fake.jwt.token"
    fake.create_room.return_value = MagicMock(room_id="fake-room", ws_url="wss://fake/")
    with patch.object(services, "_video_provider", return_value=fake):
        yield fake


@pytest.fixture(autouse=True)
def _mock_broadcast():
    with patch("apps.body_double.services.broadcast") as fake:
        yield fake


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


def _in(minutes: int):
    return timezone.now() + timedelta(minutes=minutes)


def _book(user: User, *, start_in_min: int = 60, base=None, **kwargs):
    # Pass a shared `base` when a test asserts exact agreed-window maths —
    # two raw timezone.now() calls differ by microseconds.
    start_at = (base or timezone.now()) + timedelta(minutes=start_in_min)
    return book(user=user, start_at=start_at, **kwargs)


@pytest.mark.django_db(transaction=True)
class TestBook:
    def test_first_booking_stays_open(self) -> None:
        booking, partner = _book(_user("sb_a"))
        assert booking.status == ScheduledBooking.STATUS_OPEN
        assert partner is None

    def test_overlapping_booking_matches_and_sets_agreed_window(self, _mock_broadcast) -> None:
        alice, bob = _user("sb_alice"), _user("sb_bob")
        first, _ = _book(alice, start_in_min=60, duration_minutes=60)
        second, partner = _book(bob, start_in_min=90, duration_minutes=60)

        assert partner is not None
        assert partner.pk == first.pk
        second.refresh_from_db()
        assert second.status == ScheduledBooking.STATUS_MATCHED
        assert partner.status == ScheduledBooking.STATUS_MATCHED
        assert second.matched_with_id == partner.pk
        assert partner.matched_with_id == second.pk
        # Agreed window = overlap: [90', 120') (bob's start → alice's end).
        assert second.agreed_start_at == partner.agreed_start_at == second.start_at
        assert second.agreed_end_at == partner.agreed_end_at == first.end_at
        # No session yet — the room is created on first join.
        assert second.session_id is None and partner.session_id is None
        # The waiting user (alice) got the WS event.
        _mock_broadcast.broadcast_booking_matched.assert_called_once()
        assert (
            _mock_broadcast.broadcast_booking_matched.call_args.kwargs["notify_user_id"] == alice.id
        )

    def test_past_start_rejected(self) -> None:
        with pytest.raises(InvalidBookingTimeError):
            book(user=_user("sb_past"), start_at=_in(-5))

    def test_beyond_horizon_rejected(self, settings) -> None:
        settings.BODY_DOUBLE_BOOKING_HORIZON_DAYS = 7
        with pytest.raises(InvalidBookingTimeError):
            book(user=_user("sb_far"), start_at=timezone.now() + timedelta(days=8))

    def test_own_overlapping_booking_rejected(self) -> None:
        u = _user("sb_dup")
        _book(u, start_in_min=60, duration_minutes=60)
        with pytest.raises(OverlappingBookingError):
            _book(u, start_in_min=90, duration_minutes=30)

    def test_own_adjacent_booking_allowed(self) -> None:
        u = _user("sb_adj")
        _book(u, start_in_min=60, duration_minutes=30)
        booking, _ = _book(u, start_in_min=90, duration_minutes=30)
        assert booking.status == ScheduledBooking.STATUS_OPEN

    def test_booking_allowed_while_in_live_pool(self) -> None:
        u = _user("sb_pool")
        services.enqueue(user=u)
        booking, _ = _book(u)
        assert booking.status == ScheduledBooking.STATUS_OPEN


@pytest.mark.django_db(transaction=True)
class TestCancelBooking:
    def test_cancel_open_booking(self) -> None:
        booking, _ = _book(_user("cb_open"))
        cancel_booking(booking=booking)
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_CANCELLED

    def test_cancel_is_idempotent(self) -> None:
        booking, _ = _book(_user("cb_idem"))
        cancel_booking(booking=booking)
        cancel_booking(booking=booking)  # no raise
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_CANCELLED

    def test_cancel_matched_reopens_partner(self, _mock_broadcast) -> None:
        alice, bob = _user("cb_alice"), _user("cb_bob")
        first, _ = _book(alice)
        second, _ = _book(bob)
        cancel_booking(booking=second)

        first.refresh_from_db()
        second.refresh_from_db()
        assert second.status == ScheduledBooking.STATUS_CANCELLED
        assert first.status == ScheduledBooking.STATUS_OPEN
        assert first.matched_with_id is None
        assert first.agreed_start_at is None
        _mock_broadcast.broadcast_booking_cancelled.assert_called_once()
        assert (
            _mock_broadcast.broadcast_booking_cancelled.call_args.kwargs["notify_user_id"]
            == alice.id
        )

    def test_cancel_matched_rematches_partner_instantly(self, _mock_broadcast) -> None:
        alice, bob, cara = _user("cb_a2"), _user("cb_b2"), _user("cb_c2")
        first, _ = _book(alice)
        second, _ = _book(bob)  # pairs with alice
        third, _ = _book(cara)  # same window, left open
        cancel_booking(booking=second)

        first.refresh_from_db()
        third.refresh_from_db()
        assert first.status == ScheduledBooking.STATUS_MATCHED
        assert first.matched_with_id == third.pk
        assert third.matched_with_id == first.pk
        # Both re-matched users got booking_matched (plus bob's original).
        notified = {
            c.kwargs["notify_user_id"]
            for c in _mock_broadcast.broadcast_booking_matched.call_args_list
        }
        assert {alice.id, cara.id} <= notified

    def test_cancel_after_session_started_rejected(self) -> None:
        alice, bob = _user("cb_a3"), _user("cb_b3")
        _book(alice, start_in_min=2)
        second, _ = _book(bob, start_in_min=2)
        activate_booking(booking=second, user=bob)
        second.refresh_from_db()
        with pytest.raises(BookingNotCancellableError):
            cancel_booking(booking=second)


@pytest.mark.django_db(transaction=True)
class TestActivateBooking:
    def _matched_pair(self, *, start_in_min: int = 2):
        base = timezone.now()
        alice, bob = _user(f"ab_a{start_in_min}"), _user(f"ab_b{start_in_min}")
        first, _ = _book(alice, start_in_min=start_in_min, base=base)
        second, _ = _book(bob, start_in_min=start_in_min, base=base)
        return alice, bob, first, second

    def test_first_join_creates_session_and_notifies_partner(self, _mock_broadcast) -> None:
        alice, bob, first, second = self._matched_pair()
        session = activate_booking(booking=second, user=bob)

        assert session.status == BodyDoubleSession.STATUS_ACTIVE
        assert {session.user_a_id, session.user_b_id} == {alice.id, bob.id}
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.session_id == session.pk == second.session_id
        # Status stays MATCHED until the session ends.
        assert first.status == ScheduledBooking.STATUS_MATCHED
        assert session.agreed_duration_minutes == 30
        _mock_broadcast.broadcast_match_found.assert_called_once()
        assert _mock_broadcast.broadcast_match_found.call_args.kwargs["notify_user_id"] == alice.id

    def test_second_join_returns_same_session(self, _mock_broadcast) -> None:
        alice, bob, first, second = self._matched_pair()
        session = activate_booking(booking=second, user=bob)
        first.refresh_from_db()
        again = activate_booking(booking=first, user=alice)
        assert again.pk == session.pk
        # Only the first join broadcasts.
        _mock_broadcast.broadcast_match_found.assert_called_once()

    def test_join_before_window_rejected(self, settings) -> None:
        settings.BODY_DOUBLE_BOOKING_JOIN_EARLY_S = 300
        _, bob, _, second = self._matched_pair(start_in_min=30)
        with pytest.raises(BookingNotJoinableError):
            activate_booking(booking=second, user=bob)

    def test_join_unmatched_rejected(self) -> None:
        u = _user("ab_solo")
        booking, _ = _book(u, start_in_min=2)
        with pytest.raises(BookingNotJoinableError):
            activate_booking(booking=booking, user=u)

    def test_end_session_completes_bookings_as_each_leaves(self) -> None:
        alice, bob, first, second = self._matched_pair()
        session = activate_booking(booking=second, user=bob)
        # End = leave: bob's booking retires, alice's stays attached and
        # the session survives for her (refill semantics).
        end_session(session=session, user=bob)
        first.refresh_from_db()
        second.refresh_from_db()
        session.refresh_from_db()
        assert second.status == ScheduledBooking.STATUS_COMPLETED
        assert first.status == ScheduledBooking.STATUS_MATCHED
        assert session.status == BodyDoubleSession.STATUS_ACTIVE
        # Last one out ends it.
        end_session(session=session, user=alice)
        first.refresh_from_db()
        session.refresh_from_db()
        assert first.status == ScheduledBooking.STATUS_COMPLETED
        assert session.status == BodyDoubleSession.STATUS_ENDED


@pytest.mark.django_db(transaction=True)
class TestExpiry:
    def test_open_booking_past_window_expires(self) -> None:
        u = _user("ex_open")
        booking, _ = _book(u, start_in_min=60, duration_minutes=30)
        # Shift the window into the past: only 10 of its minutes remain.
        ScheduledBooking.objects.filter(pk=booking.pk).update(start_at=_in(-20))
        assert expire_stale_bookings(user=u) == 1
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_EXPIRED

    def test_open_booking_with_enough_window_left_survives(self) -> None:
        u = _user("ex_keep")
        booking, _ = _book(u, start_in_min=60, duration_minutes=30)
        ScheduledBooking.objects.filter(pk=booking.pk).update(start_at=_in(-10))
        assert expire_stale_bookings(user=u) == 0
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_OPEN

    def test_matched_no_show_pair_expires_together(self) -> None:
        alice, bob = _user("ex_a"), _user("ex_b")
        first, _ = _book(alice, start_in_min=2)
        second, _ = _book(bob, start_in_min=2)
        ScheduledBooking.objects.filter(pk__in=[first.pk, second.pk]).update(
            agreed_start_at=_in(-60), agreed_end_at=_in(-30)
        )
        assert expire_stale_bookings(user=bob) == 2
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.status == ScheduledBooking.STATUS_EXPIRED
        assert second.status == ScheduledBooking.STATUS_EXPIRED

    def test_upcoming_bookings_sweeps_then_lists(self) -> None:
        u = _user("ex_list")
        stale, _ = _book(u, start_in_min=60, duration_minutes=30)
        ScheduledBooking.objects.filter(pk=stale.pk).update(start_at=_in(-20))
        live, _ = _book(u, start_in_min=120)
        listed = upcoming_bookings(user=u)
        assert [b.pk for b in listed] == [live.pk]


@pytest.mark.django_db(transaction=True)
class TestBookingBusyIntervals:
    def test_active_bookings_reported_as_intervals(self) -> None:
        u = _user("bi_a")
        booking, _ = _book(u, start_in_min=60, duration_minutes=30)
        intervals = booking_busy_intervals(user=u, window_start=timezone.now(), window_end=_in(240))
        assert intervals == [(booking.start_at, booking.end_at)]

    def test_matched_booking_uses_agreed_window(self) -> None:
        alice, bob = _user("bi_b"), _user("bi_c")
        _book(alice, start_in_min=60, duration_minutes=60)
        second, partner = _book(bob, start_in_min=90, duration_minutes=60)
        second.refresh_from_db()
        intervals = booking_busy_intervals(
            user=bob, window_start=timezone.now(), window_end=_in(240)
        )
        assert intervals == [(second.agreed_start_at, second.agreed_end_at)]

    def test_terminal_bookings_excluded(self) -> None:
        u = _user("bi_d")
        booking, _ = _book(u)
        cancel_booking(booking=booking)
        assert (
            booking_busy_intervals(user=u, window_start=timezone.now(), window_end=_in(240)) == []
        )
