"""Service-layer for accounts. Keeps views thin."""

from __future__ import annotations

from django.db import IntegrityError

from .models import User


class NicknameTaken(Exception):
    """Raised when create_user races with another request for the same nickname."""


def create_user_with_nickname(nickname: str) -> User:
    """Create a User; raises NicknameTaken on race-condition collision."""
    try:
        return User.objects.create_anonymous(nickname=nickname)
    except IntegrityError as exc:
        raise NicknameTaken(nickname) from exc
