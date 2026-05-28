"""Smoke tests for core ops endpoints."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_returns_200() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 201
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_version_returns_commit_field() -> None:
    response = Client().get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert "commit" in payload
    assert isinstance(payload["commit"], str)
