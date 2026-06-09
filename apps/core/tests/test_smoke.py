"""Smoke tests for core ops endpoints + project-wide brand."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User


@pytest.mark.django_db
def test_healthz_returns_200() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_version_returns_commit_field() -> None:
    response = Client().get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert "commit" in payload
    assert isinstance(payload["commit"], str)


@pytest.mark.django_db
def test_brand_is_unmasked_on_rendered_page() -> None:
    # M2 brand pass: PROJECT_NAME flipped from 'DRP' to 'unmasked' in
    # apps/core/context_processors.py. This guards against a future revert
    # that wouldn't be visible in the per-app tests (those mostly inspect
    # feature copy, not chrome).
    user = User.objects.create_anonymous(nickname="brandcheck")
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    response = client.get("/feed/")
    assert response.status_code == 200
    assert b"unmasked" in response.content
    assert b"strategies that actually work" in response.content
