"""Template context processors."""

from __future__ import annotations

import os

from django.http import HttpRequest


def build_info(request: HttpRequest) -> dict[str, str]:
    """Expose commit SHA + brand to every template.

    `PROJECT_NAME` is the user-facing brand; the codebase still lives under
    `apps/`, the repo is still `DRP`. Only the rendered surface speaks of
    "unmasked" — the rebrand was a Milestone 2 design decision.
    """
    commit = os.getenv("RENDER_GIT_COMMIT", "dev")
    return {
        "BUILD_COMMIT": commit[:7] if commit else "dev",
        "PROJECT_NAME": "unmasked",
        "PROJECT_TAGLINE": "strategies that actually work",
    }
