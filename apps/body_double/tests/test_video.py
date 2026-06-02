"""Tests for the LiveKit video provider — mocked at the SDK level so
no network call is made and no real API key is required."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.body_double.video.base import RoomInfo
from apps.body_double.video.livekit import LiveKitProvider


class TestLiveKitProvider:
    def test_create_room_returns_room_info(self, settings):
        settings.LIVEKIT_URL = "wss://drp-xyz.livekit.cloud"
        info = LiveKitProvider().create_room(room_id="r123")
        assert isinstance(info, RoomInfo)
        assert info.room_id == "r123"
        assert info.ws_url == "wss://drp-xyz.livekit.cloud"

    def test_create_room_is_idempotent_no_op(self, settings):
        """LiveKit creates rooms on first join, so create_room shouldn't
        side-effect anything we can observe — calling it twice is fine."""
        settings.LIVEKIT_URL = "wss://x/"
        a = LiveKitProvider().create_room(room_id="dup")
        b = LiveKitProvider().create_room(room_id="dup")
        assert a == b

    def test_issue_join_token_uses_nickname_as_identity(self, settings):
        settings.LIVEKIT_API_KEY = "key123"
        settings.LIVEKIT_API_SECRET = "secret123"
        user = MagicMock()
        user.nickname = "alice"

        # Mock the AccessToken builder chain so we don't need a real
        # secret or to inspect a real JWT.
        fake_builder = MagicMock()
        fake_builder.with_identity.return_value = fake_builder
        fake_builder.with_name.return_value = fake_builder
        fake_builder.with_ttl.return_value = fake_builder
        fake_builder.with_grants.return_value = fake_builder
        fake_builder.to_jwt.return_value = "FAKE.JWT.TOKEN"

        with patch("livekit.api.AccessToken", return_value=fake_builder) as mk:
            token = LiveKitProvider().issue_join_token(room_id="room1", user=user)

        # The builder was constructed with the configured key + secret.
        mk.assert_called_once_with("key123", "secret123")
        # And identity was set to the nickname.
        fake_builder.with_identity.assert_called_once_with("alice")
        fake_builder.with_name.assert_called_once_with("alice")
        assert token == "FAKE.JWT.TOKEN"

    def test_issue_join_token_grants_room_scope(self, settings):
        """The grants passed to LiveKit must restrict the token to the
        specific room — otherwise a leaked token could join any room."""
        settings.LIVEKIT_API_KEY = "k"
        settings.LIVEKIT_API_SECRET = "s"
        user = MagicMock()
        user.nickname = "u"

        fake_builder = MagicMock()
        for m in ("with_identity", "with_name", "with_ttl", "with_grants"):
            getattr(fake_builder, m).return_value = fake_builder
        fake_builder.to_jwt.return_value = "x"

        captured_grants = []
        original_with_grants = fake_builder.with_grants

        def capture(g):
            captured_grants.append(g)
            return original_with_grants(g)

        fake_builder.with_grants = capture

        with patch("livekit.api.AccessToken", return_value=fake_builder):
            LiveKitProvider().issue_join_token(room_id="my-specific-room", user=user)

        assert len(captured_grants) == 1
        g = captured_grants[0]
        assert g.room == "my-specific-room"
        assert g.room_join is True
        assert g.can_publish is True
        assert g.can_subscribe is True

    def test_end_room_is_noop(self):
        """LiveKit auto-cleans empty rooms; provider's end_room is a no-op."""
        # Just shouldn't raise.
        LiveKitProvider().end_room(room_id="any")
