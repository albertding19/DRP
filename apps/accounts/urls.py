"""URL routes for the auth app.

Anonymous-accessible routes are exempt from `EnsureAuthMiddleware` via
`EXEMPT_PREFIXES` in `apps/core/middleware.py`. Keep the exempt prefix
list in sync with this routing — any path the user must reach BEFORE
authentication needs to live under one of those prefixes.
"""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Anonymous-accessible:
    path("start/", views.start, name="start"),
    path("check-email/", views.check_email, name="check_email"),
    path("check-email/poll/", views.check_email_poll, name="check_email_poll"),
    path(
        "check-email/available/",
        views.check_email_availability,
        name="check_email_available",
    ),
    path("check-nickname/", views.check_nickname, name="check_nickname"),
    path("verify/", views.verify, name="verify"),
    path("oauth/google/start/", views.oauth_google_start, name="oauth_google_start"),
    path(
        "oauth/google/callback/",
        views.oauth_google_callback,
        name="oauth_google_callback",
    ),
    # Authed-only:
    path("claim/", views.claim, name="claim"),
    path("friends/", views.friends, name="friends"),
    path("settings/", views.settings_page, name="settings"),
    path("settings/nickname/", views.settings_nickname, name="settings_nickname"),
    path("settings/email/", views.settings_email, name="settings_email"),
    path("settings/delete/", views.settings_delete, name="settings_delete"),
    path("logout/", views.logout, name="logout"),
]
