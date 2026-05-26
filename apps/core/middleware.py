"""Project-wide middleware.

Two middlewares live here:

- `EnsureNicknameMiddleware`: the gatekeeper that makes the anonymous-nickname
  auth model work. Any request that doesn't yet have a `user_id` in the session
  is redirected to `/accounts/start/`. The exempt list covers ops endpoints,
  the picker itself, and static files.

- `NoCacheHTMLMiddleware`: tells browsers + CDN edges never to cache HTML
  responses. Without this, transient 404s during Render deploy windows can
  get cached client-side and persist for minutes after the deploy completes.
  Static assets (CSS/JS) still get long cache lifetimes via WhiteNoise's
  hashed filenames — only `text/html` responses are no-stored.
"""

from __future__ import annotations

from collections.abc import Callable

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


class EnsureNicknameMiddleware:
    """Attach `request.user` from `session['user_id']` or redirect to picker."""

    EXEMPT_PREFIXES: tuple[str, ...] = (
        "/accounts/start",
        "/accounts/check-nickname",
        "/healthz",
        "/version",
        "/static/",
        "/admin/login",
        "/admin/logout",
    )

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        user_id = request.session.get("user_id")
        if not user_id:
            return redirect(f"/accounts/start/?next={request.path}")

        # Attach the user for downstream views/templates. If the user_id is
        # stale (row deleted), clear it and re-prompt.
        User = get_user_model()
        try:
            request.user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            request.session.flush()
            return redirect("/accounts/start/")

        return self.get_response(request)


class NoCacheHTMLMiddleware:
    """Prevent browsers + edges from caching HTML responses.

    Deploy windows on Render's free tier produce brief 404s as the old daphne
    stops and the new one starts. Without explicit cache headers, browsers
    cache those transient 404s using their default heuristics and continue
    serving them after the deploy succeeds.

    Setting `Cache-Control: no-store` on HTML stops this cleanly. Static
    assets aren't affected — they go through WhiteNoise which sets its own
    long-lived cache headers on hashed filenames.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
