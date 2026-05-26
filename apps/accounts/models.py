"""Custom User model — nickname-only auth.

Design notes:
- Uses `AbstractBaseUser` (not `AbstractUser`) to avoid `username`,
  `first_name`, `last_name`, `email_address` columns the default user
  pulls in. We want explicit fields only.
- `nickname` is the canonical identifier (USERNAME_FIELD).
- `email` is nullable + unique from day one. The M4 "claim with email"
  feature will write to it without needing a schema migration.
- No password is ever set — `create_anonymous()` calls
  `set_unusable_password()` so Django's auth machinery still works but
  no password ever validates.
"""

from __future__ import annotations

import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
NICKNAME_MIN = 3
NICKNAME_MAX = 24


def validate_nickname(value: str) -> None:
    """Raise ValidationError if nickname fails format/length rules."""
    if not value:
        raise ValidationError("Nickname cannot be empty.")
    if len(value) < NICKNAME_MIN:
        raise ValidationError(f"Nickname must be at least {NICKNAME_MIN} characters.")
    if len(value) > NICKNAME_MAX:
        raise ValidationError(f"Nickname must be at most {NICKNAME_MAX} characters.")
    if not NICKNAME_PATTERN.match(value):
        raise ValidationError("Nickname can only contain letters, numbers, _ and -.")


class UserManager(BaseUserManager):
    """No `create_superuser` for now — admin access is handled via shell."""

    def create_anonymous(self, nickname: str) -> User:
        """Create a user with a nickname and no password.

        Caller is responsible for catching IntegrityError on collision.
        """
        validate_nickname(nickname)
        user = self.model(nickname=nickname)
        user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """A nickname-only user.

    No password, no email required, no first/last name. The nickname IS the
    identity. Email is nullable + unique so a future "claim this account
    with email" view can populate it without schema changes.
    """

    nickname = models.CharField(
        max_length=NICKNAME_MAX,
        unique=True,
        db_index=True,
        validators=[validate_nickname],
    )
    email = models.EmailField(
        null=True,
        blank=True,
        unique=True,
        help_text="Optional. Populated later if the user claims their account.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "nickname"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.nickname

    @property
    def is_authenticated(self) -> bool:  # type: ignore[override]
        # `AbstractBaseUser` already provides this, but explicit for clarity.
        return True
