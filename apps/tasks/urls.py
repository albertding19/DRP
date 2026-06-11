"""URL routes for the tasks app."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.index, name="index"),
    path("region/", views.region, name="region"),
    path("add/", views.add_task, name="add"),
    path("plan/", views.plan, name="plan"),
    path("break/", views.take_break, name="break"),
    path("busy/add/", views.add_busy, name="busy_add"),
    path("busy/<int:block_id>/delete/", views.delete_busy, name="busy_delete"),
    path("<int:task_id>/edit/", views.edit_task, name="edit"),
    path("<int:task_id>/delete/", views.delete, name="delete"),
    path("<int:task_id>/start/", views.start, name="start"),
    path("<int:task_id>/done/", views.done, name="done"),
    path("<int:task_id>/skip/", views.skip, name="skip"),
]
