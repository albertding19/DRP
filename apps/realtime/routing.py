"""WebSocket URL patterns.

Imported by `config/asgi.py`. Consumers themselves land Thu 28 May.
Empty list is fine for now — ASGI loads + HTTP works without any WS routes.
"""

from __future__ import annotations

from django.urls import re_path

websocket_urlpatterns: list[re_path] = []
