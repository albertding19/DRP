"""Tag admin."""

from __future__ import annotations

from django.contrib import admin

from .models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "post_count")
    search_fields = ("name", "slug")
    readonly_fields = ("post_count",)
    prepopulated_fields = {"slug": ("name",)}
