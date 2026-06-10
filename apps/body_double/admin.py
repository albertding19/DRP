"""Admin for body-double matchmaking — for moderators to inspect pool +
session state. Read-only on most fields; an `End selected` action lets
mods kill a stuck session."""

from __future__ import annotations

from django.contrib import admin
from django.utils import timezone

from .models import BodyDoubleSession, PoolTicket, ScheduledBooking


@admin.register(PoolTicket)
class PoolTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "matched_with",
        "session",
        "created_at",
    )
    list_filter = ("status", "created_at")
    raw_id_fields = ("user", "matched_with", "session")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__nickname",)
    ordering = ("-created_at",)


@admin.register(ScheduledBooking)
class ScheduledBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "start_at",
        "duration_minutes",
        "status",
        "matched_with",
        "session",
    )
    list_filter = ("status", "start_at")
    raw_id_fields = ("user", "community", "matched_with", "session")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__nickname",)
    ordering = ("-start_at",)


@admin.register(BodyDoubleSession)
class BodyDoubleSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_room_id",
        "user_a",
        "user_b",
        "status",
        "started_at",
        "ended_at",
    )
    list_filter = ("status", "started_at")
    raw_id_fields = ("user_a", "user_b")
    readonly_fields = ("created_at", "updated_at", "room_id", "started_at")
    search_fields = ("room_id", "user_a__nickname", "user_b__nickname")
    ordering = ("-started_at",)
    actions = ("end_selected",)

    @admin.display(description="Room")
    def short_room_id(self, obj: BodyDoubleSession) -> str:
        return obj.room_id[:12] + ("…" if len(obj.room_id) > 12 else "")

    @admin.action(description="End selected sessions")
    def end_selected(self, request, queryset):  # type: ignore[no-untyped-def]
        n = queryset.filter(status=BodyDoubleSession.STATUS_ACTIVE).update(
            status=BodyDoubleSession.STATUS_ENDED,
            ended_at=timezone.now(),
        )
        self.message_user(request, f"Ended {n} session(s).")
