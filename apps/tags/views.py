"""Tag views.

`/tags/` — list all tags (popular first)
`/tags/<slug>/` — feed filtered to posts with this tag
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.posts.services import feed_queryset

from .models import Tag


@require_http_methods(["GET"])
def tag_list(request: HttpRequest) -> HttpResponse:
    tags = Tag.objects.filter(post_count__gt=0)
    return render(request, "tags/list.html", {"tags": tags})


@require_http_methods(["GET"])
def tag_detail(request: HttpRequest, slug: str) -> HttpResponse:
    tag = get_object_or_404(Tag, slug=slug)
    sort = request.GET.get("sort", "new")
    qs = feed_queryset(sort=sort).filter(tags=tag)
    page = Paginator(qs, per_page=25).get_page(request.GET.get("page", 1))
    # Reuse the feed template — pass a "filtered_tag" so it can show context.
    return render(
        request,
        "posts/feed.html",
        {
            "page": page,
            "posts": page.object_list,
            "sort": sort,
            "filtered_tag": tag,
        },
    )
