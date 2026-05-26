"""Custom auth backend that resolves users from session `user_id`.

Plugged into `AUTHENTICATION_BACKENDS` in settings. The picker view (which
runs before any user exists) calls `auth.login()` after creating the user.
The middleware (in `apps.core.middleware`) does the runtime attachment via
session lookup.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class NicknameSessionBackend(ModelBackend):
    """Look up a User by nickname (no password check)."""

    def authenticate(self, request, nickname: str | None = None, **kwargs):  # type: ignore[override]
        if nickname is None:
            return None
        User = get_user_model()
        try:
            return User.objects.get(nickname=nickname, is_active=True)
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):  # type: ignore[override]
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
