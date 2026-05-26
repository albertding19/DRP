"""Post search.

For M2/M3 we use plain `icontains` over title + body. It's portable across
SQLite (local dev) and PostgreSQL (CI + prod), and good enough for a
demo-scale corpus. M4 will upgrade to PostgreSQL `SearchVectorField` with
GIN indexing — that's a single migration + signal handler away.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.posts.models import Post


def search_posts(q: str) -> QuerySet[Post]:
    """Case-insensitive search over title + body. Returns a Post queryset."""
    query = (q or "").strip()
    if not query:
        return Post.objects.none()

    return (
        Post.objects.select_related("author")
        .prefetch_related("tags")
        .filter(is_deleted=False)
        .filter(Q(title__icontains=query) | Q(body__icontains=query))
        .order_by("-created_at")
        .distinct()
    )
