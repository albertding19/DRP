"""Comment admin."""

from __future__ import annotations

from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "parent", "score", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    raw_id_fields = ("post", "parent", "author")
    search_fields = ("body", "author__nickname")
    readonly_fields = ("created_at", "updated_at")
