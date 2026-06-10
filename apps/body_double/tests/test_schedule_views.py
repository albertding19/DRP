"""Tests for the scheduled-booking views — schedule page, book form,
cancel/join actions, and the JSON status poll.

Video provider + broadcast patched like the other view/service tests.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.body_double import services
from apps.body_double.models import ScheduledBooking


def _authed_client(nickname: str) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=nickname)
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


@pytest.fixture(autouse=True)
def _mock_video_provider():
    fake = MagicMock()
    fake.issue_join_token.return_value = "fake.test.jwt"
    fake.create_room.return_value = MagicMock(room_id="r", ws_url="wss://x/")
    with (
        patch("apps.body_double.services._video_provider", return_value=fake),
        patch("apps.body_double.views.import_string", return_value=lambda: fake),
    ):
        yield fake


@pytest.fixture(autouse=True)
def _mock_broadcast():
    with patch("apps.body_double.services.broadcast") as fake:
        yield fake


def _form_payload(start_at, *, duration: int = 30, **extra) -> dict:
    local = timezone.localtime(start_at)
    payload = {
        "date": local.date().isoformat(),
        "time": local.strftime("%H:%M"),
        "duration_minutes": str(duration),
        "chattiness": "flexible",
        "work_mode": "any",
    }
    payload.update(extra)
    return payload


@pytest.mark.django_db(transaction=True)
class TestSchedulePage:
    def test_unauthed_redirected(self) -> None:
        assert Client().get("/body-double/schedule/").status_code == 302

    def test_renders_with_form(self) -> None:
        client, _ = _authed_client("sched_render")
        r = client.get("/body-double/schedule/")
        assert r.status_code == 200
        assert b"Book this slot" in r.content

    def test_lists_upcoming_bookings(self) -> None:
        client, user = _authed_client("sched_list")
        ScheduledBooking.objects.create(
            user=user,
            start_at=timezone.now() + timedelta(hours=2),
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        r = client.get("/body-double/schedule/")
        assert b"Looking for a partner" in r.content

    def test_expired_booking_shows_live_pool_cta(self) -> None:
        client, user = _authed_client("sched_expired")
        booking = ScheduledBooking.objects.create(
            user=user,
            start_at=timezone.now() + timedelta(hours=2),
            duration_minutes=30,
            status=ScheduledBooking.STATUS_OPEN,
        )
        # Pull the window into the past; the page's lazy sweep expires it.
        ScheduledBooking.objects.filter(pk=booking.pk).update(
            start_at=timezone.now() - timedelta(hours=1)
        )
        r = client.get("/body-double/schedule/")
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_EXPIRED
        assert b"Try the live pool now" in r.content


@pytest.mark.django_db(transaction=True)
class TestBookView:
    def test_creates_open_booking_and_redirects(self) -> None:
        client, user = _authed_client("book_ok")
        r = client.post(
            "/body-double/schedule/book/",
            _form_payload(timezone.now() + timedelta(hours=3)),
        )
        assert r.status_code == 302
        assert r.url == "/body-double/schedule/"
        booking = ScheduledBooking.objects.get(user=user)
        assert booking.status == ScheduledBooking.STATUS_OPEN
        assert booking.duration_minutes == 30

    def test_matches_against_overlapping_booking(self) -> None:
        client_a, alice = _authed_client("book_alice")
        client_b, bob = _authed_client("book_bob")
        start = timezone.now() + timedelta(hours=3)
        client_a.post("/body-double/schedule/book/", _form_payload(start))
        client_b.post("/body-double/schedule/book/", _form_payload(start))
        a = ScheduledBooking.objects.get(user=alice)
        b = ScheduledBooking.objects.get(user=bob)
        assert a.status == b.status == ScheduledBooking.STATUS_MATCHED
        assert a.matched_with_id == b.pk

    def test_missing_time_rerenders_with_error(self) -> None:
        client, user = _authed_client("book_notime")
        r = client.post(
            "/body-double/schedule/book/",
            _form_payload(timezone.now() + timedelta(hours=3), time=""),
        )
        assert r.status_code == 400
        assert b"Pick a date and time" in r.content
        assert not ScheduledBooking.objects.filter(user=user).exists()

    def test_past_time_rerenders_with_error(self) -> None:
        client, user = _authed_client("book_past")
        r = client.post(
            "/body-double/schedule/book/",
            _form_payload(timezone.now() - timedelta(hours=3)),
        )
        assert r.status_code == 400
        assert b"future" in r.content
        assert not ScheduledBooking.objects.filter(user=user).exists()

    def test_invalid_prefs_fall_back_to_defaults(self) -> None:
        client, user = _authed_client("book_fallback")
        client.post(
            "/body-double/schedule/book/",
            _form_payload(
                timezone.now() + timedelta(hours=3),
                duration_minutes="999",
                chattiness="screaming",
                work_mode="napping",
            ),
        )
        booking = ScheduledBooking.objects.get(user=user)
        assert booking.duration_minutes == 30
        assert booking.chattiness == "flexible"
        assert booking.work_mode == "any"


@pytest.mark.django_db(transaction=True)
class TestBookingActions:
    def _matched_pair(self, *, start_in_min: int = 2):
        client_a, alice = _authed_client(f"act_a{start_in_min}")
        client_b, bob = _authed_client(f"act_b{start_in_min}")
        base = timezone.now()
        a, _ = services.book(user=alice, start_at=base + timedelta(minutes=start_in_min))
        b, _ = services.book(user=bob, start_at=base + timedelta(minutes=start_in_min))
        a.refresh_from_db()
        return client_a, client_b, alice, bob, a, b

    def test_cancel_own_booking(self) -> None:
        client, user = _authed_client("act_cancel")
        booking, _ = services.book(user=user, start_at=timezone.now() + timedelta(hours=2))
        r = client.post(f"/body-double/bookings/{booking.pk}/cancel/")
        assert r.status_code == 302
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_CANCELLED

    def test_cannot_cancel_others_booking(self) -> None:
        client, _ = _authed_client("act_intruder")
        other = User.objects.create_anonymous(nickname="act_victim")
        booking, _ = services.book(user=other, start_at=timezone.now() + timedelta(hours=2))
        assert client.post(f"/body-double/bookings/{booking.pk}/cancel/").status_code == 404
        booking.refresh_from_db()
        assert booking.status == ScheduledBooking.STATUS_OPEN

    def test_join_inside_window_lands_in_room(self) -> None:
        _, client_b, _, bob, a, b = self._matched_pair()
        r = client_b.post(f"/body-double/bookings/{b.pk}/join/")
        assert r.status_code == 302
        b.refresh_from_db()
        assert b.session_id is not None
        assert r.url == f"/body-double/room/{b.session_id}/"

    def test_join_too_early_bounces_to_schedule(self) -> None:
        _, client_b, _, _, _, b = self._matched_pair(start_in_min=120)
        r = client_b.post(f"/body-double/bookings/{b.pk}/join/")
        assert r.status_code == 302
        assert r.url == "/body-double/schedule/"
        b.refresh_from_db()
        assert b.session_id is None

    def test_cannot_join_others_booking(self) -> None:
        _, _, _, _, a, _ = self._matched_pair()
        client, _ = _authed_client("act_snoop")
        assert client.post(f"/body-double/bookings/{a.pk}/join/").status_code == 404


@pytest.mark.django_db(transaction=True)
class TestScheduleStatus:
    def test_reports_bookings_with_join_state(self) -> None:
        client, user = _authed_client("st_a")
        partner = User.objects.create_anonymous(nickname="st_b")
        base = timezone.now()
        booking, _ = services.book(user=user, start_at=base + timedelta(minutes=2))
        services.book(user=partner, start_at=base + timedelta(minutes=2))
        r = client.get("/body-double/schedule/status/")
        assert r.status_code == 200
        data = r.json()["bookings"]
        assert len(data) == 1
        assert data[0]["id"] == booking.pk
        assert data[0]["status"] == ScheduledBooking.STATUS_MATCHED
        assert data[0]["joinable"] is True
        assert data[0]["partner"] == "st_b"

    def test_live_booking_carries_room_url(self) -> None:
        client, user = _authed_client("st_live")
        partner = User.objects.create_anonymous(nickname="st_partner")
        base = timezone.now()
        booking, _ = services.book(user=user, start_at=base + timedelta(minutes=2))
        other, _ = services.book(user=partner, start_at=base + timedelta(minutes=2))
        other.refresh_from_db()
        session = services.activate_booking(booking=other, user=partner)
        data = client.get("/body-double/schedule/status/").json()["bookings"]
        assert data[0]["live"] is True
        assert data[0]["room_url"] == f"/body-double/room/{session.pk}/"

    def test_empty_for_no_bookings(self) -> None:
        client, _ = _authed_client("st_empty")
        assert client.get("/body-double/schedule/status/").json() == {"bookings": []}
