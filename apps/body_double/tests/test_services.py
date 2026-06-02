"""Tests for body-double services — enqueue, cancel, end_session.

Video provider is mocked via an autouse fixture so tests don't need real
LiveKit credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import User
from apps.body_double import services
from apps.body_double.models import BodyDoubleSession, PoolTicket
from apps.body_double.services import (
    AlreadyInPoolError,
    NotInSessionError,
    cancel_waiting,
    end_session,
    enqueue,
    get_active_ticket,
)


@pytest.fixture(autouse=True)
def _mock_video_provider():
    """Replace the configured VideoProvider with a no-op fake so tests
    don't need LiveKit credentials. `issue_join_token` returns a fake
    JWT; `create_room` / `end_room` are no-ops."""
    fake = MagicMock()
    fake.issue_join_token.return_value = "fake.jwt.token"
    fake.create_room.return_value = MagicMock(room_id="fake-room", ws_url="wss://fake/")
    with patch.object(services, "_video_provider", return_value=fake):
        yield fake


@pytest.fixture(autouse=True)
def _mock_broadcast():
    """The broadcast layer needs a running channel layer for live calls.
    Tests don't care about side-effects beyond 'was it called'; replace
    with a MagicMock that records arguments."""
    with (
        patch("apps.realtime.broadcast.broadcast_match_found") as fake,
        # Important: patch where services imports it from.
        patch("apps.body_double.services.broadcast") as services_mod,
    ):
        services_mod.broadcast_match_found = fake
        yield fake


def _user(nick: str) -> User:
    return User.objects.create_anonymous(nickname=nick)


@pytest.mark.django_db(transaction=True)
class TestEnqueue:
    def test_first_user_creates_waiting_ticket(self) -> None:
        alice = _user("alicequeue")
        ticket, session = enqueue(user=alice)
        assert ticket.status == PoolTicket.STATUS_WAITING
        assert ticket.community_id is None
        assert session is None
        assert PoolTicket.objects.count() == 1

    def test_with_community_records_it_on_ticket(self) -> None:
        from apps.communities.models import Community
        from apps.communities.services import create_community

        owner = _user("communityowner_enq")
        community = create_community(
            creator=owner, name="Enq Com", category=Community.CATEGORY_INTEREST
        )
        alice = _user("alice_community_enq")
        ticket, _ = enqueue(user=alice, community=community)
        assert ticket.community_id == community.id

    def test_second_user_triggers_match(self, _mock_broadcast) -> None:
        alice = _user("alice_match")
        bob = _user("bob_match")
        enqueue(user=alice)  # alice now waiting
        bob_ticket, session = enqueue(user=bob)

        # Both tickets matched, session created, room provisioned.
        assert session is not None
        assert session.status == BodyDoubleSession.STATUS_ACTIVE
        assert session.user_a_id == alice.id  # whoever was waiting first
        assert session.user_b_id == bob.id

        alice_ticket = PoolTicket.objects.get(user=alice)
        assert alice_ticket.status == PoolTicket.STATUS_MATCHED
        assert alice_ticket.session_id == session.id
        assert alice_ticket.matched_with_id == bob_ticket.id

        assert bob_ticket.status == PoolTicket.STATUS_MATCHED
        assert bob_ticket.matched_with_id == alice_ticket.id

        # Partner (the waiting user) was notified via the broadcast.
        _mock_broadcast.assert_called_once()
        kwargs = _mock_broadcast.call_args.kwargs
        assert kwargs["notify_user_id"] == alice.id

    def test_double_enqueue_raises_already_in_pool(self) -> None:
        alice = _user("alice_dup")
        enqueue(user=alice)
        with pytest.raises(AlreadyInPoolError):
            enqueue(user=alice)

    def test_re_enqueue_after_cancel_allowed(self) -> None:
        alice = _user("alice_retry")
        enqueue(user=alice)
        cancel_waiting(user=alice)
        # Now allowed again.
        ticket, _ = enqueue(user=alice)
        assert ticket.status == PoolTicket.STATUS_WAITING
        assert PoolTicket.objects.filter(user=alice).count() == 2


@pytest.mark.django_db(transaction=True)
class TestCancelWaiting:
    def test_cancels_waiting_ticket(self) -> None:
        alice = _user("alice_cancel")
        enqueue(user=alice)
        n = cancel_waiting(user=alice)
        assert n == 1
        ticket = PoolTicket.objects.get(user=alice)
        assert ticket.status == PoolTicket.STATUS_CANCELLED

    def test_no_op_when_not_waiting(self) -> None:
        alice = _user("alice_nowait")
        n = cancel_waiting(user=alice)
        assert n == 0

    def test_does_not_cancel_matched_ticket(self) -> None:
        alice = _user("alice_keep")
        bob = _user("bob_keep")
        enqueue(user=alice)
        enqueue(user=bob)  # alice → matched
        alice_ticket = PoolTicket.objects.get(user=alice)
        assert alice_ticket.status == PoolTicket.STATUS_MATCHED

        n = cancel_waiting(user=alice)
        assert n == 0
        alice_ticket.refresh_from_db()
        assert alice_ticket.status == PoolTicket.STATUS_MATCHED


@pytest.mark.django_db(transaction=True)
class TestEndSession:
    def _matched_pair(self):
        alice = _user("alice_session")
        bob = _user("bob_session")
        enqueue(user=alice)
        _, session = enqueue(user=bob)
        return alice, bob, session

    def test_participant_can_end(self) -> None:
        alice, _, session = self._matched_pair()
        end_session(session=session, user=alice)
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ENDED
        assert session.ended_at is not None

    def test_non_participant_cannot_end(self) -> None:
        _, _, session = self._matched_pair()
        stranger = _user("strangerend")
        with pytest.raises(NotInSessionError):
            end_session(session=session, user=stranger)
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ACTIVE

    def test_idempotent_on_already_ended(self) -> None:
        alice, _, session = self._matched_pair()
        end_session(session=session, user=alice)
        # Second call should be a no-op, not raise.
        end_session(session=session, user=alice)
        session.refresh_from_db()
        assert session.status == BodyDoubleSession.STATUS_ENDED

    def test_tickets_become_completed_so_user_can_re_enqueue(self) -> None:
        """Regression: after a session ends, both users' tickets must
        transition to COMPLETED so they can enqueue again. Previously the
        tickets stayed MATCHED, which caused the index view to redirect
        to the now-ended room → room view redirects back to index →
        Safari refuses the loop ('can't open this page')."""
        alice, bob, session = self._matched_pair()
        end_session(session=session, user=alice)

        alice_ticket = PoolTicket.objects.get(user=alice)
        bob_ticket = PoolTicket.objects.get(user=bob)
        assert alice_ticket.status == PoolTicket.STATUS_COMPLETED
        assert bob_ticket.status == PoolTicket.STATUS_COMPLETED

        # And re-enqueue is now allowed (no AlreadyInPoolError).
        new_ticket, _ = enqueue(user=alice)
        assert new_ticket.status == PoolTicket.STATUS_WAITING


@pytest.mark.django_db(transaction=True)
class TestGetActiveTicket:
    def test_returns_waiting_ticket(self) -> None:
        alice = _user("alice_active")
        ticket, _ = enqueue(user=alice)
        assert get_active_ticket(user=alice) == ticket

    def test_returns_matched_ticket(self) -> None:
        alice = _user("alice_amatch")
        bob = _user("bob_amatch")
        enqueue(user=alice)
        enqueue(user=bob)
        ticket = get_active_ticket(user=alice)
        assert ticket is not None
        assert ticket.status == PoolTicket.STATUS_MATCHED

    def test_none_when_no_active_tickets(self) -> None:
        alice = _user("alice_none")
        assert get_active_ticket(user=alice) is None

    def test_none_after_cancel(self) -> None:
        alice = _user("alice_postcancel")
        enqueue(user=alice)
        cancel_waiting(user=alice)
        assert get_active_ticket(user=alice) is None
