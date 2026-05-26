"""Post URLs — placeholder feed today, full CRUD lands Wed 27 May."""

from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.feed, name="feed"),
]
