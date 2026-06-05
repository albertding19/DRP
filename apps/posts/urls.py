"""Post URLs.

`/feed/` hosts the post feed; `posts/new/` + `posts/<pk>/` cover create and
detail. The root path `/` is owned by the homepage (apps.core.views.home).
"""

from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("feed/", views.feed, name="feed"),
    path("posts/new/", views.create, name="create"),
    path("posts/<int:pk>/", views.detail, name="detail"),
    path("posts/<int:pk>/report/", views.report, name="report"),
]
