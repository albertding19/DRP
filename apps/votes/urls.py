"""Vote URLs."""

from django.urls import path

from . import views

app_name = "votes"

urlpatterns = [
    path(
        "vote/<str:target_type>/<int:object_id>/",
        views.cast,
        name="cast",
    ),
]
