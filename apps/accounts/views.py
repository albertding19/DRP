"""Nickname picker.

The picker is the only view that runs *without* a user in session. It bypasses
`EnsureNicknameMiddleware` via the `EXEMPT_PREFIXES` list in core/middleware.
"""

from __future__ import annotations

from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import NicknamePickForm
from .models import User
from .services import NicknameTaken, create_user_with_nickname


@require_http_methods(["GET", "POST"])
def start(request: HttpRequest) -> HttpResponse:
    """Pick-a-nickname page.

    GET: render the form.
    POST: create the user, log them in, redirect to `?next=` or `/`.
    """
    # If already signed in, skip the picker.
    if request.session.get("user_id"):
        return redirect(request.GET.get("next") or "/")

    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST":
        form = NicknamePickForm(request.POST)
        if form.is_valid():
            try:
                user = create_user_with_nickname(form.cleaned_data["nickname"])
            except NicknameTaken:
                form.add_error("nickname", "That nickname's taken — try another.")
            else:
                request.session["user_id"] = user.id
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
                login(
                    request,
                    user,
                    backend="apps.accounts.backends.NicknameSessionBackend",
                )
                return redirect(next_url)
    else:
        form = NicknamePickForm()

    return render(request, "accounts/start.html", {"form": form, "next": next_url})


@require_http_methods(["POST"])
def check_nickname(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: inline uniqueness check while user types.

    POST { nickname }
    → HTML fragment, "available" or "taken".
    """
    nickname = (request.POST.get("nickname") or "").strip()
    if not nickname:
        return render(request, "accounts/_nickname_check.html", {"state": "empty"})

    state = "taken" if User.objects.filter(nickname=nickname).exists() else "available"
    return render(
        request,
        "accounts/_nickname_check.html",
        {"state": state, "nickname": nickname},
    )


@require_http_methods(["POST"])
def logout(request: HttpRequest) -> HttpResponse:
    """Clear session (= "switch nickname")."""
    request.session.flush()
    return redirect(reverse("accounts:start"))
