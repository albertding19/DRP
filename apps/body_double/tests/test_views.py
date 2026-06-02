"""Tests for body-double views.

The LiveKit provider is patched out at the import-path level so the room
view doesn't need real credentials.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.body_double.models import BodyDoubleSession, PoolTicket


def _authed_client(nickname: str) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=nickname)
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


@pytest.fixture(autouse=True)
def _mock_video_provider():
    """The room view + services both resolve the video provider via
    `settings.BODY_DOUBLE_VIDEO_PROVIDER`. Patch both call sites — the
    services._video_provider helper, and the room view's local
    import_string call — so tests don't require real LiveKit credentials."""
    from unittest.mock import MagicMock

    fake = MagicMock()
    fake.issue_join_token.return_value = "fake.test.jwt"
    fake.create_room.return_value = MagicMock(room_id="r", ws_url="wss://x/")
    with (
        patch("apps.body_double.services._video_provider", return_value=fake),
        # The view module imported import_string at module load time, so
        # we patch its rebinding there (NOT the upstream django utility).
        patch("apps.body_double.views.import_string", return_value=lambda: fake),
    ):
        yield fake


@pytest.mark.django_db(transaction=True)
class TestIndexView:
    def test_unauthed_redirected(self) -> None:
        response = Client().get("/body-double/")
        assert response.status_code == 302

    def test_landing_renders_for_authed_no_ticket(self) -> None:
        client, _ = _authed_client("indexnoticket")
        response = client.get("/body-double/")
        assert response.status_code == 200
        assert b"Find a body double" in response.content

    def test_landing_redirects_to_waiting_when_waiting(self) -> None:
        client, user = _authed_client("indexwaiting")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        response = client.get("/body-double/")
        assert response.status_code == 302
        assert response.url == "/body-double/waiting/"

    def test_landing_redirects_to_room_when_matched(self) -> None:
        client, user = _authed_client("indexmatched")
        session = BodyDoubleSession.objects.create(room_id="abc", user_a=user, user_b=user)
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_MATCHED, session=session)
        response = client.get("/body-double/")
        assert response.status_code == 302
        assert response.url == f"/body-double/room/{session.id}/"


@pytest.mark.django_db(transaction=True)
class TestFindView:
    def test_unauthed_redirects_to_login(self) -> None:
        response = Client().post("/body-double/find/")
        assert response.status_code == 302

    def test_first_user_redirects_to_waiting(self) -> None:
        client, _ = _authed_client("findfirst")
        response = client.post("/body-double/find/")
        assert response.status_code == 302
        assert response.url == "/body-double/waiting/"
        assert PoolTicket.objects.count() == 1

    def test_second_user_redirects_to_room(self) -> None:
        # First user joins pool.
        _authed_client("findfirst_b")
        first_user = User.objects.get(nickname="findfirst_b")
        PoolTicket.objects.create(user=first_user, status=PoolTicket.STATUS_WAITING)

        client, _ = _authed_client("findsecond_b")
        response = client.post("/body-double/find/")
        assert response.status_code == 302
        assert response.url.startswith("/body-double/room/")
        session = BodyDoubleSession.objects.get()
        assert response.url == f"/body-double/room/{session.id}/"

    def test_double_find_redirects_to_index(self) -> None:
        """Already-in-pool collision is caught and bounces back."""
        client, _ = _authed_client("finddouble")
        client.post("/body-double/find/")
        response = client.post("/body-double/find/")
        assert response.status_code == 302
        assert response.url == "/body-double/"


@pytest.mark.django_db(transaction=True)
class TestWaitingView:
    def test_renders_when_waiting(self) -> None:
        client, user = _authed_client("waitingrender")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        response = client.get("/body-double/waiting/")
        assert response.status_code == 200
        assert b"Looking for a body double" in response.content

    def test_redirects_to_index_when_no_ticket(self) -> None:
        client, _ = _authed_client("waitingnone")
        response = client.get("/body-double/waiting/")
        assert response.status_code == 302
        assert response.url == "/body-double/"

    def test_redirects_to_room_when_matched(self) -> None:
        client, user = _authed_client("waitingmatched")
        session = BodyDoubleSession.objects.create(room_id="r", user_a=user, user_b=user)
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_MATCHED, session=session)
        response = client.get("/body-double/waiting/")
        assert response.status_code == 302
        assert response.url == f"/body-double/room/{session.id}/"


