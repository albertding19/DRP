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


@pytest.fixture(autouse=True)
def _neutralise_claude_judge(monkeypatch, request):
    """Autouse: stop tests from hitting the real Anthropic API.

    Any unit / integration test would otherwise reach out over the network
    (or fail because ANTHROPIC_API_KEY is unset). We patch the L2 judge to
    always return (False, "") — the same fail-open path it takes in
    production when the key is missing.

    Tests that explicitly want to exercise L2 should:
      - Patch `apps.moderation.services.judge_with_claude` to a custom
        function inside the test body, OR
      - Mark with `@pytest.mark.live` to opt out of this autouse and hit
        the real API (live tests are skipped in CI by default).
    """
    if "live" in request.keywords:
        return  # let live tests through

    def _always_pass(text: str) -> tuple[bool, str]:
        return False, ""

    monkeypatch.setattr("apps.moderation.services.judge_with_claude", _always_pass)
