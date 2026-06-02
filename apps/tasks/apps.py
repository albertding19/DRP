"""App config for tasks — to-do list that auto-generates today's timetable."""

from __future__ import annotations

from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks"
