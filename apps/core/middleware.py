"""Project-wide middleware.

`EnsureNicknameMiddleware` is the gatekeeper that makes the anonymous-nickname
auth model work: any request that doesn't yet have a `user_id` in the session
is redirected to `/accounts/start/`. The exempt list covers ops endpoints,
the picker itself, and static files.
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
