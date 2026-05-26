"""Post views — feed + create + detail.

The feed is the app's landing page; the create view is the "Share" flow;
the detail view is what you see when you click a post. All three are
HTMX-aware: a request from HTMX (django-htmx sets `request.htmx`) gets a
partial fragment; a normal request gets the full base-extended page.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import PostForm
from .models import Post
from .services import create_post, feed_queryset


@require_http_methods(["GET"])
def feed(request: HttpRequest) -> HttpResponse:
    """The home page — paginated list of posts."""
    sort = request.GET.get("sort", "new")
    qs = feed_queryset(sort=sort)
    page = Paginator(qs, per_page=25).get_page(request.GET.get("page", 1))
    return render(
        request,
        "posts/feed.html",
        {"page": page, "posts": page.object_list, "sort": sort},
    )


@require_http_methods(["GET"])
def detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show one post (and its comments — view added Mon 1 Jun)."""
    post = get_object_or_404(Post.objects.select_related("author"), pk=pk, is_deleted=False)
    return render(request, "posts/detail.html", {"post": post})


@login_required
@require_http_methods(["GET", "POST"])
def create(request: HttpRequest) -> HttpResponse:
    """Render and process the Share form."""
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = create_post(
                author=request.user,
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                post_type=form.cleaned_data["post_type"],
            )
            return redirect(reverse("posts:detail", args=[post.pk]))
    else:
        form = PostForm()
    return render(request, "posts/form.html", {"form": form})
