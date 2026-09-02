# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Professional CV/Portfolio landing page plus a self-hosted visit-tracking analytics service. Two independently deployed pieces that share one `docker-compose.yaml` and one Traefik reverse proxy:

1. **Frontend (`src/`)** — Zero-build, zero-dependency vanilla JS static site served by Nginx.
2. **Analytics backend (`backend/`)** — FastAPI + asyncpg service that records visits into PostgreSQL and exposes a stats API and a dashboard.

**Production URLs (all on `devapis.cloud`, routed by path):**

| Path | Method | Auth |
|---|---|---|
| `/cv` | GET | public — static CV site |
| `/api/track` | POST | public (Traefik rate limit: 10/min, burst 20) |
| `/health` | GET | public — 200 if the service answers, 503 if not. Says nothing about which component failed |
| `/api/analytics` | GET | **HTTP Basic** — stats JSON |
| `/api/analytics/recent` | GET | **HTTP Basic** — recent visits JSON |
| `/api/analytics/health` | GET | **HTTP Basic** — detailed diagnostics (row counts, pool) |
| `/analytics` | GET | **HTTP Basic** — HTML dashboard (+ its `dashboard.css` / `.js`) |

Both analytics routers are rate-limited in Traefik: 10/min on `/api/track`, 15/min on
the private ones — constant-time credential comparison stops timing attacks, not volume.

Auth is enforced **in the application** (`require_analytics_auth` in `backend/app/security.py`),
not in Traefik, so protection is versioned and survives container recreation.
`/docs`, `/redoc` and `/openapi.json` are disabled.

## Development Commands

### Frontend — local
```bash
# Serve the static site (no build step)
python -m http.server 8000 --directory src/
# or
npx serve src/
# → http://localhost:8000
```

### Frontend — Docker
```bash
docker build -t landpage .
docker run -p 8080:8080 landpage   # → http://localhost:8080 (nginx-unprivileged listens on 8080)
```

### Backend — local
```bash
cd backend
pip install -r requirements.txt
# Requires a reachable PostgreSQL; configure via env vars (see below)
uvicorn main:app --reload --port 8000   # → http://localhost:8000
```

### Full stack — Docker Compose (production)
```bash
docker compose up -d              # builds+runs cv + analytics-api
docker compose logs -f            # all services
docker compose logs -f analytics-api
docker compose restart            # restart both
docker compose down

# Convenience scripts:
./deploy-analytics.sh             # first-time analytics setup (checks postgres17, network, seeds schema, verifies endpoints)
./update-production.sh            # rebuild analytics-api and force-recreate both services
```

### Testing

**Backend — automated** (`backend/tests/`, run by CI in the `backend` job):

```bash
cd backend
make test        # crea .venv, instala requirements-dev y ejecuta pytest
make lint        # ruff check + ruff format --check, lo mismo que la CI
```

No PostgreSQL required: `conftest.py` replaces the pool with an in-memory double
and `ASGITransport` skips the `lifespan`, so each test injects a `Settings` and the
fake pool into `app.state`. A suite that requires a container is a suite that stops being
run. Cover, in order of importance: `anonymize_ip`/`is_internal_ip` (nothing but a
truncated prefix and a salted hash ever reaches the DB, `X-Forwarded-For`
injection is neutralized), the auth matrix (every `/api/analytics*` and
`/analytics` route answers 401 without credentials and 503 when unconfigured),
and `parse_user_agent` ordering.

**`parse_user_agent` ordering is load-bearing and tested for that reason.** Every
UA string carries several clues at once and the first branch wins: Opera and Edge
also announce `Chrome/`, Android declares `Linux`, and iPhone/iPad declare
`like Mac OS X`. Those three were mis-ordered and silently mislabelled every
Opera, Android and iOS visit ever recorded — while `device_type`, computed
separately, correctly said `Mobile`. The rules are ordered tables (`BROWSERS`,
`SYSTEMS`) in `backend/app/useragent.py`, so the order is visible data: add new
browsers/OSes as a row, most-specific-first, and add a test.

**Frontend — end-to-end** (`tools/e2e/`, run by CI in the `frontend-e2e` job):

```bash
cd tools/e2e
npm ci && npx playwright install chromium
npx playwright test
```

