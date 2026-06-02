"""Communities URLs.

Mounted at /communities/ in config.urls.
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("new/", views.create_view, name="create"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/join/", views.join, name="join"),
    path("<slug:slug>/leave/", views.leave, name="leave"),
]
