"""Comment URLs.

Mounted under `''` in config.urls so the paths are:
    /posts/<pk>/comments/                GET   create top-level (POST) /
                                                permalink page (GET, with cpk)
    /posts/<pk>/comments/<cpk>/          GET   single-comment permalink page
    /comments/<pk>/reply/                POST  create reply
    /comments/<pk>/delete/               POST  soft-delete (author only)
"""

from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("posts/<int:post_pk>/comments/", views.create, name="create"),
    path(
        "posts/<int:post_pk>/comments/<int:comment_pk>/",
        views.permalink,
        name="permalink",
    ),
    path("comments/<int:comment_pk>/reply/", views.reply, name="reply"),
    path("comments/<int:comment_pk>/delete/", views.delete, name="delete"),
]