Playwright lives in `tools/e2e/` so `src/` stays dependency-free. The server
serves `src/` **under `/cv/`** (`preparar-servidor.sh` symlinks it), because the
HTML carries `<base href="/cv/">`: served at the root, every asset 404s and the
tests would measure a page with no CSS or JS. Navigate with `goto('./')`, never
`goto('/')` — an absolute path replaces the whole base path. Two projects, desktop
and mobile; the mobile menu and the double-fire guard on tap are only covered by
the mobile one.

Covered: theme persists across reload, certificate modal traps and restores focus,
collapsed certifications, nav active state (opening the mobile menu first), the
tracking payload, and that the English page's JS-generated strings are English.

Structural regressions (ES/EN sync, untranslated text, ATS docs, OG image,
page-weight budget, no inline JS, security headers, real 404) are covered by CI
guards.

## Architecture

### Zero-Build Frontend Philosophy
The `src/` frontend intentionally has **no build system** — files are served directly, no transpile/bundle/minify, no npm deps. Edits are reflected on refresh (or container restart). This constraint does **not** apply to the backend, which is a normal Python service.

### Frontend Modules (`src/main.js`)
IIFE modules, each with an `init()` called from a single `init()` on DOM ready. No inter-module dependencies. `data-js="true"` is set on `<html>` once JS loads.

```
ThemeManager   Dark/light mode, localStorage key `cv-color-scheme`
SmoothScroll   Anchor nav with history.pushState
NavHighlight   Active nav link via Intersection Observer
Accessibility  Skip links, ARIA live regions
CertModal      Certificate image lightbox
PDFExport      Print/PDF with forced light theme
PrintHandler   Ctrl+P / Cmd+P shortcut
Analytics      POSTs to https://devapis.cloud/api/track ~1s after load; fails silently
```

The `Analytics` module hardcodes the production `/api/track` URL and swallows all errors so tracking never affects UX. It sends `{"page": location.pathname}` so ES and EN visits can be told apart; everything else the backend derives from request headers. The backend never stores that value raw — it maps it against a closed set (`app/paginas.py`) and anything unknown becomes `otro`.

### Backend Architecture (`backend/app/`)
FastAPI app assembled by `create_app()` in `backend/app/__init__.py`; `backend/main.py`
only instantiates it for uvicorn. One module per responsibility:

```
app/config.py             Settings (frozen dataclass) + load_settings(); required secrets
app/security.py           require_analytics_auth (HTTP Basic, constant-time compare)
app/privacy.py            anonymize_ip, is_internal_ip, client_ip_from_request
app/useragent.py          parse_user_agent as ordered rule tables
app/db.py                 create_pool + reconciliación de tráfico interno en cada arranque
app/migrations.py         runner de migraciones (SQL numerado + migraciones de Python)
app/logs.py               logger de la aplicación, nivel por LOG_LEVEL
app/middleware.py         cabeceras de seguridad de todas las respuestas
app/timeutils.py          zona de presentación (ANALYTICS_DISPLAY_TZ)
migrations/*.sql          esquema versionado, anotado en la tabla schema_migrations
app/models.py             Pydantic response models (the API contract; /docs is off)
app/repositories/visits.py VisitRepository — the only place that speaks SQL
app/routes/public.py      POST /api/track, GET /health
app/routes/analytics.py   /api/analytics, /api/analytics/recent, /analytics + its css/js
app/static/               dashboard.html / .css / .js (no inline script; served with CSP)
app/dependencies.py       get_settings / get_visits — read app.state, injected via Depends
```

Key points:

