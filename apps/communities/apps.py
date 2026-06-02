"""App config for communities — joinable groups categorised by
module / course / interest / institution."""

from __future__ import annotations

from django.apps import AppConfig


class CommunitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.communities"
    label = "communities"
    verbose_name = "Communities"

    def ready(self) -> None:
        # Importing signals registers the member_count denormalisation
        # handlers on CommunityMembership.
        from . import signals  # noqa: F401
