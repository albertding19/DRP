"""Video-provider Protocol — the pluggable extension point for the
underlying call infrastructure.

The MVP implementation is `livekit.LiveKitProvider`. Future providers
(`JitsiProvider`, `DailyProvider`, `SelfHostedLiveKitProvider`) implement
the same Protocol and are selected via `settings.BODY_DOUBLE_VIDEO_PROVIDER`.

The services layer talks only to this Protocol, never to the LiveKit SDK
directly. Provider swap = settings change + new module; no view, template,
or service changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RoomInfo:
    """Provider-side identifiers needed to join a room.

    `room_id` is the value passed to `issue_join_token` and rendered as
    the call-page route. `ws_url` is the provider's signalling/media
    endpoint (e.g. `wss://drp-xyz.livekit.cloud`); rendered into the call
    page so the client SDK knows where to connect.
    """

    room_id: str
    ws_url: str


class VideoProvider(Protocol):
    """Abstract video-call provider."""

    def create_room(
        self, *, room_id: str, max_participants: int = 2
    ) -> RoomInfo:  # pragma: no cover
        """Provision (or no-op claim) a room. Idempotent on `room_id`."""
        ...

    def issue_join_token(self, *, room_id: str, user) -> str:  # type: ignore[no-untyped-def]  # pragma: no cover
        """Return a short-lived credential authorising `user` to join `room_id`."""
        ...

    def end_room(self, *, room_id: str) -> None:  # pragma: no cover
        """Best-effort termination of the room. Implementations may be a
        no-op if the provider auto-cleans empty rooms."""
        ...