- **Connection pool:** one `asyncpg` pool created in the `lifespan` handler (`min_size=1, max_size=10`), stored in `app.state.pool` and closed on shutdown. There is **no module-level state**: settings and pool live in `app.state`, and routes receive them through `Depends` (`app/dependencies.py`). That is what lets the tests swap the pool for an in-memory double without patching modules.
- **Schema:** versioned migrations in `backend/migrations/`, applied on startup and recorded in `schema_migrations`. **To change the schema, add a numbered file — never edit an applied one.** A migration that needs Python (deriving a salted hash, say) goes in `MIGRACIONES_PYTHON` in `app/migrations.py` and shares the numbering. `backend/Dockerfile` must copy `migrations/`, or the container starts against a schema-less database and only fails on the first visit. Separate from migrations: `reconciliar_trafico_interno()` runs on **every** startup, because `ANALYTICS_IGNORE_NETWORKS` changes and old rows must be re-evaluated when it does.
- **Required config:** `DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD`, `ANALYTICS_IP_SALT` have **no defaults** — `load_settings()` raises and the container refuses to start if any is missing. This is deliberate: the old code silently fell back to `postgres`/`postgres`. `docker-compose.yaml` additionally requires `DB_HOST`, `DB_NAME` and `DB_USER` via `${VAR:?}`, after a defaulted `DB_HOST=postgres17` pointed at a container that did not exist on the host and left the service restart-looping unnoticed.
- **IP anonymization:** IPs are **never stored in clear text**. `anonymize_ip()` validates the value is a real IP (which also neutralizes injection via the client-controlled `x-forwarded-for` header), then stores `ip_prefix` (truncated /24 IPv4, /48 IPv6) and `ip_hash` (SHA-256 salted with `ANALYTICS_IP_SALT`). Changing the salt breaks unique-visitor continuity.
- **Visit tracking:** `/api/track` parses browser/OS/device from the User-Agent via a hand-rolled `parse_user_agent()` (no external UA library) and inserts a row. Errors return `{"status":"error"}` without the exception detail. The request body is capped at 512 bytes and an unreadable one is discarded silently — a public route must never fail on what the client sends.
- **Dashboard:** three plain files in `backend/app/static/` served by authenticated routes under `/analytics/`, with a `script-src 'self'` CSP. The JS builds the DOM with `createElement`/`textContent`, never `innerHTML` with request-derived data.
- **Timezone:** columns are `TIMESTAMPTZ` and the pool pins the session to UTC, so nothing depends on the Postgres container's clock settings. `ANALYTICS_DISPLAY_TZ` (default `America/Caracas`) decides two things: the offset of the dates the API returns, and **where the day starts** in the aggregates. A visit at 20:00 in Caracas used to land on the next day when the cut was made in UTC. The repository applies it in SQL (`AT TIME ZONE $1`); an unknown zone warns and falls back to UTC rather than refusing to start.
- **CORS:** restricted to `https://devapis.cloud` and localhost origins.
- **Data model:** single table `cv_visits` (ip_prefix, ip_hash, `visitor_hash`, user_agent, browser, os, device_type, referer, language, `page`, `is_internal`, `is_bot`, `is_repeat`, visited_at, created_at).
- **What counts as a visit.** Two filters, defined once in `app/repositories/visits.py`: `PERSONAS` (`NOT is_internal AND NOT is_bot`) is the base for unique visitors, browsers and devices; `VISITAS` adds `NOT is_repeat` and is what "visits" means. A reload or a second tab from the same `visitor_hash` within 30 minutes is the same visit — computed **inside the INSERT**, because asking first and writing after is two round trips and a window where two concurrent requests each declare themselves the first. `visitor_hash` is `sha256(salt:ip:user-agent)`: `ip_hash` alone counted a whole NAT'd office as one visitor. Uniques use `COALESCE(visitor_hash, ip_hash)` so rows older than the column still count.
- **Internal traffic:** `is_internal_ip()` flags a visit as own traffic when the IP is private/loopback/link-local/reserved **or** falls in `ANALYTICS_IGNORE_NETWORKS`. Both checks are needed: the server's own public IP is a perfectly valid public IP, so `is_private` does not catch it, and every `curl` health check fired from the VPS would count as a visit — in the first real-traffic measurement that plus internal browsing was **70% of all recorded "visits"**. Flagged rows are still stored and still appear in `/api/analytics/recent` (marked), but every aggregate query and the `cv_analytics_summary` view filter them out with `WHERE NOT is_internal`. Keep `/recent` unfiltered: in local development everything is private, and without it you cannot tell "nothing is arriving" from "it arrives and is being discarded". Legacy installs may still carry an `ip_address` column until `database/migrate-anonymize-ips.sql` is run.

### Deployment Architecture
```
Browser (HTTPS) → Traefik (TLS termination, path routing on devapis.cloud)
    ├─ PathPrefix(/cv)                      → strip /cv → cv (Nginx :8080, serves src/)
    ├─ Path(/api/track) or Path(/health)    → analytics-api  [router analytics-public,
    │                                          priority 100, rate-limited]
    └─ PathPrefix(/api/analytics)           → analytics-api  [router analytics-private,
       or PathPrefix(/analytics)               priority 90, app-level HTTP Basic]
```

