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
from apps.realtime import broadcast

from .forms import CommentForm
from .models import Comment
from .services import create_comment, report_comment, soft_delete_comment


@login_required
@require_POST
def create(request: HttpRequest, post_pk: int) -> HttpResponse:
    """Create a top-level comment on a post."""
    post = get_object_or_404(Post, pk=post_pk, is_deleted=False)
    form = CommentForm(request.POST, author=request.user)
    if not form.is_valid():
        return _render_create_error(request, post, form)

    try:
        comment = create_comment(author=request.user, post=post, body=form.cleaned_data["body"])
    except ValidationError as exc:
        form.add_error("body", exc)
        return _render_create_error(request, post, form)

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
    form = CommentForm(request.POST, author=request.user)
    if not form.is_valid():
        return _render_reply_error(request, parent, form)

    try:
        comment = create_comment(
            author=request.user,
            post=post,
            body=form.cleaned_data["body"],
            parent=parent,
        )
    except ValidationError as exc:
        form.add_error("body", exc)
        return _render_reply_error(request, parent, form)

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


@login_required
@require_POST
def report(request: HttpRequest, comment_pk: int) -> HttpResponse:
    """Record a user's report against a comment. Idempotent per user/comment.

    HTMX: returns a small `_reported.html` partial that replaces the Report
    button with a "Thanks — we've recorded your report" confirmation.
    Non-HTMX: redirects to the post detail page.

    If the report pushes the count over the threshold, broadcasts a WS
    `comment_hidden` event so live viewers' UI removes the node without a
    refresh.
    """
    comment = get_object_or_404(
        Comment.objects.select_related("post"),
        pk=comment_pk,
        is_deleted=False,
        is_hidden=False,
    )
    _, just_hidden = report_comment(comment=comment, reporter=request.user)

    if just_hidden:
        broadcast.broadcast_comment_hidden(comment)

    if request.htmx:
        return render(
            request,
            "comments/_reported.html",
            {"comment": comment},
        )
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
        is_hidden=False,
    )
    return render(
        request,
        "comments/permalink.html",
        {"post": post, "comment": comment},
    )


def _render_create_error(request: HttpRequest, post: Post, form: CommentForm) -> HttpResponse:
    """Re-render the new-comment form with validation errors visible.

    HTMX path: returns just the `_comment_form.html` partial and overrides
    the swap target via `HX-Retarget` / `HX-Reswap` so the form replaces
    itself in-place (preserving the user's typed input) instead of being
    inserted at the top of #thread.

    Non-HTMX path: returns the full post-detail page with the form's errors
    populated so the user sees what went wrong.
    """
    if request.htmx:
        response = render(
            request,
            "comments/_comment_form.html",
            {"form": form, "post": post},
        )
        response["HX-Retarget"] = f"#comment-form-{post.id}"
        response["HX-Reswap"] = "outerHTML"
        return response
    return render(
        request,
        "posts/detail.html",
        {"post": post, "comment_form": form},
    )


def _render_reply_error(request: HttpRequest, parent: Comment, form: CommentForm) -> HttpResponse:
    """Re-render the reply form with validation errors visible.

    Same HX-Retarget / HX-Reswap pattern as `_render_create_error`, but
    targeting the per-comment reply form by id.
    """
    if request.htmx:
        response = render(
            request,
            "comments/_reply_form.html",
            {"form": form, "comment": parent},
        )
        response["HX-Retarget"] = f"#reply-form-{parent.id}"
        response["HX-Reswap"] = "outerHTML"
        return response
    return render(
        request,
        "posts/detail.html",
        {"post": parent.post, "reply_form": form, "reply_parent": parent},
    )
