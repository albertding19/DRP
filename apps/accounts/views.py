"""Auth views — welcome page, magic link verify, Google OAuth callback,
claim flow, settings page, logout.

Every view that takes a user-controlled `?next=` runs it through
`services.validate_next_url` before passing it to `redirect()` — this is
the canonical open-redirector defense. Previous shapes of this file (and
its predecessor nickname picker at the same path) did NOT validate, so a
forwarded magic link could phish a user onto an attacker site. Don't
regress.
"""

from __future__ import annotations

import logging
import secrets

from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    ClaimEmailForm,
    EmailSignInForm,
    SettingsEmailForm,
    SettingsNicknameForm,
)
from .models import SignInToken, User
from .services import (
    EmailTakenError,
    OAuthError,
    RateLimitedError,
    SignInTokenExpiredError,
    SignInTokenInvalidError,
    claim_account_with_email,
    delete_account,
    google_oauth_authorize_url,
    google_oauth_complete,
    request_email_change,
    send_signin_link,
    validate_next_url,
    verify_signin_token,
)

logger = logging.getLogger(__name__)


def _client_ip(request: HttpRequest) -> str:
    """Best-effort client IP for rate-limit + logging.

    Honours `X-Forwarded-For` first (Render terminates SSL at an edge
    proxy that sets this), then falls back to `REMOTE_ADDR`. Only takes
    the first IP from XFF — the rest of the list could be attacker-
    controlled and we don't trust it.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _login_user(request: HttpRequest, user: User) -> None:
    """Set the session up after successful authentication. Mirrors the
    legacy nickname-picker flow at the same exact session-key shape so
    the test fixture (`client_with_session`) keeps working unchanged."""
    request.session["user_id"] = user.id
    request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
    login(request, user, backend="apps.accounts.backends.NicknameSessionBackend")


# ---------------------------------------------------------------------------
# Welcome page — unified email + Google sign-in front door
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def start(request: HttpRequest) -> HttpResponse:
    """The new welcome page.

    GET:
      - Already signed in → redirect to `?next=` (validated) or `/`.
      - Anonymous → render the email form + Google button.

    POST:
      - Validate email, send magic link, redirect to interstitial.
    """
    raw_next = request.GET.get("next") or request.POST.get("next") or "/"
    next_url = validate_next_url(raw_next, request=request)

    if request.session.get("user_id"):
        return redirect(next_url)

    if request.method == "POST":
        form = EmailSignInForm(request.POST)
        if form.is_valid():
            try:
                send_signin_link(
                    email=form.cleaned_data["email"],
                    intent=SignInToken.INTENT_LOGIN,
                    ip_address=_client_ip(request),
                    next_url=next_url,
                    request=request,
                )
            except RateLimitedError:
                form.add_error(
                    "email",
                    "Too many sign-in links requested. Wait an hour and try again.",
                )
            else:
                return redirect(
                    reverse("accounts:check_email") + f"?email={form.cleaned_data['email']}"
                )
    else:
        form = EmailSignInForm()

    google_enabled = bool(
        # Hide the button when no client ID is configured (dev without OAuth set up).
        request.GET.get("force_google") or _google_configured()
    )
    return render(
        request,
        "accounts/start.html",
        {
            "form": form,
            "next": next_url,
            "google_enabled": google_enabled,
        },
    )


def _google_configured() -> bool:
    from django.conf import settings

    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


@require_GET
def check_email(request: HttpRequest) -> HttpResponse:
    """Interstitial: 'We sent you a link to <email>.' Shown after a
    successful POST on the welcome page. Doesn't trust the email param
    for anything but display — no DB lookup."""
    return render(
        request,
        "accounts/check_email.html",
        {"email": (request.GET.get("email") or "").strip()},
    )


# ---------------------------------------------------------------------------
# Magic-link verify (anonymous can hit this — exempt prefix in middleware)
# ---------------------------------------------------------------------------
@require_GET
def verify(request: HttpRequest) -> HttpResponse:
    """Click handler for the magic link.

    Hashes the `?t=` parameter, looks up the token, redeems it, signs the
    user in, redirects to `?next=` (validated). Every failure mode renders
    a friendly page rather than a 500."""
    raw_token = (request.GET.get("t") or "").strip()
    next_url = validate_next_url(request.GET.get("next"), request=request)

    if not raw_token:
        return render(
            request,
            "accounts/verify_error.html",
            {"reason": "missing"},
            status=400,
        )

    try:
        user, _intent = verify_signin_token(
            raw_token,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
    except SignInTokenExpiredError:
        return render(request, "accounts/verify_error.html", {"reason": "expired"}, status=400)
    except SignInTokenInvalidError:
        return render(request, "accounts/verify_error.html", {"reason": "invalid"}, status=400)
    except EmailTakenError:
        return render(
            request,
            "accounts/verify_error.html",
            {"reason": "email_taken"},
            status=400,
        )

    _login_user(request, user)
    return redirect(next_url)


# ---------------------------------------------------------------------------
# Google OAuth — start + callback
# ---------------------------------------------------------------------------
@require_GET
def oauth_google_start(request: HttpRequest) -> HttpResponse:
    """Initiate the OAuth flow. Generates a CSRF state token, stores it
    in the session, redirects to Google's consent page.

    The `?next=` is validated NOW and stashed in the session — we
    deliberately don't round-trip it through Google. Without this,
    `?next=` becomes a phishable open redirector via OAuth state."""
    if not _google_configured():
        return HttpResponseBadRequest("Google sign-in is not configured.")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["oauth_next"] = validate_next_url(request.GET.get("next"), request=request)
    return redirect(google_oauth_authorize_url(state=state))


@require_GET
def oauth_google_callback(request: HttpRequest) -> HttpResponse:
    """Google bounces here with `?code=` and `?state=`. Verify state,
    exchange code for userinfo, find/create the user, sign them in."""
    expected_state = request.session.pop("oauth_state", None)
    next_url = request.session.pop("oauth_next", "/")
    received_state = request.GET.get("state")
    if not expected_state or not received_state or expected_state != received_state:
        return HttpResponseBadRequest("Invalid OAuth state.")

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing OAuth code.")

    try:
        user, _created = google_oauth_complete(code=code, ip_address=_client_ip(request))
    except OAuthError as exc:
        return render(request, "accounts/oauth_error.html", {"reason": str(exc)}, status=400)

    _login_user(request, user)
    return redirect(next_url)


# ---------------------------------------------------------------------------
# Claim flow (existing nickname-only users add an email)
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def claim(request: HttpRequest) -> HttpResponse:
    """Authed user adds an email to their account."""
    if not request.session.get("user_id"):
        return redirect(reverse("accounts:start"))
    if getattr(request.user, "email", None):
        return redirect(reverse("accounts:settings"))

    if request.method == "POST":
        form = ClaimEmailForm(request.POST)
        if form.is_valid():
            try:
                claim_account_with_email(
                    user=request.user,
                    email=form.cleaned_data["email"],
                    ip_address=_client_ip(request),
                    request=request,
                )
            except EmailTakenError:
                form.add_error("email", "That email's already in use.")
            except RateLimitedError:
                form.add_error(
                    "email",
                    "Too many requests. Wait an hour and try again.",
                )
            else:
                return redirect(
                    reverse("accounts:check_email") + f"?email={form.cleaned_data['email']}"
                )
    else:
        form = ClaimEmailForm()
    return render(request, "accounts/claim.html", {"form": form})


# ---------------------------------------------------------------------------
# Settings page — profile / email / nickname / delete
# ---------------------------------------------------------------------------
@require_GET
def settings_page(request: HttpRequest) -> HttpResponse:
    """The settings landing. Renders the current nickname + email + the
    forms for editing each + the delete-account button."""
    return render(
        request,
        "accounts/settings.html",
        {
            "nickname_form": SettingsNicknameForm(
                initial={"nickname": request.user.nickname},
                current_user=request.user,
            ),
            "email_form": SettingsEmailForm(
                initial={"email": request.user.email or ""},
                current_user=request.user,
            ),
        },
    )


@require_POST
def settings_nickname(request: HttpRequest) -> HttpResponse:
    """Change-nickname POST. Immediate (no email verification)."""
    form = SettingsNicknameForm(request.POST, current_user=request.user)
    if form.is_valid():
        request.user.nickname = form.cleaned_data["nickname"]
        request.user.save(update_fields=["nickname"])
        return redirect(reverse("accounts:settings"))
    return render(
        request,
        "accounts/settings.html",
        {
            "nickname_form": form,
            "email_form": SettingsEmailForm(
                initial={"email": request.user.email or ""},
                current_user=request.user,
            ),
        },
    )


@require_POST
def settings_email(request: HttpRequest) -> HttpResponse:
    """Change-email POST. Sends verification to the NEW address; nothing
    changes on the user until they click the link."""
    form = SettingsEmailForm(request.POST, current_user=request.user)
    if form.is_valid():
        try:
            request_email_change(
                user=request.user,
                new_email=form.cleaned_data["email"],
                ip_address=_client_ip(request),
                request=request,
            )
        except RateLimitedError:
            form.add_error("email", "Too many requests. Wait an hour and try again.")
        except EmailTakenError:
            form.add_error("email", "That email's already in use.")
        else:
            return redirect(
                reverse("accounts:check_email") + f"?email={form.cleaned_data['email']}"
            )
    return render(
        request,
        "accounts/settings.html",
        {
            "nickname_form": SettingsNicknameForm(
                initial={"nickname": request.user.nickname},
                current_user=request.user,
            ),
            "email_form": form,
        },
    )


@require_POST
def settings_delete(request: HttpRequest) -> HttpResponse:
    """Hard-delete the user + flush session. Cascades + SET_NULLs per
    model FK rules: content survives as [deleted], personal data is wiped."""
    delete_account(user=request.user)
    request.session.flush()
    return redirect(reverse("accounts:start"))


# ---------------------------------------------------------------------------
# HTMX uniqueness checks
# ---------------------------------------------------------------------------
@require_POST
def check_nickname(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: inline uniqueness check while user types."""
    nickname = (request.POST.get("nickname") or "").strip()
    current_user_id = request.session.get("user_id")
    if not nickname:
        return render(request, "accounts/_nickname_check.html", {"state": "empty"})
    qs = User.objects.filter(nickname=nickname)
    if current_user_id:
        qs = qs.exclude(pk=current_user_id)
    state = "taken" if qs.exists() else "available"
    return render(
        request,
        "accounts/_nickname_check.html",
        {"state": state, "nickname": nickname},
    )


@require_POST
def check_email_availability(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: email availability for the claim + settings flows."""
    email = (request.POST.get("email") or "").strip().lower()
    current_user_id = request.session.get("user_id")
    if not email:
        return render(request, "accounts/_email_check.html", {"state": "empty"})
    qs = User.objects.filter(email=email)
    if current_user_id:
        qs = qs.exclude(pk=current_user_id)
    state = "taken" if qs.exists() else "available"
    return render(
        request,
        "accounts/_email_check.html",
        {"state": state, "email": email},
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    """Clear session and bounce back to welcome."""
    request.session.flush()
    return redirect(reverse("accounts:start"))
