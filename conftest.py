"""Pytest fixtures shared across all apps.

`DJANGO_SETTINGS_MODULE` is set in `[tool.pytest.ini_options]` (pyproject.toml).
This file holds project-wide fixtures so each app's `tests/` directory stays lean.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client_with_session(client, db):
    """A Django test client with a freshly created anonymous user in session."""
    from apps.accounts.models import User

    user = User.objects.create_anonymous(nickname="testuser")
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user
