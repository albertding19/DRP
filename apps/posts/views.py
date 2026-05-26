"""Post views — placeholder feed today, full CRUD lands Wed 27 May."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Post


def feed(request: HttpRequest) -> HttpResponse:
    """Placeholder feed.

    Reads the latest 25 posts (none yet) and renders them. Wednesday's work
    replaces this with: paginated, sortable (hot/new/top), tag-filterable,
    HTMX-aware. For now it just confirms the route resolves and the auth
    middleware works end-to-end.
    """
    posts = Post.objects.order_by("-created_at")[:25]
    return render(request, "posts/feed.html", {"posts": posts})
