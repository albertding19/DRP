"""Tag URLs.

Mounted under `tags/` in config.urls — final paths are:
    /tags/                — tag list
    /tags/<slug>/         — tag detail (feed filtered by tag)
"""

from django.urls import path

from . import views

app_name = "tags"

urlpatterns = [
    path("", views.tag_list, name="list"),
    path("<slug:slug>/", views.tag_detail, name="detail"),
]
