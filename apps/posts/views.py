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
from django.views.decorators.http import require_http_methods, require_POST

from apps.realtime import broadcast

from .forms import PostForm
from .models import Post
from .services import create_post, feed_queryset, report_post


@require_http_methods(["GET"])
def feed(request: HttpRequest) -> HttpResponse:
    """The home page — paginated list of posts.

    Supports ?sort= and ?tag= filters. Tag filter is preferred via
    /tags/<slug>/ for clean URLs, but the query param works too.
    """
    sort = request.GET.get("sort", "new")
    qs = feed_queryset(sort=sort)
    tag_slug = request.GET.get("tag")
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)
    page = Paginator(qs, per_page=25).get_page(request.GET.get("page", 1))
    return render(
        request,
        "posts/feed.html",
        {"page": page, "posts": page.object_list, "sort": sort},
    )


@require_http_methods(["GET"])
def detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show one post (and its comments).

    Excludes hidden posts (L3 community report threshold reached) — same
    treatment as soft-deleted: 404. Admins can unhide via Django admin.
    """
    post = get_object_or_404(
        Post.objects.select_related("author"),
        pk=pk,
        is_deleted=False,
        is_hidden=False,
    )
    return render(request, "posts/detail.html", {"post": post})


@login_required
@require_POST
def report(request: HttpRequest, pk: int) -> HttpResponse:
    """Record a user's report against a post. Idempotent per (post, user).

    HTMX: returns `_reported.html` partial that replaces the Report button
    with a "Thanks — we've recorded your report" confirmation.
    Non-HTMX: redirects to the post detail page (or feed if hidden).

    If the report crosses the threshold, broadcasts a WS `post_hidden`
    event to the feed group AND the per-post group so live viewers' UI
    removes the card without a refresh.
    """
    post = get_object_or_404(Post, pk=pk, is_deleted=False, is_hidden=False)
    _, just_hidden = report_post(post=post, reporter=request.user)

    if just_hidden:
        broadcast.broadcast_post_hidden(post)

    if request.htmx:
        return render(request, "posts/_reported.html", {"post": post})
    return redirect(reverse("posts:detail", args=[post.pk]))


@login_required
@require_http_methods(["GET", "POST"])
def create(request: HttpRequest) -> HttpResponse:
    """Render and process the Share form.

    Passes `author=request.user` to the form so the moderation L1/L2 checks
    can attribute any block decisions to the submitting user in
    `ModerationLog`. On a moderation rejection, the form re-renders with the
    user's typed input preserved and an error message above the offending
    field.
    """
    if request.method == "POST":
        form = PostForm(request.POST, author=request.user)
        if form.is_valid():
            post = create_post(
                author=request.user,
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                post_type=form.cleaned_data["post_type"],
                tag_names=form.cleaned_data.get("tags") or [],
            )
            return redirect(reverse("posts:detail", args=[post.pk]))
    else:
        form = PostForm()
    return render(request, "posts/form.html", {"form": form})
