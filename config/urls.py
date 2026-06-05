"""Root URL configuration.

Each app owns its own `urls.py` which is included here. App URL prefixes:

- `/`                       → personal dashboard (apps.core.views.home)
- `/feed/`                  → posts feed
- `/posts/...`              → post create/detail/edit
- `/comments/...`           → comment create/delete
- `/vote/...`               → voting endpoints
- `/accounts/start/`        → nickname picker (no auth required)
- `/tags/...`               → tag pages (M3)
- `/search/`                → full-text search (M3)
- `/healthz`, `/version`    → ops endpoints (no auth)
- `/admin/`                 → Django admin

Apps that are stubs (tags, search, comments, votes, realtime) include empty
url modules so the import graph is stable from day one.
"""

from django.contrib import admin
from django.urls import include, path

from apps.core.views import healthz, home, version

urlpatterns = [
    # ---- ops ----
    path("healthz", healthz, name="healthz"),
    path("version", version, name="version"),
    # ---- auth ----
    path("accounts/", include("apps.accounts.urls")),
    # ---- homepage (must come BEFORE the empty-prefix includes below) ----
    path("", home, name="home"),
    # ---- features ----
    path("", include("apps.posts.urls")),
    path("", include("apps.comments.urls")),
    path("", include("apps.votes.urls")),
    path("tags/", include("apps.tags.urls")),
    path("search/", include("apps.search.urls")),
    path("body-double/", include("apps.body_double.urls")),
    path("communities/", include("apps.communities.urls")),
    path("tasks/", include("apps.tasks.urls")),
    # ---- admin ----
    path("admin/", admin.site.urls),
]
