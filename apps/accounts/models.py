"""Custom User model + SignInToken (magic-link / OAuth state).

Design notes for the User model:
- Uses `AbstractBaseUser` (not `AbstractUser`) to avoid `username`,
  `first_name`, `last_name`, `email_address` columns the default user
  pulls in. We want explicit fields only.
- `nickname` is the canonical USERNAME_FIELD (legacy — preserved so
  existing sessions stay valid). Display name only; email is the new
  primary identity for sign-in.
- `email` is nullable + unique. Anonymous nickname-only users have
  `email IS NULL` and are prompted to "claim" their account; new signups
  always have one.
- No password is ever set — `create_anonymous()` calls
  `set_unusable_password()` so Django's auth machinery still works but
  no password ever validates.
"""

from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

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


class SignInToken(models.Model):
    """One-shot magic-link / verification token.

    A single table covers four intents:
      - `login`          — sign-in or signup (covers both via email)
      - `claim`          — existing nickname user adds an email
      - `email_change`   — settings page: verify a new address
      - `delete_confirm` — reserved for a v2 email-click delete (enum
                           present now so we don't need a later migration)

    **The raw token NEVER enters the database.** Generation hashes
    `secrets.token_urlsafe(32)` with SHA-256 and stores only the digest in
    `token_hash`. The raw token lives in exactly two places — the email
    body, and (briefly) the verify view's GET parameter. Redemption hashes
    the incoming `?t=…` parameter and looks up by `token_hash`. This means
    a DB dump leak cannot be used to log in as anyone — equivalent to
    Django's own password-reset and GitHub's email-verification flows.

    Single-use enforcement: `used_at` is set inside the same transaction
    that signs the user in, so concurrent clicks race safely. Sibling-
    token invalidation (`_invalidate_sibling_tokens` in services) marks
    any other unused tokens for the same `(email, intent)` as used at
    redemption time, so a forwarded duplicate link can't be exploited.

    Expiry: 15 minutes by default (configurable via
    `settings.SIGNIN_TOKEN_TTL_MIN`). The verify view rejects expired
    tokens BEFORE checking used_at so an expired-and-clicked-anyway link
    still says "this link expired" rather than "this link's already been
    used", which is friendlier UX.
    """

    INTENT_LOGIN = "login"
    INTENT_CLAIM = "claim"
    INTENT_EMAIL_CHANGE = "email_change"
    INTENT_DELETE_CONFIRM = "delete_confirm"
    INTENT_CHOICES = [
        (INTENT_LOGIN, "Sign-in (login or signup)"),
        (INTENT_CLAIM, "Claim — add email to nickname-only account"),
        (INTENT_EMAIL_CHANGE, "Verify new email on settings page"),
        (INTENT_DELETE_CONFIRM, "Confirm account deletion"),
    ]

    # SHA-256 hex digest is exactly 64 chars. Unique + indexed for O(1)
    # redemption lookup.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)

    # The email the token was issued for. Source of truth at redemption —
    # we do NOT trust `user.email` to match, since for signup tokens
    # `user` is null and email IS the only identity.
    email = models.EmailField()

    # null for fresh signups (no User row exists yet); set for
    # login / claim / email_change tokens.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="signin_tokens",
    )

    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Drives the rate-limit query: count tokens for (email, intent)
        # created in the last hour. Composite index ordered so the
        # date-range scan hits a contiguous slice.
        indexes = [
            models.Index(
                fields=["email", "intent", "-created_at"],
                name="signin_token_email_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SignInToken<{self.intent} for {self.email} hash={self.token_hash[:8]}…>"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @classmethod
    def default_expiry(cls) -> models.DateTimeField:
        """Helper for callers that need the canonical expiry timestamp."""
        return timezone.now() + timedelta(minutes=settings.SIGNIN_TOKEN_TTL_MIN)


class Friendship(models.Model):
    """A friend connection between two users.

    Lifecycle: `pending` (request sent) → `accepted` (mutual). One row
    per pair, direction = who asked. Friendship is symmetric once
    accepted — use `Friendship.friend_ids(user)` everywhere instead of
    querying a direction by hand.
    """

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_CHOICES = [(STATUS_PENDING, "Pending"), (STATUS_ACCEPTED, "Accepted")]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_sent"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_received"
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="one_request_per_pair"),
        ]

    def __str__(self) -> str:
        return f"friendship {self.from_user_id}→{self.to_user_id} ({self.status})"

    @classmethod
    def friend_ids(cls, user) -> set[int]:
        """Ids of everyone `user` has an ACCEPTED friendship with,
        regardless of who asked."""
        ids: set[int] = set()
        rows = cls.objects.filter(status=cls.STATUS_ACCEPTED).filter(
            models.Q(from_user=user) | models.Q(to_user=user)
        )
        for a, b in rows.values_list("from_user_id", "to_user_id"):
            ids.add(b if a == user.id else a)
        return ids
