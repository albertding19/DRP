"""Vote admin."""

from __future__ import annotations

from django.contrib import admin

from .models import Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content_type", "object_id", "value", "created_at")
    list_filter = ("value", "content_type", "created_at")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
