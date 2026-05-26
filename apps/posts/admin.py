"""Django admin registration — moderation panel for posts."""

from __future__ import annotations

from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "post_type",
        "author",
        "score",
        "comment_count",
        "is_deleted",
        "created_at",
    )
    list_filter = ("post_type", "is_deleted", "created_at")
    search_fields = ("title", "body", "author__nickname")
    readonly_fields = ("created_at", "updated_at", "score", "comment_count")
    actions = ("soft_delete_selected",)

    @admin.action(description="Soft-delete selected posts")
    def soft_delete_selected(self, request, queryset):  # noqa: ANN001, ARG002
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f"Soft-deleted {updated} post(s).")
