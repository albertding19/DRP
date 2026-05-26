"""WebSocket URL patterns.

Imported by `config/asgi.py`. Mount points:
  /ws/feed/                 — FeedConsumer (subscribed on the feed page)
  /ws/posts/<int:post_id>/  — PostConsumer (one channel per post)
"""

from __future__ import annotations

from django.urls import path

from .consumers import FeedConsumer, PostConsumer

websocket_urlpatterns = [
    path("ws/feed/", FeedConsumer.as_asgi()),
    path("ws/posts/<int:post_id>/", PostConsumer.as_asgi()),
]
