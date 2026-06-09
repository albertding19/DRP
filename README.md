# DRP — Reddit-style ADHD peer-support app

A peer-support webapp for adults newly referred or diagnosed with ADHD.
Built for Imperial College London × Royal College of Art's *Designing for
Real People* (DRP 2026).

[![CI](https://github.com/albertding19/DRP/actions/workflows/ci.yml/badge.svg)](https://github.com/albertding19/DRP/actions/workflows/ci.yml)

**Live:** https://drp-web.onrender.com *(once Render deploys; see `render.yaml`)*

Browse a feed of problems / coping strategies, share your own, upvote,
comment. All actions land in real time — votes and comments push to other
viewers via WebSocket. Pick a nickname to enter; no email or password.

## Quickstart

Prerequisites: Python 3.12, Docker.

```bash
# 1. Start Postgres + Redis
docker compose up -d postgres redis

# 2. Venv + deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Env
cp .env.example .env

# 4. Migrate + run
python manage.py migrate
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Visit `http://127.0.0.1:8000/` — you'll be redirected to pick a nickname.

## Tests + lint

```bash
pytest                  # all tests
ruff check .            # lint
ruff format .           # format
```

CI runs all three on every push and PR to `main`.

## CI / CD

| Step | Where |
|---|---|
| **CI** | GitHub Actions: ruff + pytest + migrate-check + ASGI-load + collectstatic |
| **CD** | Render auto-deploy on merge to `main` (see `render.yaml`) |
| **Public URL** | `https://drp-web.onrender.com` |
| **CD evidence** | `/version` returns the deployed commit SHA |

Render's free tier sleeps after ~15 min idle. For the M2 demo, ping
`/healthz` from [UptimeRobot](https://uptimerobot.com) 30 min before the
slot to wake the dyno.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the one-page diagram
and module ownership table.

Full implementation plan: `/Users/albertding/.claude/plans/we-are-making-a-nested-dawn.md`

## Project structure

```
config/                 # Django project (settings, urls, asgi)
apps/
  core/                 # base templates, healthz, version, middleware
  accounts/             # custom User, nickname picker
  posts/                # Post model + feed              (Wed 27 May)
  comments/             # threaded comments              (Mon 1 Jun)
  votes/                # generic Vote + cast service    (Wed 27 May)
  tags/                 # Tag model + tag pages          (M3, 1 Jun)
  search/               # PG full-text search            (M3, 1 Jun)
  realtime/             # Channels consumers + broadcast (Thu 28 May)
static/                 # css, htmx, alpine, realtime.js
templates/              # base.html
.github/workflows/      # CI
render.yaml             # CD blueprint
```

## Milestones

| Date | Milestone | Weight |
|---|---|---|
| Thu 22 May | M1 — Elevator pitch | 5% |
| **Fri 29 May** | **M2 — Concept Development** | **5%** |
| Mon 2 Jun | Law TRA | 10% |
| Fri 5 Jun | M3 — Iterative Development | 5% |
| Fri 12 Jun | M4 — More Iterative Development | 5% |
| 16–17 Jun | Final Demo + Presentation | 50% |
| Thu 19 Jun | Project Documentation | 20% |

## Auth — prerequisites before email + Google sign-in work in prod

The login service ships using **Resend SMTP** for magic-link emails and
**Google OAuth** for one-click sign-in. Both need to be configured outside
the repo before they work on Render. The code degrades gracefully when
they're missing (the welcome page hides the Google button, and email
sends fail with a user-visible error) but for production you need:

1. **Resend account + verified domain.**
   - Sign up at https://resend.com
   - Add and verify a sending domain (SPF + DKIM DNS records). Without
     verification, magic-link emails land in spam or get bounced.
   - **Demo shortcut:** leave `DEFAULT_FROM_EMAIL` at the default
     `unmasked <onboarding@resend.dev>` — Resend allows this shared
     sender for early projects but deliverability is degraded.
   - Generate an API key, set it in Render as `RESEND_API_KEY`.
2. **Google OAuth client.**
   - Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
     → Web application.
   - Authorised redirect URIs (must match exactly):
     - `http://localhost:8000/accounts/oauth/google/callback/` (dev)
     - `https://drp-web-5xwh.onrender.com/accounts/oauth/google/callback/` (prod)
   - While the OAuth consent screen is in dev mode, add yourself + any
     testers under "Test users".
   - Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in
     Render. `GOOGLE_OAUTH_REDIRECT_URI` defaults to the prod URL above
     and can be left as-is.

## Acknowledgements

DRP module: Imperial DoC × Royal College of Art Service Design.
Research interviews with adults with ADHD + NHS practitioners conducted
20 May 2026 (full notes in `interviews/`).
