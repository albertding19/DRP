"""Ops endpoints — no auth, no DB access (so they stay green during outages)."""

from __future__ import annotations

import os

from django.http import JsonResponse


def healthz(request) -> JsonResponse:
    """Liveness probe. Render's health-check pings this."""
    return JsonResponse({"status": "ok"})


def version(request) -> JsonResponse:
    """Show the current commit SHA — proves CD pipeline updated."""
    commit = os.getenv("RENDER_GIT_COMMIT", "dev")
    return JsonResponse({"commit": commit[:7] if commit else "dev"})