The two routers are split so tracking stays public while stats stay private.

**`priority` is load-bearing, not cosmetic.** Traefik's own dashboard is published
on the same host by the Traefik container's labels:
`Host(devapis.cloud) && (PathPrefix(/api) || PathPrefix(/dashboard))`, guarded by a
`basicauth` middleware. Traefik v2 derives priority from rule length, so that router
scores **73** and claims every `/api/*` path that nothing outranks. Both routers here
must therefore stay **above 73** — otherwise requests land on the Traefik dashboard
and come back as `401` with `WWW-Authenticate: Basic realm="traefik"`. That is exactly
what silently broke `POST /api/track` for months: the frontend swallows tracking
errors by design, so nothing surfaced. Public (100) also outranks private (90) so
`/api/track` never falls through to the private router.

Both services join the external **`server`** network (Traefik). `analytics-api`
**additionally joins `db-internal`**, because the PostgreSQL container is deliberately
not on `server`; without that second network the service cannot resolve `DB_HOST` and
dies at startup with `gaierror: Temporary failure in name resolution`. Create `server`
with `docker network create server` if missing; `db-internal` belongs to the project
that owns PostgreSQL.

**`DB_HOST` is a container name, and it is not guessable.** Read it from the host
rather than from memory or from this file — `docker ps --format '{{.Names}}' | grep -i postgres`
— and confirm the container shares a network with `analytics-api`. Traefik uses cert
resolver `resolver` for automatic TLS. Routing labels live in `docker-compose.yaml`;
the `/cv` prefix is stripped by the `cv-stripprefix` middleware before reaching Nginx.

**Containers run without root.** The frontend image is `nginxinc/nginx-unprivileged`
(uid 101) and therefore listens on **8080**, not 80: a non-root process cannot bind a
privileged port, and putting `listen 80` back kills the container at startup. The
backend image creates a system user `app` and switches to it before `CMD`. Both
services in `docker-compose.yaml` run with `no-new-privileges`, `cap_drop: ALL` and a
`read_only` filesystem with `tmpfs` on `/tmp` — so nothing in either service may write
to disk. The CI `compose` job checks all of this.

**Security headers live in `nginx-security-headers.conf`, included in `server` *and* in
every `location` that sets a header.** Nginx does not merge `add_header` across levels:
a `location` with its own `Cache-Control` drops *all* headers inherited from `server`.
With the headers written only at server level, **no response carried the CSP or HSTS**,
in production, for months, with no visible symptom. If you add a `location` with an
`add_header`, add the `include` too. The CI `compose` job boots the image and checks
every route for the four headers and for exactly one `Cache-Control`.

**Nginx (`nginx.conf`):** only a `server {}` block (global directives were removed — they conflict with `nginx:1.27-alpine` defaults and caused `duplicate directive` startup crashes; keep it that way). SPA fallback (404→index.html), `index.html` no-cache, assets cached 1y immutable, security headers (CSP restricts scripts to `'self'`, so keep JS in external `main.js`), gzip, `.git`/dotfiles blocked.

## Configuration & Secrets

Unlike the pure-static original, the backend **does use secrets**. `.env` (gitignored) supplies DB credentials consumed by `docker-compose.yaml` → the analytics container:

```
DB_HOST=...              # required — the PostgreSQL *container name*, verify with docker ps
DB_NAME=...              # required
DB_USER=...              # required — a dedicated role, not the postgres superuser
DB_PASSWORD=...          # required
DB_PORT=5432
ANALYTICS_USER=...       # required — guards the stats endpoints
ANALYTICS_PASSWORD=...   # required — openssl rand -base64 32
ANALYTICS_IP_SALT=...    # required — openssl rand -hex 32, set once, never rotate
ANALYTICS_IGNORE_NETWORKS=...  # optional — the server's own public IP; see above
```

Copy `.env.example` → `.env` and fill every value. Never commit `.env`.
`docker-compose.yaml` uses `${VAR:?message}` for the four required secrets, so
`docker compose up` fails fast instead of starting with defaults. See `DEPLOY-ANALYTICS.md` for the full first-deploy runbook and `analytics-backend-proposal.md` for design rationale.

