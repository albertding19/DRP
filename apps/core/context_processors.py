"""Template context processors."""

from __future__ import annotations

import os

from django.http import HttpRequest


def build_info(request: HttpRequest) -> dict[str, str]:
    """Expose commit SHA + project name to every template."""
    commit = os.getenv("RENDER_GIT_COMMIT", "dev")
    return {
        "BUILD_COMMIT": commit[:7] if commit else "dev",
        "PROJECT_NAME": "DRP",
    }
