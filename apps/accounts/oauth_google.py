"""Google OAuth helpers — kept in a separate module from `services.py` so
the three external calls (authorize URL, exchange code, fetch userinfo)
are individually mockable in tests AND so we can swap in a different
provider's helpers later without touching the rest of accounts.

We deliberately do NOT use django-allauth. For ONE provider, allauth
brings in dozens of settings, migrations, templates, and URL prefixes
that we don't need. The total surface of these helpers is ~70 lines of
honest code calling well-documented Google endpoints.

Reference:
  https://developers.google.com/identity/protocols/oauth2/web-server
  https://accounts.google.com/.well-known/openid-configuration
"""

from __future__ import annotations

from urllib.parse import urlencode

import requests
from django.conf import settings

# Google OAuth 2.0 endpoints. Hardcoded — Google publishes them via the
# discovery document at https://accounts.google.com/.well-known/openid-configuration
# but a runtime fetch isn't worth the latency or the surface area.
_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Minimum scope set we need. `openid` enables the OIDC userinfo endpoint;
# `email` populates `email` + `email_verified`; `profile` populates `name`.
# Asking for more is a privacy red flag with no benefit.
_SCOPE = "openid email profile"

# Network timeout for outbound Google calls. Google's median response is
# <500 ms; we pad generously for cold-network blips but cap so a hung
# Google connection can't block the Daphne worker.
_REQUEST_TIMEOUT_S = 8


class OAuthError(Exception):
    """Wrap any non-2xx response from Google so callers handle one type."""


def authorize_url(*, state: str) -> str:
    """Build the consent-page URL the user is redirected to.

    The `state` parameter is CSRF-prevention: views/services.py generates
    it, stores it in `request.session["oauth_state"]`, and asserts a
    byte-for-byte match on the callback. Without this, an attacker could
    trick a logged-out user's browser into hitting our callback URL with
    an attacker-controlled `code`, signing the victim into the attacker's
    Google account.
    """
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "state": state,
        # `prompt=select_account` makes Google show the account picker
        # every time, even if the user is already signed in to one Google
        # account in this browser. UX win — avoids silently signing in
        # with the wrong account on shared devices.
        "prompt": "select_account",
        # `access_type=online` — we don't need a refresh token. Refresh
        # tokens are valuable to attackers; we just need one userinfo
        # call's worth of access.
        "access_type": "online",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(*, code: str) -> dict:
    """Trade the one-shot auth code from Google for an access token.

    POSTs to Google's token endpoint with our confidential-client
    credentials. The `redirect_uri` MUST match the one we used in
    `authorize_url` — Google verifies this server-side as a defense
    against authorization-code injection.

    Raises `OAuthError` on any non-2xx response.
    """
    resp = requests.post(
        _TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=_REQUEST_TIMEOUT_S,
    )
    if not resp.ok:
        raise OAuthError(f"Google token exchange failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()


def fetch_userinfo(*, access_token: str) -> dict:
    """Call Google's OIDC userinfo endpoint with the access token.

    The returned dict contains `sub`, `email`, `email_verified`, `name`,
    `picture`, etc. Callers MUST check `email_verified is True` before
    trusting `email` for account lookup. Without that check, an attacker
    with a Google account whose `email` happens to match a target user's
    address could hijack the target's account — a subtle but real attack
    vector (e.g. via Google Workspace re-assigned addresses).
    """
    resp = requests.get(
        _USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_REQUEST_TIMEOUT_S,
    )
    if not resp.ok:
        raise OAuthError(f"Google userinfo fetch failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()
