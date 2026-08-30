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

Auth is enforced **in the application** (`require_analytics_auth` in `backend/main.py`),
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
docker run -p 8080:80 landpage   # → http://localhost:8080
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
No automated tests. Manual checklist:
- **Frontend:** theme toggle (light/dark), smooth-scroll nav, certificate modal (click any cert card), PDF export button, responsive layouts, keyboard/screen-reader accessibility.
- **Backend:** `curl https://devapis.cloud/health`, `curl -X POST https://devapis.cloud/api/track`, `curl https://devapis.cloud/api/analytics`.

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

### Backend Architecture (`backend/main.py`)
Single-file FastAPI app. Key points:

- **Connection pool:** one global `asyncpg` pool created in the `lifespan` handler (`min_size=1, max_size=10`), closed on shutdown.
- **Schema auto-init:** on startup `init_database()` runs the DDL (`CREATE TABLE IF NOT EXISTS`, idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations, indexes, the `cv_analytics_summary` view) and then backfills anonymized IPs for legacy rows. This mirrors `database/init-analytics.sql`. **If you change the schema, update both** `main.py`'s `DDL_SCRIPT` and `database/init-analytics.sql`.
- **Required config:** `DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD`, `ANALYTICS_IP_SALT` have **no defaults** — `get_settings()` raises and the container refuses to start if any is missing. This is deliberate: the old code silently fell back to `postgres`/`postgres`.
- **IP anonymization:** IPs are **never stored in clear text**. `anonymize_ip()` validates the value is a real IP (which also neutralizes injection via the client-controlled `x-forwarded-for` header), then stores `ip_prefix` (truncated /24 IPv4, /48 IPv6) and `ip_hash` (SHA-256 salted with `ANALYTICS_IP_SALT`). Changing the salt breaks unique-visitor continuity.
- **Visit tracking:** `/api/track` parses browser/OS/device from the User-Agent via a hand-rolled `parse_user_agent()` (no external UA library) and inserts a row. Errors return `{"status":"error"}` without the exception detail.
- **Dashboard:** built with `createElement`/`textContent`, never `innerHTML` with request-derived data.
- **Timezone:** stored timestamps are UTC; API responses convert display times to Venezuela time (UTC-4) via `to_venezuela_time()`.
- **CORS:** restricted to `https://devapis.cloud` and localhost origins.
- **Data model:** single table `cv_visits` (ip_prefix, ip_hash, user_agent, browser, os, device_type, referer, language, visited_at, created_at). Legacy installs may still carry an `ip_address` column until `database/migrate-anonymize-ips.sql` is run.

### Deployment Architecture
```
Browser (HTTPS) → Traefik (TLS termination, path routing on devapis.cloud)
    ├─ PathPrefix(/cv)                      → strip /cv → cv (Nginx :80, serves src/)
    ├─ Path(/api/track) or Path(/health)    → analytics-api  [router analytics-public,
    │                                          priority 100, rate-limited]
    └─ PathPrefix(/api/analytics)           → analytics-api  [router analytics-private,
       or PathPrefix(/analytics)               priority 50, app-level HTTP Basic]
```

The two routers are split so tracking stays public while stats stay private.
`priority` is set explicitly so the narrower public rule wins.

Both services join the **external `server` Docker network** (must already exist; `docker network create server` if not) and rely on a **PostgreSQL container named `postgres17`** on that same network. Traefik uses cert resolver `resolver` for automatic TLS. Routing labels live in `docker-compose.yaml`; the `/cv` prefix is stripped by the `cv-stripprefix` middleware before reaching Nginx.

**Nginx (`nginx.conf`):** only a `server {}` block (global directives were removed — they conflict with `nginx:1.27-alpine` defaults and caused `duplicate directive` startup crashes; keep it that way). SPA fallback (404→index.html), `index.html` no-cache, assets cached 1y immutable, security headers (CSP restricts scripts to `'self'`, so keep JS in external `main.js`), gzip, `.git`/dotfiles blocked.

## Configuration & Secrets

Unlike the pure-static original, the backend **does use secrets**. `.env` (gitignored) supplies DB credentials consumed by `docker-compose.yaml` → the analytics container:

```
DB_HOST=postgres17
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=...          # required, no default
DB_PORT=5432
ANALYTICS_USER=...       # required — guards the stats endpoints
ANALYTICS_PASSWORD=...   # required — openssl rand -base64 32
ANALYTICS_IP_SALT=...    # required — openssl rand -hex 32, set once, never rotate
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
- Mobile-first: base styles for mobile, `@media (min-width: ...)` for larger. Breakpoints: 380px, 640px, 768px, 1024px.

### JavaScript (`src/main.js`)
- IIFE module with `init()`; register it in the main `init()`.
- No external dependencies.
- Support both `click` and `touchend` for mobile buttons.
- CSP forbids inline scripts — all JS must live in `main.js`.

### Backend (`backend/main.py`)
- Keep it dependency-light (currently only fastapi, uvicorn, asyncpg). Adding a lib means editing `backend/requirements.txt` and rebuilding the image.
- Schema changes: update DDL in `main.py` **and** `database/init-analytics.sql`.
- Acquire connections via `DB_POOL.acquire()`; never open ad-hoc connections.
- Any new endpoint that returns visit data must take `Depends(require_analytics_auth)`.
- Never persist a raw IP. Route it through `anonymize_ip()`.
- Never return `str(e)` to the client; log it and return a generic message.

### Images
Place in `src/assets/images/`, reference relatively (`assets/images/x.png`), set explicit `width`/`height`, descriptive `alt`.

## Important Constraints

- **`-old.*` backups** now live in `.backups/` (gitignored and untracked), not in `src/`. They used to sit in `src/` where Nginx served them publicly at `/cv/index-old.html`. Keep them out of `src/`: anything in that directory is published. Edit the live `index.html` / `styles.css` / `main.js`.
- **Frontend volumes** are mounted read-only in production; changes require the file to be present in `src/`.
- **Browser support:** ES6+, CSS Grid/Flexbox, Intersection Observer required; no IE11.
- **Performance budget:** keep total frontend page size well under 200KB (currently ~76KB); CSS/JS unminified is acceptable at this size.

## Troubleshooting

**Frontend changes not appearing:** hard-refresh (Ctrl+Shift+R); `docker compose down && up -d`; confirm the file saved in `src/`.

**Traefik routing:** ensure external `server` network exists (`docker network ls`); check `docker logs traefik`; inspect labels with `docker inspect`.

**Backend unhealthy / DB errors:** `/health` returns 503 if the pool can't reach Postgres. Verify the `postgres17` container is up on the `server` network and `.env` credentials are correct; `docker compose logs -f analytics-api`.

**Backend refuses to start / `docker compose up` errors on a variable:** a required secret is missing from `.env` (`DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD`, `ANALYTICS_IP_SALT`). This is intended behaviour, not a bug.

**`/api/track` returns 401:** something is applying auth to the whole `/api` prefix — most likely a leftover Traefik `basicauth` middleware defined outside this repo (a `docker-compose.override.yaml` on the server or a Traefik file-provider config). Tracking must stay public; only `/api/analytics*` and `/analytics` are protected.

**Theme not persisting:** check `localStorage` key `cv-color-scheme` (DevTools → Application → Local Storage).

**PDF export:** uses the browser print dialog; theme is forced light during print — use the print media query for print-only styles.
