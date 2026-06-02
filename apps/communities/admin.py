"""Communities admin — list / filter / hard-delete."""

from __future__ import annotations

from django.contrib import admin

from .models import Community, CommunityMembership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "member_count", "creator", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("name", "slug", "description", "creator__nickname")
    raw_id_fields = ("creator",)
    readonly_fields = ("created_at", "updated_at", "member_count")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("-member_count", "name")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "community", "user", "created_at")
    list_filter = ("community", "created_at")
    raw_id_fields = ("user", "community")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__nickname", "community__name")
