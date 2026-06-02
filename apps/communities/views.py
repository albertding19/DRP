"""Communities views — browse, detail, create, join, leave."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Community, CommunityMembership
from .services import create_community, join_community, leave_community


@login_required
@require_GET
def list_view(request: HttpRequest) -> HttpResponse:
    """Browse all communities. Optional `?category=<cat>` and `?q=<text>`."""
    qs = Community.objects.all().order_by("-member_count", "name")

    category = request.GET.get("category", "").strip()
    if category and category in dict(Community.CATEGORY_CHOICES):
        qs = qs.filter(category=category)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)

    page = Paginator(qs, per_page=24).get_page(request.GET.get("page", 1))
    # Surface which communities the current user is already a member of, so
    # the card template can render Join vs Leave without an N+1.
    member_ids = set(
        CommunityMembership.objects.filter(user=request.user).values_list("community_id", flat=True)
    )
    return render(
        request,
        "communities/list.html",
        {
            "page": page,
            "communities": page.object_list,
            "category": category,
            "categories": Community.CATEGORY_CHOICES,
            "q": q,
            "member_ids": member_ids,
        },
    )


@login_required
@require_GET
def detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Single community page: info, member list, body-double CTA."""
    community = get_object_or_404(Community, slug=slug)
    is_member = CommunityMembership.objects.filter(user=request.user, community=community).exists()
    # Member list — paginated, most-recent-joined first.
    members_qs = (
        CommunityMembership.objects.filter(community=community)
        .select_related("user")
        .order_by("-created_at")
    )
    members_page = Paginator(members_qs, per_page=30).get_page(request.GET.get("page", 1))
    return render(
        request,
        "communities/detail.html",
        {
            "community": community,
            "is_member": is_member,
            "members_page": members_page,
            "members": members_page.object_list,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_view(request: HttpRequest) -> HttpResponse:
    """Create a new community. Anyone (logged-in) can do this."""
    errors: dict[str, str] = {}
    initial = {"name": "", "category": "", "description": ""}

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        category = (request.POST.get("category") or "").strip()
        description = (request.POST.get("description") or "").strip()
        initial = {"name": name, "category": category, "description": description}

        if not name:
            errors["name"] = "Give your community a name."
        if category not in dict(Community.CATEGORY_CHOICES):
            errors["category"] = "Pick one of the available categories."

        if not errors:
            community = create_community(
                creator=request.user,
                name=name,
                category=category,
                description=description,
            )
            return redirect(reverse("communities:detail", args=[community.slug]))

    return render(
        request,
        "communities/create.html",
        {
            "errors": errors,
            "initial": initial,
            "categories": Community.CATEGORY_CHOICES,
        },
    )


@login_required
@require_POST
def join(request: HttpRequest, slug: str) -> HttpResponse:
    community = get_object_or_404(Community, slug=slug)
    join_community(user=request.user, community=community)
    return redirect("communities:detail", slug=slug)


@login_required
@require_POST
def leave(request: HttpRequest, slug: str) -> HttpResponse:
    community = get_object_or_404(Community, slug=slug)
    leave_community(user=request.user, community=community)
    return redirect("communities:detail", slug=slug)
