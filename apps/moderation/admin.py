"""Admin for ModerationLog — surface block decisions for human review."""

from __future__ import annotations

from django.contrib import admin

from .models import ModerationLog


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "layer",
        "surface",
        "author",
        "false_positive",
        "created_at",
        "short_text",
    )
    list_filter = ("layer", "surface", "false_positive", "created_at")
    search_fields = ("text", "reason", "author__nickname")
    raw_id_fields = ("author",)
    readonly_fields = ("created_at", "updated_at", "layer", "surface", "text", "reason", "author")
    ordering = ("-created_at",)

    @admin.display(description="Text (preview)")
    def short_text(self, obj: ModerationLog) -> str:
        body = obj.text or ""
        return body[:80] + ("…" if len(body) > 80 else "")