## Code Modification Guidelines

### HTML (`src/index.html`)
Spanish (`lang="es"`), semantic HTML5, ARIA labels, BEM class names.

### CSS (`src/styles.css`)
- BEM naming (`.block__element--modifier`).
- CSS custom properties only — no hardcoded colors. Define token in `:root`, override under `[data-theme="dark"]`.
- **Use `--color-primary-text` for text and focus rings, never `--color-primary`.** The brand blue `#0ea5e9` scores 2.53–2.77:1 against the light backgrounds, well under the 4.5:1 WCAG AA needs for body text (and under 3:1 for focus indicators). `--color-primary-text` resolves to sky-700 `#0369a1` in light and stays `#0ea5e9` in dark, where the original already clears 6.44:1. `--color-primary` remains correct for decorative borders and fills. When white text sits on a brand-coloured background, use `--color-primary-strong`/`--color-primary-stronger`.
- Mobile-first: base styles for mobile, `@media (min-width: ...)` for larger. Breakpoints: 380px, 640px, 768px, 1024px.

### JavaScript (`src/main.js`)
- IIFE module with `init()`; register it in the main `init()`.
- No external dependencies.
- Support both `click` and `touchend` for mobile buttons.
- CSP forbids inline scripts — all JS must live in `main.js` or `theme-init.js`.
- Text generated from JS goes through `t()` and the `TEXTOS` table, never an inline `lang === 'en' ? …` ternary — that check exists once, at the top of the file.
- Buttons use `onActivate(el, fn)`, which registers `click` and `touchend` and swallows the duplicate: on mobile both fire and the action ran twice.
- `theme-init.js` loads **without `defer` in the `<head>`** and owns the `localStorage` key. `main.js` is deferred, so applying the theme there meant a flash of the wrong one on every load. If you add a script tag to `index.html`, teach `tools/generar-version-en.py` to rewrite its path — the English page has no `<base>`.

### Backend (`backend/app/`)
- Keep it dependency-light (currently only fastapi, uvicorn, asyncpg). Adding a lib means editing `backend/requirements.txt` and rebuilding the image.
- Schema changes: add a file to `backend/migrations/` with the next number. Never edit one that has been applied — the databases that already ran it would keep a schema different from the one they claim to have.
- All SQL lives in `app/repositories/`. Routes call repository methods; they never touch the pool or write SQL. The repository acquires from the pool per method; never open ad-hoc connections.
- No module-level state. Anything a route needs comes through `Depends` from `app/dependencies.py`; pure functions (`anonymize_ip`, `is_internal_ip`) take their inputs as parameters.
- Every response has a model in `app/models.py` and the route declares it as `response_model`.
- The dashboard has no inline JS (the CI guard covers `backend/app/static/*.html` too) and every file under `/analytics/` takes `Depends(require_analytics_auth)`.
- Any new endpoint that returns visit data must take `Depends(require_analytics_auth)`.
- Never persist a raw IP. Route it through `anonymize_ip()`.
- Never return `str(e)` to the client; log it and return a generic message.

### Images
Place in `src/assets/images/`, reference relatively (`assets/images/x.webp`), set explicit `width`/`height`, descriptive `alt`.

The **certificate diplomas are WebP**, quality 85. They are the heaviest thing
the site can serve — as PNG the 14 of them were 2.1 MB, now 451 KB — and they
are text, so the conversion was checked at 200% zoom against the originals:
even the UUID line is indistinguishable (RMSE 0.42%). The PNG originals are in
`.backups/certificados-png/` (gitignored), not in `src/`. There is no PNG
fallback on purpose: see the browser-support note below.

The two **Open Graph covers** are the exception on both counts: `og-cover.png`
(ES) and `og-cover-en.png` (EN) are **generated** by `tools/generar-og.py` — edit
the script, not the PNGs — and are referenced by **absolute** URL
(`https://devapis.cloud/cv/assets/images/...`) because the LinkedIn, WhatsApp and
X crawlers read the `<head>` without loading the page and resolve neither
relative paths nor `<base>`. They are 1200×630 (the 1.91:1 that
`twitter:card=summary_large_image` requires); `tools/generar-og.py --check`
enforces the size and the meta tags in CI, and needs no Pillow.

