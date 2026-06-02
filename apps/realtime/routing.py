"""WebSocket URL patterns.

Imported by `config/asgi.py`. Mount points:
  /ws/feed/                       — FeedConsumer (subscribed on the feed page)
  /ws/posts/<int:post_id>/        — PostConsumer (one channel per post)
  /ws/matchmaking/<int:user_id>/  — MatchmakingConsumer (waiting body-double user)
"""

from __future__ import annotations

from django.urls import path

from .consumers import FeedConsumer, MatchmakingConsumer, PostConsumer

websocket_urlpatterns = [
    path("ws/feed/", FeedConsumer.as_asgi()),
    path("ws/posts/<int:post_id>/", PostConsumer.as_asgi()),
    path("ws/matchmaking/<int:user_id>/", MatchmakingConsumer.as_asgi()),
]
