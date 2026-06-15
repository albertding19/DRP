# unmasked — *The Right Match*

**An ADHD focus & connection app: work alongside a real person (body-doubling), plan your day automatically, and find peer support.**

Built for Imperial College London × Royal College of Art's *Designing for Real People* (DRP 2026).

[![CI](https://github.com/albertding19/DRP/actions/workflows/ci.yml/badge.svg)](https://github.com/albertding19/DRP/actions/workflows/ci.yml)

**Live:** https://drp-web-5xwh.onrender.com *(Render free tier — see [Deployment](#deployment); custom domain `drp.it.com` once DNS + cert are live)*

---

## What it is

People with ADHD often know *what* to do but struggle to start and stay on task alone. **unmasked** tackles that with three connected ideas:

- **🤝 Body double** — get matched with another user (or a friend) and work alongside them over live video. Our server only mints a short-lived room token; the browser streams directly to LiveKit Cloud, and your call identity is just your nickname.
- **📅 A day that plans itself** — drop tasks into a To-do list, block off the times you're busy, then hit **Schedule my day** and the planner lays everything onto a timetable around your commitments (UK time).
- **💬 Peer support** — a calm, moderated feed of problems and coping strategies, plus topic communities and a friends list.

Everything is **real-time and multi-user**: votes, comments, new posts and match events push to other viewers over WebSocket. Sign-in is **passwordless** — pick a nickname to start; claim your account later with a magic link or Google.

### Feature map (left-sidebar nav)

| Section | What it does |
|---|---|
| **Home** | Personal dashboard — today's plan, body-double status, your communities, feed pulse |
| **Tasks** | To-do backlog → "Schedule my day" → auto-planned timetable; busy blocks & breaks |
| **Body double** | Find a focus partner now or schedule one; live LiveKit video room |
| **Friends** | Add/manage friends; body-double with people you know |
| **Communities** | Browse / create topic communities |
| **Feed** | Forum of posts, threaded comments, upvotes, tags, full-text search |

---

## Tech stack

A **server-rendered hypermedia app** — no SPA, no JS build step.

- **Backend:** Python · Django 5.1 · Django Channels, served by **Daphne** (one ASGI process for HTTP **and** WebSocket)
- **Frontend:** Django Templates + **HTMX** (server-rendered HTML fragments) + **Alpine.js** (light client state); ~25 KB of progressive enhancement
- **Data:** **PostgreSQL** (system of record, via the Django ORM) · **Redis** (Channels channel layer — the real-time pub/sub bus)
- **External services:** **LiveKit** (WebRTC video) · **Anthropic Claude** (Haiku — L2 content moderation) · **Resend** (magic-link email) · **Google OAuth**
- **Ops:** **Render** (web + managed Postgres + Redis from `render.yaml`) · **GitHub Actions** CI · Docker Compose for local DB/cache only

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the diagram and module map, and [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) for the *why* behind each choice.

---

## Quickstart

**Prerequisites:** Python 3.12+ and Docker.

```bash
# 1. Start Postgres + Redis (the app itself runs on the host)
docker compose up -d postgres redis

# 2. Virtualenv + dependencies
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Environment
cp .env.example .env

# 4. Migrate + run (Daphne serves HTTP + WebSocket)
python manage.py migrate
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Open **http://127.0.0.1:8000/** — you'll be redirected to pick a nickname, then land on your dashboard.

> The app runs natively on the host (not in a container) so `manage.py` and IDE debuggers work without indirection. Docker Compose only provides Postgres + Redis.

---

## Tests & lint

```bash
pytest                  # full suite (Postgres-backed; uses config.settings.test)
ruff check .            # lint
ruff format .           # format
```

- Tests live in each app's `tests/` package and run under `config.settings.test` (in-memory channel layer, no network — the Claude judge is auto-stubbed; opt into live API tests with `-m live`).
- Coverage: `pytest --cov=apps --cov=config` (CI gates at ≥40%).

---

## Configuration

Settings are environment-driven via `django-environ`, split by target:
`config/settings/{base,dev,test,prod}.py` (select with `DJANGO_SETTINGS_MODULE`).

Key variables (see `.env.example` and `render.yaml`):

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django core |
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Channels channel layer |
| `ANTHROPIC_API_KEY` | Claude (Haiku) L2 moderation — **fails open** if unset |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `LIVEKIT_URL` | Body-double video |
| `RESEND_API_KEY` / `DEFAULT_FROM_EMAIL` | Magic-link email |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` / `_REDIRECT_URI` | Google sign-in |
| `TASKS_WORK_START_HOUR` / `TASKS_WORK_END_HOUR` / `TASKS_BREAK_MINUTES` | Day-planner window & breaks |

The app **degrades gracefully** when optional services are missing: moderation falls open, the Google button hides, and video features are unavailable rather than crashing.

---

## Deployment

One file provisions everything on **Render**: [`render.yaml`](render.yaml) declares a web service (Daphne), managed Postgres, and Redis (Frankfurt region).

- **CD:** merge to `main` → Render auto-deploys (build runs `collectstatic` + `migrate`).
- **Health:** `/healthz` (JSON liveness) · `/version` (deployed commit SHA — CD evidence).
- **Free-tier caveat:** the web service sleeps after ~15 min idle (~30 s cold start). Before a demo, ping `/healthz` from [UptimeRobot](https://uptimerobot.com) ~30 min ahead. Postgres free tier expires after 90 days.
- Secrets marked `sync: false` in `render.yaml` (Anthropic / LiveKit / Resend / Google) are set in the Render dashboard, not committed.

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`:
`ruff check` → `ruff format --check` → **ASGI loads** → `makemigrations --check` → `pytest --cov` → `collectstatic` smoke.

---

## Project structure

```
config/                 # Django project: settings/{base,dev,test,prod}, urls, asgi
apps/
  core/                 # dashboard home, base templates, /healthz, /version, middleware
  accounts/             # custom User (nickname), passwordless auth + Google OAuth, friends
  tasks/                # To-do backlog + auto-planned timetable, busy blocks, breaks
  body_double/          # matchmaking + scheduled bookings + LiveKit video rooms
  posts/                # forum feed + posts
  comments/             # threaded comments
  votes/                # generic upvotes
  tags/                 # tags / category pages
  search/               # PostgreSQL full-text search
  communities/          # topic communities + membership
  moderation/           # 2-layer filter: L1 keyword + L2 Claude (fail-open)
  realtime/             # Channels consumers + broadcast (WebSocket fan-out)
static/                 # site.css, htmx, alpine, realtime.js, icons
templates/              # base.html (olive header + sidebar shell)
scripts/                # architecture-diagram generators (python-pptx, icon pipeline)
docs/                   # ARCHITECTURE.md, ARCHITECTURE_DECISIONS.md, diagrams
.github/workflows/      # CI
docker-compose.yml      # local Postgres + Redis
render.yaml             # Render blueprint (web + Postgres + Redis)
```

**Swappable seams** (set via `config/settings`): the body-double **matching strategy**
(default `TimetableAwareStrategy`) and the **video provider** (`LiveKitProvider`) are both
behind interfaces, so they can be changed without touching call sites.

---

## External services — production setup

The login and video features need credentials configured outside the repo. The code degrades gracefully without them, but for a real deployment:

1. **Resend (magic-link email).** Create an account, **verify a sending domain** (SPF + DKIM), generate an API key → set `RESEND_API_KEY` on Render. `DEFAULT_FROM_EMAIL` must use the verified domain — the `onboarding@resend.dev` sandbox sender only delivers to the account owner's own address.
2. **Google OAuth.** Cloud Console → Credentials → OAuth 2.0 Client ID (Web). Authorised redirect URIs must match exactly:
   - `http://localhost:8000/accounts/oauth/google/callback/` (dev)
   - `https://drp-web-5xwh.onrender.com/accounts/oauth/google/callback/` (prod)

   While the consent screen is in dev mode, add testers under "Test users". Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.
3. **LiveKit Cloud (body-double video).** Create a project, then set `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and `LIVEKIT_URL`. The server only mints room-scoped JWTs; media never passes through the backend.
4. **Anthropic (content moderation).** Set `ANTHROPIC_API_KEY` to enable L2 (Claude Haiku) judging. If absent, L2 fails open and content posts through the L1 keyword filter only.

---

## Milestones (DRP 2026)

| Date | Milestone | Weight |
|---|---|---|
| Thu 22 May | M1 — Elevator pitch | 5% |
| Fri 29 May | M2 — Concept Development | 5% |
| Mon 2 Jun | Law TRA | 10% |
| Fri 5 Jun | M3 — Iterative Development | 5% |
| Fri 12 Jun | M4 — Iterative Development | 5% |
| 16–17 Jun | **Final Demo + Presentation** | **50%** |
| Thu 19 Jun | Project Documentation | 20% |

---

## Acknowledgements

DRP module: Imperial College London Department of Computing × Royal College of Art Service Design.
User research with adults with ADHD and NHS practitioners (notes in `interviews/`).