## Important Constraints

- **`-old.*` backups** now live in `.backups/` (gitignored and untracked), not in `src/`. They used to sit in `src/` where Nginx served them publicly at `/cv/index-old.html`. Keep them out of `src/`: anything in that directory is published. Edit the live `index.html` / `styles.css` / `main.js`.
- **Frontend volumes** are mounted read-only in production; changes require the file to be present in `src/`.
- **Browser support:** ES6+, CSS Grid/Flexbox, Intersection Observer required; no IE11.
  WebP raises the floor a little: the certificate images are WebP-only, with no
  `<picture>` fallback, because the modal sets `img.src` from `data-cert` in JS
  and a fallback would mean shipping both formats — which is the entire weight
  saving. That takes the Safari floor from 12.1 (Intersection Observer) to 14
  (Sept 2020). Everything else in the stack is older than that, so WebP is what
  sets the minimum; if a diploma ever renders blank, this is why.
- **Performance budget:** keep total frontend page size well under 200KB (currently ~76KB); CSS/JS unminified is acceptable at this size.

## Troubleshooting

**Frontend changes not appearing:** hard-refresh (Ctrl+Shift+R); `docker compose down && up -d`; confirm the file saved in `src/`.

**Traefik routing:** ensure external `server` network exists (`docker network ls`); check `docker logs traefik`; inspect labels with `docker inspect`.

**Backend unhealthy / DB errors:** `/health` returns 503 if the pool can't reach Postgres. Verify the container named in `DB_HOST` is up (`docker ps | grep -i postgres`), that it shares a network with `analytics-api`, and that `.env` credentials are correct; `docker compose logs -f analytics-api`.

**`gaierror: Temporary failure in name resolution` at startup:** `DB_HOST` names a container that either does not exist or shares no Docker network with `analytics-api`. Check both — the name is the more common mistake, the network the more confusing one, because the name resolves fine from the host shell and only fails inside the container.

**Backend refuses to start / `docker compose up` errors on a variable:** a required secret is missing from `.env` (`DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD`, `ANALYTICS_IP_SALT`). This is intended behaviour, not a bug.

**`/api/track` or `/api/analytics` returns 401:** check the response header. `WWW-Authenticate: Basic realm="traefik"` means the request never reached this backend — it hit the **Traefik dashboard's** own router, which publishes `PathPrefix(/api)` on the same host from labels on the Traefik container (`/home/hernan/traefik/docker-compose.yml`, outside this repo). Its priority is 73; raise the router priority here above that rather than editing Traefik. `realm="cv-analytics"` is the opposite situation and means the app answered, so the credentials are simply wrong. Tracking must stay public; only `/api/analytics*` and `/analytics` are protected.

Verify with a **GET**, capturing the headers:

```bash
curl -s -o /dev/null -D - https://devapis.cloud/api/analytics | grep -iE '^HTTP|www-authenticate'
```

The realm tells you which of the two you are talking to. **Do not use `curl -I`
here.** These routes are declared `GET` only, so a HEAD request answers
`405 Method Not Allowed` with no `WWW-Authenticate` header at all — which reads
exactly like "the stats are being served without credentials". The deploy
workflow's own check had this bug and reported a security alarm that did not
exist. `curl -I` is fine against `/cv`, which Nginx serves.

**Theme not persisting:** check `localStorage` key `cv-color-scheme` (DevTools → Application → Local Storage).

**PDF export:** uses the browser print dialog; theme is forced light during print — use the print media query for print-only styles.

## Fuente de verdad para datos personales

Toda afirmación factual sobre José Hernán Varela (años de experiencia, stack por
empleo, métricas, certificaciones, fechas) debe provenir del perfil canónico, que
se mantiene **fuera de este repositorio** en `~/Documentos/Mio/cv-privado/PERFIL-CANONICO.md`.

Ese documento es privado a propósito: contiene el inventario de correcciones
pendientes y de métricas por verificar, y este repositorio es público.
No lo copies aquí ni cites su contenido en archivos versionados.

Nunca inventes ni estimes datos biográficos, cifras de rendimiento ni logros.
Si un dato no está en el perfil canónico, deténte y pregunta.
