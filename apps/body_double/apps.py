"""App config for body-doubling — random pool matchmaking + video rooms."""

from __future__ import annotations

from django.apps import AppConfig


class BodyDoubleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.body_double"
    label = "body_double"
    verbose_name = "Body double matchmaking"
