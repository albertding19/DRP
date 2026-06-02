"""Communities services.

Five service functions, all callable from views, admin, or tests:

  create_community(*, creator, name, category, description="") -> Community
  join_community(*, user, community) -> CommunityMembership
  leave_community(*, user, community) -> int
  user_communities(user) -> QuerySet[Community]
  communities_for_category(category) -> QuerySet[Community]

The denormalised `Community.member_count` is maintained by signals in
`apps/communities/signals.py` — the services don't touch it directly so
that bulk admin operations stay consistent.
"""

from __future__ import annotations

from secrets import token_hex

from django.db import transaction
from django.db.models import QuerySet
from django.utils.text import slugify

from .models import Community, CommunityMembership


class CommunityNameTakenError(Exception):
    """Raised when the slugified name collides with an existing community
    AND the caller doesn't want auto-suffixing."""


def _unique_slug(name: str) -> str:
    """Slugify `name`; if the slug is already taken, append a short random
    suffix until we find a free one. Caps retry count to avoid infinite
    loops on pathological inputs."""
    base = slugify(name)[:128] or "community"
    if not Community.objects.filter(slug=base).exists():
        return base
    for _ in range(10):
        candidate = f"{base}-{token_hex(2)}"
        if not Community.objects.filter(slug=candidate).exists():
            return candidate
    # Extremely unlikely; surface as the collision error.
    raise CommunityNameTakenError(f"Could not find a free slug after 10 retries for name={name!r}")


@transaction.atomic
def create_community(
    *,
    creator,  # type: ignore[no-untyped-def]
    name: str,
    category: str,
    description: str = "",
) -> Community:
    """Create a new community. Auto-slugifies; collision-suffixes if needed.

    The creator is also auto-joined as the first member.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Community name can't be empty.")
    if category not in dict(Community.CATEGORY_CHOICES):
        raise ValueError(f"Unknown category: {category!r}")

    slug = _unique_slug(name)
    community = Community.objects.create(
        name=name,
        slug=slug,
        category=category,
        description=description.strip(),
        creator=creator if getattr(creator, "is_authenticated", False) else None,
    )
    # Creator becomes the first member.
    if getattr(creator, "is_authenticated", False):
        join_community(user=creator, community=community)
    return community


@transaction.atomic
def join_community(*, user, community: Community) -> CommunityMembership:  # type: ignore[no-untyped-def]
    """Idempotent: returns existing membership if user is already in."""
    membership, _ = CommunityMembership.objects.get_or_create(user=user, community=community)
    return membership


@transaction.atomic
def leave_community(*, user, community: Community) -> int:  # type: ignore[no-untyped-def]
    """Returns number of memberships deleted (0 or 1)."""
    deleted, _ = CommunityMembership.objects.filter(user=user, community=community).delete()
    return deleted


def user_communities(user) -> QuerySet[Community]:  # type: ignore[no-untyped-def]
    """All communities `user` is a member of, most-recently joined first.

    Anonymous users get an empty queryset (the call shouldn't crash on
    middleware paths that hit this with AnonymousUser)."""
    if not getattr(user, "is_authenticated", False):
        return Community.objects.none()
    return Community.objects.filter(memberships__user=user).order_by("-memberships__created_at")


def communities_for_category(category: str) -> QuerySet[Community]:
    """All communities in the given category, ordered by popularity."""
    return Community.objects.filter(category=category).order_by("-member_count", "name")
