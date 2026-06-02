"""Admin registration for tasks."""

from __future__ import annotations

from django.contrib import admin

from .models import BusyBlock, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "status", "priority", "scheduled_start", "deadline")
    list_filter = ("status", "priority", "energy", "body_double_preferred")
    search_fields = ("name", "user__nickname")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at", "completed_at")


@admin.register(BusyBlock)
class BusyBlockAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "kind", "start_at", "end_at")
    list_filter = ("kind",)
    search_fields = ("name", "user__nickname")
    raw_id_fields = ("user",)
