"""Tests for partner refill — when a body double leaves, the survivor
keeps the room and the pool quietly routes a new partner into it.

Video provider + broadcast are mocked like `test_services.py`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import User
from apps.body_double import services
from apps.body_double.models import BodyDoubleSession, PoolTicket
from apps.body_double.services import end_session, enqueue, request_refill


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


def _survivor_setup(tag: str):
    """Alice + Bob matched; Bob leaves; Alice requests a refill.
    Returns (alice, session, alice's refill ticket)."""
    alice, bob = _user(f"rf_a_{tag}"), _user(f"rf_b_{tag}")
    enqueue(user=alice)
    _, session = enqueue(user=bob)
    end_session(session=session, user=bob)
    ticket, matched_now = request_refill(session=session, user=alice)
    assert matched_now is False
    return alice, session, ticket


@pytest.mark.django_db(transaction=True)
class TestRequestRefill:
    def test_flips_survivor_ticket_to_waiting_with_session(self) -> None:
        alice, session, ticket = _survivor_setup("flip")
        assert ticket.user_id == alice.id
        assert ticket.status == PoolTicket.STATUS_WAITING
        assert ticket.session_id == session.id
        assert ticket.matched_with_id is None
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ACTIVE

    def test_evicts_closed_tab_partner(self) -> None:
        # Bob never clicks End (closed tab) — refill must retire his
        # MATCHED ticket so he isn't stuck attached to the session.
        alice, bob = _user("rf_a_tab"), _user("rf_b_tab")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        request_refill(session=session, user=alice)
        assert PoolTicket.objects.get(user=bob).status == PoolTicket.STATUS_COMPLETED

    def test_idempotent_re_request(self) -> None:
        _alice, session, ticket = _survivor_setup("idem")
        again, matched_now = request_refill(session=session, user=ticket.user)
        assert again.pk == ticket.pk
        assert matched_now is False
        assert PoolTicket.objects.filter(user=ticket.user).count() == 1

    def test_ended_session_returns_none(self) -> None:
        alice, bob = _user("rf_a_end"), _user("rf_b_end")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        end_session(session=session, user=bob)
        end_session(session=session, user=alice)
        ticket, matched_now = request_refill(session=session, user=alice)
        assert ticket is None and matched_now is False

    def test_refill_finds_already_waiting_user(self, _mock_broadcast) -> None:
        # Cara is already waiting in the pool when the refill is requested.
        alice, bob, cara = _user("rf_a_w"), _user("rf_b_w"), _user("rf_c_w")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        end_session(session=session, user=bob)
        enqueue(user=cara)  # waits (alice still MATCHED at this point)
        ticket, matched_now = request_refill(session=session, user=alice)
        assert matched_now is True
        session.refresh_from_db()
        assert {session.user_a_id, session.user_b_id} == {alice.id, cara.id}
        cara_ticket = PoolTicket.objects.get(user=cara)
        assert cara_ticket.status == PoolTicket.STATUS_MATCHED
        assert cara_ticket.session_id == session.id
        # Cara is on the waiting page — she gets the room push.
        assert _mock_broadcast.broadcast_match_found.call_args.kwargs["notify_user_id"] == cara.id


@pytest.mark.django_db(transaction=True)
class TestEnqueueJoinsRefill:
    def test_new_enqueuer_joins_existing_room(self, _mock_video_provider) -> None:
        alice, session, _ticket = _survivor_setup("join")
        _mock_video_provider.create_room.reset_mock()
        cara = _user("rf_c_join")
        cara_ticket, joined_session = enqueue(user=cara)

        # Same session, same room — no new room created.
        assert joined_session.pk == session.pk
        _mock_video_provider.create_room.assert_not_called()
        assert BodyDoubleSession.objects.count() == 1
        joined_session.refresh_from_db()
        assert {joined_session.user_a_id, joined_session.user_b_id} == {alice.id, cara.id}
        # Both tickets matched and cross-referenced.
        alice_ticket = PoolTicket.objects.get(user=alice)
        cara_ticket.refresh_from_db()
        assert alice_ticket.status == PoolTicket.STATUS_MATCHED
        assert cara_ticket.status == PoolTicket.STATUS_MATCHED
        assert alice_ticket.matched_with_id == cara_ticket.pk
        assert cara_ticket.matched_with_id == alice_ticket.pk
        assert cara_ticket.session_id == session.pk

    def test_two_refill_tickets_never_pair(self) -> None:
        # Two survivors, each anchored to their own room, must not be
        # teleported into each other's. Both sessions are formed BEFORE
        # any refill so the setups can't cross-match.
        alice, bob = _user("rf_a_p1"), _user("rf_b_p1")
        enqueue(user=alice)
        _, session_a = enqueue(user=bob)
        carol, dave = _user("rf_c_p2"), _user("rf_d_p2")
        enqueue(user=carol)
        _, session_b = enqueue(user=dave)
        end_session(session=session_a, user=bob)
        end_session(session=session_b, user=dave)

        # Alice becomes refill-waiting first; Carol's refill then sees
        # Alice's ticket as the only waiting candidate — and must skip it.
        ticket_a, _ = request_refill(session=session_a, user=alice)
        ticket_b, matched_now = request_refill(session=session_b, user=carol)
        assert matched_now is False
        ticket_a.refresh_from_db()
        assert ticket_a.status == PoolTicket.STATUS_WAITING
        assert ticket_a.matched_with_id is None
        assert ticket_b.matched_with_id is None

    def test_survivor_reload_routes_to_room_not_waiting(self) -> None:
        # The index view must send a refill-waiting user back to their
        # room, not the waiting page.
        from django.test import Client

        alice, session, _ticket = _survivor_setup("route")
        client = Client()
        s = client.session
        s["user_id"] = alice.id
        s.save()
        r = client.get("/body-double/")
        assert r.status_code == 302
        assert r.url == f"/body-double/room/{session.id}/"


@pytest.mark.django_db(transaction=True)
class TestRefillView:
    def _client_for(self, user):
        from django.test import Client

        client = Client()
        s = client.session
        s["user_id"] = user.id
        s.save()
        return client

    def test_refill_endpoint_waits(self) -> None:
        alice, bob = _user("rfv_a"), _user("rfv_b")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        end_session(session=session, user=bob)
        r = self._client_for(alice).post(f"/body-double/sessions/{session.id}/refill/")
        assert r.status_code == 200
        assert r.json() == {"status": "waiting"}

    def test_refill_endpoint_reports_ended(self) -> None:
        alice, bob = _user("rfv_a2"), _user("rfv_b2")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        end_session(session=session, user=bob)
        end_session(session=session, user=alice)
        r = self._client_for(alice).post(f"/body-double/sessions/{session.id}/refill/")
        assert r.json() == {"status": "ended"}

    def test_non_participant_404(self) -> None:
        alice, bob = _user("rfv_a3"), _user("rfv_b3")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        stranger = _user("rfv_s3")
        r = self._client_for(stranger).post(f"/body-double/sessions/{session.id}/refill/")
        assert r.status_code == 404


def _two_lonely_rooms(tag: str):
    """Two sessions formed FIRST (so the setups can't cross-match), then
    both partners leave and both survivors request refills. Returns
    (alice, session_a, carol, session_b)."""
    alice, bob = _user(f"tl_a_{tag}"), _user(f"tl_b_{tag}")
    enqueue(user=alice)
    _, session_a = enqueue(user=bob)
    carol, dave = _user(f"tl_c_{tag}"), _user(f"tl_d_{tag}")
    enqueue(user=carol)
    _, session_b = enqueue(user=dave)
    end_session(session=session_a, user=bob)
    end_session(session=session_b, user=dave)
    request_refill(session=session_a, user=alice)
    request_refill(session=session_b, user=carol)
    return alice, session_a, carol, session_b


@pytest.mark.django_db(transaction=True)
class TestHop:
    """A lonely survivor may CHOOSE to abandon their room and join
    another survivor's — the manual counterpart to auto-refill."""

    def test_hop_joins_other_survivors_room(self) -> None:
        alice, session_a, carol, session_b = _two_lonely_rooms("hop1")

        from apps.body_double.services import hop_to_room

        target = hop_to_room(session=session_b, user=carol)
        assert target is not None
        assert target.pk == session_a.pk
        # Carol's old room is ended (she was the last one attached).
        session_b.refresh_from_db()
        assert session_b.status == BodyDoubleSession.STATUS_ENDED
        # Alice's room now holds both, both MATCHED.
        session_a.refresh_from_db()
        assert {session_a.user_a_id, session_a.user_b_id} == {alice.id, carol.id}
        assert PoolTicket.objects.get(user=alice).status == PoolTicket.STATUS_MATCHED
        new_carol = PoolTicket.objects.filter(user=carol, status=PoolTicket.STATUS_MATCHED).get()
        assert new_carol.session_id == session_a.pk

    def test_no_room_returns_none(self) -> None:
        bob, session_b, _ = _survivor_setup("hop3")
        from apps.body_double.services import hop_to_room

        assert hop_to_room(session=session_b, user=bob) is None
        session_b.refresh_from_db()
        assert session_b.status == BodyDoubleSession.STATUS_ACTIVE

    def test_chattiness_incompatible_room_not_offered(self) -> None:
        # Quiet survivor must not be offered a chatty survivor's room.
        from apps.body_double.services import find_hoppable_room

        alice, bob = _user("hp_a_q"), _user("hp_b_q")
        enqueue(user=alice, chattiness=PoolTicket.CHATTINESS_CHATTY)
        _, session = enqueue(user=bob, chattiness=PoolTicket.CHATTINESS_CHATTY)
        end_session(session=session, user=bob)
        request_refill(session=session, user=alice)  # chatty refill waiting

        carol = _user("hp_c_q")
        enqueue(user=carol, chattiness=PoolTicket.CHATTINESS_QUIET)
        assert find_hoppable_room(user=carol) is None

    def test_hop_view_get_reports_availability_and_post_redirects(self) -> None:
        from django.test import Client

        _alice, session_a, carol, session_b = _two_lonely_rooms("hopv1")
        client = Client()
        s = client.session
        s["user_id"] = carol.id
        s.save()

        r = client.get(f"/body-double/sessions/{session_b.id}/hop/")
        assert r.json() == {"available": True}
        r = client.post(f"/body-double/sessions/{session_b.id}/hop/")
        assert r.status_code == 302
        assert r.url == f"/body-double/room/{session_a.id}/"

    def test_hop_view_get_false_when_no_rooms(self) -> None:
        from django.test import Client

        bob, session_b, _ = _survivor_setup("hopv3")
        client = Client()
        s = client.session
        s["user_id"] = bob.id
        s.save()
        r = client.get(f"/body-double/sessions/{session_b.id}/hop/")
        assert r.json() == {"available": False}


@pytest.mark.django_db(transaction=True)
class TestRequeue:
    def test_requeue_leaves_room_and_rejoins_pool_with_prefs(self) -> None:
        from apps.body_double.services import requeue_from_room

        alice, bob = _user("rq_a"), _user("rq_b")
        enqueue(user=alice, chattiness=PoolTicket.CHATTINESS_QUIET, duration_minutes=60)
        _, session = enqueue(user=bob, chattiness=PoolTicket.CHATTINESS_QUIET, duration_minutes=60)
        end_session(session=session, user=bob)

        ticket, new_session = requeue_from_room(session=session, user=alice)
        assert new_session is None  # pool empty
        assert ticket.status == PoolTicket.STATUS_WAITING
        assert ticket.session_id is None  # general queue, not a refill
        assert ticket.chattiness == PoolTicket.CHATTINESS_QUIET
        assert ticket.duration_minutes == 60
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ENDED

    def test_requeue_view_redirects_to_waiting(self) -> None:
        from django.test import Client

        alice, bob = _user("rqv_a"), _user("rqv_b")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        end_session(session=session, user=bob)
        client = Client()
        s = client.session
        s["user_id"] = alice.id
        s.save()
        r = client.post(f"/body-double/sessions/{session.id}/requeue/")
        assert r.status_code == 302
        assert r.url == "/body-double/waiting/"

    def test_requeue_can_match_into_another_survivors_room(self) -> None:
        from apps.body_double.services import requeue_from_room

        alice, session_a, carol, session_b = _two_lonely_rooms("rq2")
        # Carol requeues: the general matcher finds alice's refill ticket
        # and routes carol into alice's room.
        _ticket, new_session = requeue_from_room(session=session_b, user=carol)
        assert new_session is not None
        assert new_session.pk == session_a.pk
