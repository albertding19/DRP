"""Comment views — create, reply, delete.

All return HTMX-friendly partials when possible, so a comment posting from
the detail page swaps inline without a full reload. Non-HTMX clients get
a redirect back to the detail page.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.posts.models import Post

from .forms import CommentForm
from .models import Comment
from .services import create_comment, soft_delete_comment


@login_required
@require_POST
def create(request: HttpRequest, post_pk: int) -> HttpResponse:
    """Create a top-level comment on a post."""
    post = get_object_or_404(Post, pk=post_pk, is_deleted=False)
    form = CommentForm(request.POST)
    if not form.is_valid():
        # Re-render the detail page so the user sees the form errors.
        return _redirect_with_error(request, post, form)

    try:
        comment = create_comment(author=request.user, post=post, body=form.cleaned_data["body"])
    except ValidationError as exc:
        return _redirect_with_error(request, post, exc.messages)

    if request.htmx:
        return render(
            request,
            "comments/_comment.html",
            {"comment": comment, "post": post, "thread_root": True},
        )
    return redirect(reverse("posts:detail", args=[post.pk]) + f"#c{comment.id}")


@login_required
@require_POST
def reply(request: HttpRequest, comment_pk: int) -> HttpResponse:
    """Reply to an existing comment (one-level nesting)."""
    parent = get_object_or_404(Comment, pk=comment_pk, is_deleted=False)
    post = parent.post
    form = CommentForm(request.POST)
    if not form.is_valid():
        return _redirect_with_error(request, post, form)

    try:
        comment = create_comment(
            author=request.user,
            post=post,
            body=form.cleaned_data["body"],
            parent=parent,
        )
    except ValidationError as exc:
        return _redirect_with_error(request, post, exc.messages)

    if request.htmx:
        return render(
            request,
            "comments/_comment.html",
            {"comment": comment, "post": post, "thread_root": False},
        )
    return redirect(reverse("posts:detail", args=[post.pk]) + f"#c{comment.id}")


@login_required
@require_POST
def delete(request: HttpRequest, comment_pk: int) -> HttpResponse:
    """Soft-delete one's own comment."""
    comment = get_object_or_404(Comment, pk=comment_pk, is_deleted=False)
    try:
        soft_delete_comment(comment=comment, requesting_user=request.user)
    except PermissionError:
        return HttpResponse(status=403)

    if request.htmx:
        # Return the deleted-state partial so the row visually marks
        # itself but stays in the thread (preserves parent/reply context).
        return render(request, "comments/_comment_deleted.html", {"comment": comment})
    return redirect(reverse("posts:detail", args=[comment.post_id]))


@require_GET
def permalink(request: HttpRequest, post_pk: int, comment_pk: int) -> HttpResponse:
    """Reddit-style single-comment view.

    Renders the post header plus exactly one comment (and its replies, if it
    is a top-level comment — with our one-level nesting, a reply has no
    descendants of its own). The comment ID is the page's focus; the parent
    thread can be reached via the "back to full thread" link.

    404s on missing post/comment, deleted post/comment, or mismatched
    (comment-belongs-to-different-post) requests.
    """
    post = get_object_or_404(Post, pk=post_pk, is_deleted=False)
    comment = get_object_or_404(
        Comment.objects.select_related("author").prefetch_related("replies__author"),
        pk=comment_pk,
        post=post,
        is_deleted=False,
    )
    return render(
        request,
        "comments/permalink.html",
        {"post": post, "comment": comment},
    )


def _redirect_with_error(request, post, form_or_errors):  # type: ignore[no-untyped-def]
    """Fallback re-render path when validation failed.

    Best-effort: send the user back to the detail page; the form re-renders
    empty. For MVP this is acceptable — the body length check is server-side
    but unlikely to fire because the textarea has maxlength=5000. The
    `form_or_errors` argument is reserved for future message-passing once
    Django's messages framework is wired into the layout.
    """
    del form_or_errors  # intentionally unused for now
    return redirect(reverse("posts:detail", args=[post.pk]))