@pytest.mark.django_db(transaction=True)
class TestRoomView:
    def test_participant_can_view(self) -> None:
        client, user = _authed_client("roompart")
        session = BodyDoubleSession.objects.create(
            room_id="participant-room", user_a=user, user_b=user
        )
        response = client.get(f"/body-double/room/{session.id}/")
        assert response.status_code == 200
        # The fake token should be rendered into the page.
        assert b"fake.test.jwt" in response.content

    def test_non_participant_404(self) -> None:
        # Create a session between two other users.
        u_a = User.objects.create_anonymous(nickname="roomother_a")
        u_b = User.objects.create_anonymous(nickname="roomother_b")
        session = BodyDoubleSession.objects.create(room_id="r2", user_a=u_a, user_b=u_b)
        # Some random user tries to view.
        client, _ = _authed_client("roomstranger")
        response = client.get(f"/body-double/room/{session.id}/")
        assert response.status_code == 404

    def test_ended_session_redirects(self) -> None:
        client, user = _authed_client("roomended")
        session = BodyDoubleSession.objects.create(
            room_id="r3",
            user_a=user,
            user_b=user,
            status=BodyDoubleSession.STATUS_ENDED,
        )
        response = client.get(f"/body-double/room/{session.id}/")
        assert response.status_code == 302
        assert response.url == "/body-double/"

    def test_missing_session_404(self) -> None:
        client, _ = _authed_client("roommissing")
        response = client.get("/body-double/room/9999/")
        assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
class TestLeaveView:
    def test_cancels_waiting_and_redirects(self) -> None:
        client, user = _authed_client("leavewait")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        response = client.post("/body-double/leave/")
        assert response.status_code == 302
        ticket = PoolTicket.objects.get(user=user)
        assert ticket.status == PoolTicket.STATUS_CANCELLED

    def test_noop_when_not_waiting(self) -> None:
        client, _ = _authed_client("leavenoop")
        response = client.post("/body-double/leave/")
        assert response.status_code == 302  # still redirects to landing


@pytest.mark.django_db(transaction=True)
class TestStatusView:
    """JSON polling endpoint used by the waiting page as a WS fallback."""

    def test_no_ticket_returns_null_status(self) -> None:
        client, _ = _authed_client("statusnone")
        r = client.get("/body-double/status/")
        assert r.status_code == 200
        data = r.json()
        assert data == {"status": None, "matched": False, "room_url": None}

    def test_waiting_ticket_returns_waiting(self) -> None:
        client, user = _authed_client("statuswait")
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_WAITING)
        r = client.get("/body-double/status/")
        data = r.json()
        assert data["status"] == "waiting"
        assert data["matched"] is False
        assert data["room_url"] is None

    def test_matched_ticket_returns_room_url(self) -> None:
        client, user = _authed_client("statusmatched")
        session = BodyDoubleSession.objects.create(room_id="abc", user_a=user, user_b=user)
        PoolTicket.objects.create(user=user, status=PoolTicket.STATUS_MATCHED, session=session)
        r = client.get("/body-double/status/")
        data = r.json()
        assert data["status"] == "matched"
        assert data["matched"] is True
        assert data["room_url"] == f"/body-double/room/{session.id}/"

    def test_unauthed_redirected(self) -> None:
        r = Client().get("/body-double/status/")
        assert r.status_code == 302


@pytest.mark.django_db(transaction=True)
class TestEndView:
    def test_participant_can_end(self) -> None:
        client, user = _authed_client("endpart")
        session = BodyDoubleSession.objects.create(room_id="endr", user_a=user, user_b=user)
        response = client.post(f"/body-double/sessions/{session.id}/end/")
        assert response.status_code == 302
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ENDED

    def test_non_participant_404(self) -> None:
        u_a = User.objects.create_anonymous(nickname="endother_a")
        u_b = User.objects.create_anonymous(nickname="endother_b")
        session = BodyDoubleSession.objects.create(room_id="endr2", user_a=u_a, user_b=u_b)
        client, _ = _authed_client("endstranger")
        response = client.post(f"/body-double/sessions/{session.id}/end/")
        assert response.status_code == 404
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ACTIVE
