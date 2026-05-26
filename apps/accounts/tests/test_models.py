"""Tests for the User model + manager."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import User, validate_nickname


@pytest.mark.django_db
class TestUserManager:
    def test_create_anonymous_succeeds(self) -> None:
        user = User.objects.create_anonymous(nickname="alex")
        assert user.pk is not None
        assert user.nickname == "alex"
        assert user.email is None
        assert user.is_active is True
        assert not user.has_usable_password()

    def test_create_anonymous_collision_raises(self) -> None:
        User.objects.create_anonymous(nickname="alex")
        with pytest.raises(IntegrityError):
            User.objects.create_anonymous(nickname="alex")


class TestNicknameValidation:
    @pytest.mark.parametrize("good", ["alex", "alex_99", "a-b-c", "abc"])
    def test_valid(self, good: str) -> None:
        validate_nickname(good)  # should not raise

    @pytest.mark.parametrize(
        "bad,reason",
        [
            ("", "empty"),
            ("ab", "too short"),
            ("a" * 25, "too long"),
            ("has space", "space not allowed"),
            ("has!exclamation", "exclamation not allowed"),
        ],
    )
    def test_invalid(self, bad: str, reason: str) -> None:
        with pytest.raises(ValidationError):
            validate_nickname(bad)
