"""Search view — renders the feed template with search results."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services import search_posts


@require_http_methods(["GET"])
def search(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = search_posts(q) if q else None
    page = Paginator(qs, per_page=25).get_page(request.GET.get("page", 1)) if qs else None
    return render(
        request,
        "search/results.html",
        {
            "q": q,
            "page": page,
            "posts": page.object_list if page else [],
            "sort": "new",
        },
    )
