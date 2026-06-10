"""Tests for project middleware."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User


@pytest.mark.django_db
class TestNoCacheHTMLMiddleware:
    """HTML responses must carry no-store cache headers.

    JSON ops endpoints (healthz, version) are still text/json so they are
    correctly excluded — only HTML is targeted.
    """

    def test_picker_html_has_no_store(self) -> None:
        response = Client().get("/accounts/start/")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/html")
        assert "no-store" in response["Cache-Control"]
        assert response["Pragma"] == "no-cache"

    def test_healthz_json_is_not_marked(self) -> None:
        """JSON responses don't need the no-store header (and we don't set it)."""
        response = Client().get("/healthz")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")
        # Either no Cache-Control header at all, or one we didn't set
        cache_control = response.get("Cache-Control", "")
        assert "no-store" not in cache_control or response.get("Pragma") != "no-cache"

    def test_redirect_html_response_still_has_header(self) -> None:
        """The 302 from middleware to /accounts/start/ is still text/html."""
        # Root path -> EnsureNicknameMiddleware redirects to picker
        response = Client().get("/")
        assert response.status_code == 302
        # 302 responses still have Content-Type: text/html by default
        if response.get("Content-Type", "").startswith("text/html"):
            assert "no-store" in response.get("Cache-Control", "")

    def test_post_create_anon_user_then_html_still_no_store(self) -> None:
        User.objects.create_anonymous(nickname="cacheuser")
        client = Client()
        session = client.session
        session["user_id"] = User.objects.get(nickname="cacheuser").id
        session.save()
        response = client.get("/accounts/start/")
        assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
class TestCanonicalHostMiddleware:
    """Requests on non-canonical hostnames must 301 to CANONICAL_HOST
    (path + query preserved); health endpoints stay exempt so Render's
    internal checks keep getting 200s. Unset (dev/test) = no-op."""

    def test_redirects_to_canonical_host(self, settings) -> None:
        settings.CANONICAL_HOST = "canonical.example"
        r = Client().get("/accounts/start/", HTTP_HOST="other.example")
        assert r.status_code == 301
        assert r["Location"] == "https://canonical.example/accounts/start/"

    def test_preserves_path_and_query(self, settings) -> None:
        settings.CANONICAL_HOST = "canonical.example"
        r = Client().get("/accounts/start/?next=/feed/", HTTP_HOST="other.example")
        assert r["Location"] == "https://canonical.example/accounts/start/?next=/feed/"

    def test_canonical_host_passes_through(self, settings) -> None:
        settings.CANONICAL_HOST = "canonical.example"
        r = Client().get("/accounts/start/", HTTP_HOST="canonical.example")
        assert r.status_code == 200

    def test_health_endpoints_exempt(self, settings) -> None:
        settings.CANONICAL_HOST = "canonical.example"
        assert Client().get("/healthz", HTTP_HOST="other.example").status_code == 200
        assert Client().get("/version", HTTP_HOST="other.example").status_code == 200

    def test_disabled_when_unset(self) -> None:
        # CANONICAL_HOST defaults to "" outside prod — any host works.
        assert Client().get("/accounts/start/", HTTP_HOST="whatever.example").status_code == 200
