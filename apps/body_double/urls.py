"""Body-double URLs.

Mounted at /body-double/ in config.urls.
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "body_double"

urlpatterns = [
    path("", views.index, name="index"),
    path("find/", views.find, name="find"),
    path("waiting/", views.waiting, name="waiting"),
    path("status/", views.status, name="status"),
    path("room/<int:session_id>/", views.room, name="room"),
    path("leave/", views.leave, name="leave"),
    path("sessions/<int:session_id>/end/", views.end, name="end"),
    path("schedule/", views.schedule, name="schedule"),
    path("schedule/book/", views.book_view, name="book"),
    path("schedule/status/", views.schedule_status, name="schedule_status"),
    path("bookings/<int:booking_id>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("bookings/<int:booking_id>/join/", views.booking_join, name="booking_join"),
]
