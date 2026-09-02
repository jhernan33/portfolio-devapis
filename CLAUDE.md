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
| `/health` | GET | public — backend + DB health |
| `/api/analytics` | GET | **HTTP Basic** — stats JSON |
| `/api/analytics/recent` | GET | **HTTP Basic** — recent visits JSON |
| `/analytics` | GET | **HTTP Basic** — HTML dashboard |

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
pip install -r requirements-dev.txt
python -m pytest
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

**Frontend — manual checklist:** theme toggle (light/dark), smooth-scroll nav,
certificate modal (click any cert card), PDF export button, responsive layouts,
keyboard/screen-reader accessibility. Structural regressions (ES/EN sync, ATS
docs, OG image, page-weight budget, no inline JS) are covered by CI guards.

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

The `Analytics` module hardcodes the production `/api/track` URL and swallows all errors so tracking never affects UX. It sends no body — the backend derives everything from request headers.

### Backend Architecture (`backend/app/`)
FastAPI app assembled by `create_app()` in `backend/app/__init__.py`; `backend/main.py`
only instantiates it for uvicorn. One module per responsibility:

```
app/config.py             Settings (frozen dataclass) + load_settings(); required secrets
app/security.py           require_analytics_auth (HTTP Basic, constant-time compare)
app/privacy.py            anonymize_ip, is_internal_ip, client_ip_from_request
app/useragent.py          parse_user_agent as ordered rule tables
app/db.py                 create_pool, DDL_SCRIPT, init_database + legacy backfills
app/models.py             Pydantic response models (the API contract; /docs is off)
app/repositories/visits.py VisitRepository — the only place that speaks SQL
app/routes/public.py      POST /api/track, GET /health
app/routes/analytics.py   /api/analytics, /api/analytics/recent, /analytics + its css/js
app/static/               dashboard.html / .css / .js (no inline script; served with CSP)
app/dependencies.py       get_settings / get_visits — read app.state, injected via Depends
```

Key points:

- **Connection pool:** one `asyncpg` pool created in the `lifespan` handler (`min_size=1, max_size=10`), stored in `app.state.pool` and closed on shutdown. There is **no module-level state**: settings and pool live in `app.state`, and routes receive them through `Depends` (`app/dependencies.py`). That is what lets the tests swap the pool for an in-memory double without patching modules.
- **Schema auto-init:** on startup `init_database()` runs the DDL (`CREATE TABLE IF NOT EXISTS`, idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations, indexes, the `cv_analytics_summary` view) and then backfills anonymized IPs for legacy rows. This mirrors `database/init-analytics.sql`. **If you change the schema, update both** `backend/app/db.py`'s `DDL_SCRIPT` and `database/init-analytics.sql`.
- **Required config:** `DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD`, `ANALYTICS_IP_SALT` have **no defaults** — `load_settings()` raises and the container refuses to start if any is missing. This is deliberate: the old code silently fell back to `postgres`/`postgres`. `docker-compose.yaml` additionally requires `DB_HOST`, `DB_NAME` and `DB_USER` via `${VAR:?}`, after a defaulted `DB_HOST=postgres17` pointed at a container that did not exist on the host and left the service restart-looping unnoticed.
- **IP anonymization:** IPs are **never stored in clear text**. `anonymize_ip()` validates the value is a real IP (which also neutralizes injection via the client-controlled `x-forwarded-for` header), then stores `ip_prefix` (truncated /24 IPv4, /48 IPv6) and `ip_hash` (SHA-256 salted with `ANALYTICS_IP_SALT`). Changing the salt breaks unique-visitor continuity.
- **Visit tracking:** `/api/track` parses browser/OS/device from the User-Agent via a hand-rolled `parse_user_agent()` (no external UA library) and inserts a row. Errors return `{"status":"error"}` without the exception detail.
- **Dashboard:** three plain files in `backend/app/static/` served by authenticated routes under `/analytics/`, with a `script-src 'self'` CSP. The JS builds the DOM with `createElement`/`textContent`, never `innerHTML` with request-derived data.
- **Timezone:** stored timestamps are UTC; API responses convert display times to Venezuela time (UTC-4) via `to_venezuela_time()`.
- **CORS:** restricted to `https://devapis.cloud` and localhost origins.
- **Data model:** single table `cv_visits` (ip_prefix, ip_hash, user_agent, browser, os, device_type, referer, language, `is_internal`, visited_at, created_at).
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
- CSP forbids inline scripts — all JS must live in `main.js`.

### Backend (`backend/app/`)
- Keep it dependency-light (currently only fastapi, uvicorn, asyncpg). Adding a lib means editing `backend/requirements.txt` and rebuilding the image.
- Schema changes: update DDL in `backend/app/db.py` **and** `database/init-analytics.sql`.
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
