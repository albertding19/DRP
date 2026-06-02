"""LiveKit Cloud implementation of `VideoProvider`.

LiveKit auto-creates rooms on first participant join, so `create_room` at
the MVP is effectively a no-op that just returns the `RoomInfo` for the
caller to render into the call page. The real work is `issue_join_token`,
which mints a short-lived JWT scoped to the requested room.

Future tightening: pre-create the room via `LiveKitAPI.room.create_room`
to set `max_participants=2` server-side. The free tier supports this; we
defer it because LiveKit also enforces it via the token's grants.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings

from .base import RoomInfo


class LiveKitProvider:
    """Production video provider using LiveKit Cloud."""

    def create_room(
        self,
        *,
        room_id: str,
        max_participants: int = 2,  # noqa: ARG002
    ) -> RoomInfo:
        # LiveKit creates rooms lazily on first join. We just return the
        # RoomInfo so the caller can render the join URL + token.
        return RoomInfo(room_id=room_id, ws_url=settings.LIVEKIT_URL)

    def issue_join_token(self, *, room_id: str, user) -> str:  # type: ignore[no-untyped-def]
        """Mint a 1-hour JWT authorising `user` to join `room_id`.

        Identity = nickname (matches the rest of the app's identity model
        — no real names, no email leaked to the call). Grants are
        intentionally minimal: room-join + publish + subscribe, no admin.
        """
        from livekit.api import AccessToken, VideoGrants

        return (
            AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(user.nickname)
            .with_name(user.nickname)
            .with_ttl(timedelta(hours=1))
            .with_grants(
                VideoGrants(
                    room=room_id,
                    room_join=True,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .to_jwt()
        )

    def end_room(self, *, room_id: str) -> None:  # noqa: ARG002
        # LiveKit auto-cleans rooms after all participants leave, so we
        # don't need to call the server API. Kept as a real method so the
        # interface contract holds for other providers.
        return None
