"""Post URLs.

Mounted under both `''` (so `/` and `/feed/` hit the feed) and via
`posts/new/`, `posts/<pk>/` for create + detail.
"""

from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("feed/", views.feed, name="feed_alias"),
    path("posts/new/", views.create, name="create"),
    path("posts/<int:pk>/", views.detail, name="detail"),
]
