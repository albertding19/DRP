"""Comment admin."""

from __future__ import annotations

from django.contrib import admin

from .models import Comment, CommentReport


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "author",
        "parent",
        "score",
        "report_count",
        "is_hidden",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_hidden", "is_deleted", "created_at")
    raw_id_fields = ("post", "parent", "author")
    search_fields = ("body", "author__nickname")
    readonly_fields = ("created_at", "updated_at", "report_count")
    actions = ("unhide_selected",)

    @admin.action(description="Unhide selected comments")
    def unhide_selected(self, request, queryset):  # type: ignore[no-untyped-def]
        n = queryset.update(is_hidden=False)
        self.message_user(request, f"Unhid {n} comment(s).")


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ("id", "comment", "reporter", "created_at")
    list_filter = ("created_at",)
    raw_id_fields = ("comment", "reporter")
    readonly_fields = ("created_at", "updated_at", "comment", "reporter")
