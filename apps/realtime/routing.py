"""WebSocket URL patterns.

Imported by `config/asgi.py`. Mount points:
  /ws/feed/                       — FeedConsumer (subscribed on the feed page)
  /ws/posts/<int:post_id>/        — PostConsumer (one channel per post)
  /ws/matchmaking/<int:user_id>/  — MatchmakingConsumer (waiting body-double user)
  /ws/signin/<int:token_id>/      — SignInConsumer (check-email page wait)
"""

from __future__ import annotations

from django.urls import path

from .consumers import FeedConsumer, MatchmakingConsumer, PostConsumer, SignInConsumer

websocket_urlpatterns = [
    path("ws/feed/", FeedConsumer.as_asgi()),
    path("ws/posts/<int:post_id>/", PostConsumer.as_asgi()),
    path("ws/matchmaking/<int:user_id>/", MatchmakingConsumer.as_asgi()),
    path("ws/signin/<int:token_id>/", SignInConsumer.as_asgi()),
]
