> **Documento histórico.** Es la propuesta con la que se diseñó el backend de
> analytics en agosto de 2026. Se conserva porque explica *por qué* se hizo un
> servicio propio en lugar de usar Google Analytics, pero **el código que
> describe ya no coincide con el que hay**: desde entonces el backend se dividió
> en el paquete `backend/app/`, el esquema pasó a migraciones versionadas y se
> añadieron anonimización, autenticación en la aplicación y el filtrado de
> tráfico que no es una persona.
>
> Para el estado actual: [`CLAUDE.md`](CLAUDE.md) describe la arquitectura y
> [`docs/DECISIONES-TECNICAS.md`](docs/DECISIONES-TECNICAS.md), el porqué de
> cada cambio.

# Sistema de Analytics Propio - Propuesta de Implementación

## Arquitectura

```
┌──────────────┐      POST /api/track      ┌──────────────┐      ┌──────────────┐
│   Frontend   │ ───────────────────────> │   FastAPI    │ ───> │ PostgreSQL   │
│   (CV)       │                           │   Backend    │      │   Database   │
└──────────────┘                           └──────────────┘      └──────────────┘
                                                  │
                                                  ↓
                                           ┌──────────────┐
                                           │   Dashboard  │
                                           │   /analytics │
                                           └──────────────┘
```

## Stack Propuesto

- **Backend**: FastAPI (ligero, rápido, async)
- **Base de Datos**: PostgreSQL (ya lo conoces)
- **Container**: Docker (mismo stack actual)
- **Frontend**: JavaScript vanilla (ya tienes)

## 1. Backend - FastAPI

### `backend/main.py`

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncpg
import os
import user_agents

app = FastAPI()

# CORS para permitir requests desde tu CV
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://devapis.cloud"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Pool de conexiones PostgreSQL
DB_POOL = None

@app.on_event("startup")
async def startup():
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "analytics"),
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        min_size=1,
        max_size=10
    )

@app.on_event("shutdown")
async def shutdown():
    await DB_POOL.close()

@app.post("/api/track")
async def track_visit(request: Request):
    """Registra una visita al CV"""

    # Obtener datos del request
    user_agent_string = request.headers.get("user-agent", "Unknown")
    user_agent = user_agents.parse(user_agent_string)

    # Obtener IP real (considerando proxy Traefik)
    ip = request.headers.get("x-forwarded-for", request.client.host)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    # Datos del navegador
    browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
    os_info = f"{user_agent.os.family} {user_agent.os.version_string}"
    device = "Mobile" if user_agent.is_mobile else "Desktop"

    # Datos adicionales
    referer = request.headers.get("referer", None)
    language = request.headers.get("accept-language", "Unknown")

    # Insertar en base de datos
    async with DB_POOL.acquire() as conn:
        await conn.execute("""
            INSERT INTO visits (
                ip_address,
                user_agent,
                browser,
                os,
                device_type,
                referer,
                language,
                visited_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, ip, user_agent_string, browser, os_info, device, referer, language, datetime.utcnow())

    return {"status": "tracked"}

@app.get("/api/analytics")
async def get_analytics():
    """Dashboard simple de analytics"""

    async with DB_POOL.acquire() as conn:
        # Total de visitas
        total_visits = await conn.fetchval("SELECT COUNT(*) FROM visits")

        # Visitas únicas por IP
        unique_visitors = await conn.fetchval("SELECT COUNT(DISTINCT ip_address) FROM visits")

        # Visitas últimos 7 días
        recent_visits = await conn.fetchval("""
            SELECT COUNT(*) FROM visits
            WHERE visited_at > NOW() - INTERVAL '7 days'
        """)

        # Top 5 navegadores
        top_browsers = await conn.fetch("""
            SELECT browser, COUNT(*) as count
            FROM visits
            GROUP BY browser
            ORDER BY count DESC
            LIMIT 5
        """)

        # Top 5 países/IPs
        top_ips = await conn.fetch("""
            SELECT ip_address, COUNT(*) as visits
            FROM visits
            GROUP BY ip_address
            ORDER BY visits DESC
            LIMIT 10
        """)

        # Dispositivos
        device_stats = await conn.fetch("""
            SELECT device_type, COUNT(*) as count
            FROM visits
            GROUP BY device_type
        """)

    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "recent_visits_7d": recent_visits,
        "top_browsers": [dict(r) for r in top_browsers],
        "top_ips": [dict(r) for r in top_ips],
        "device_stats": [dict(r) for r in device_stats]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### `backend/requirements.txt`

```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
asyncpg==0.30.0
user-agents==2.2.0
python-dotenv==1.0.0
```

### `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 2. Base de Datos - PostgreSQL Schema

### `database/init.sql`

```sql
CREATE TABLE IF NOT EXISTS visits (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(20),
    referer TEXT,
    language VARCHAR(50),
    visited_at TIMESTAMP DEFAULT NOW(),

    -- Índices para queries rápidas
    INDEX idx_ip (ip_address),
    INDEX idx_visited_at (visited_at),
    INDEX idx_device (device_type)
);

-- Vista para analytics rápidos
CREATE OR REPLACE VIEW analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_address) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d
FROM visits;
```

## 3. Docker Compose Actualizado

```yaml
services:
  # Tu CV actual
  cv:
    build: .
    image: landpage:latest
    container_name: landpage
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.cv.rule=Host(`devapis.cloud`) && PathPrefix(`/cv`)"
      - "traefik.http.routers.cv.entrypoints=https"
      - "traefik.http.routers.cv.tls=true"
      - "traefik.http.routers.cv.tls.certresolver=resolver"
      - "traefik.http.middlewares.cv-stripprefix.stripprefix.prefixes=/cv"
      - "traefik.http.routers.cv.middlewares=cv-stripprefix@docker"
      - "traefik.http.routers.cv.service=cv"
      - "traefik.http.services.cv.loadbalancer.server.port=80"
    volumes:
      - ./src:/usr/share/nginx/html:z
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - server
      - analytics

  # Nuevo backend de analytics
  analytics-api:
    build: ./backend
    container_name: analytics-api
    restart: unless-stopped
    environment:
      - DB_HOST=analytics-db
      - DB_NAME=analytics
      - DB_USER=analytics
      - DB_PASSWORD=${DB_PASSWORD}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.analytics.rule=Host(`devapis.cloud`) && PathPrefix(`/api`)"
      - "traefik.http.routers.analytics.entrypoints=https"
      - "traefik.http.routers.analytics.tls=true"
      - "traefik.http.routers.analytics.tls.certresolver=resolver"
      - "traefik.http.routers.analytics.service=analytics"
      - "traefik.http.services.analytics.loadbalancer.server.port=8000"
    depends_on:
      - analytics-db
    networks:
      - server
      - analytics

  # Base de datos PostgreSQL
  analytics-db:
    image: postgres:16-alpine
    container_name: analytics-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=analytics
      - POSTGRES_USER=analytics
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - analytics-data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - analytics

networks:
  server:
    external: true
  analytics:
    internal: true

volumes:
  analytics-data:
```

## 4. Frontend - JavaScript Tracker

### Agregar al `src/main.js`:

```javascript
/* ============================================
   ANALYTICS TRACKER
   ============================================ */

const Analytics = {
	init() {
		this.trackVisit();
	},

	async trackVisit() {
		try {
			const response = await fetch('https://devapis.cloud/api/track', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					timestamp: new Date().toISOString()
				})
			});

			if (response.ok) {
				console.log('Visit tracked');
			}
		} catch (error) {
			console.error('Analytics tracking failed:', error);
		}
	}
};

// Agregar en la función init():
function init() {
	console.log('CV JS initialized');
	ThemeManager.init();
	SmoothScroll.init();
	NavHighlight.init();
	Accessibility.init();
	CertModal.init();
	PDFExport.init();
	PrintHandler.init();
	Analytics.init(); // <-- NUEVO

	document.documentElement.setAttribute('data-js', 'true');
	console.log('All modules loaded');
}
```

## 5. Variables de Entorno

### `.env` (crear en raíz del proyecto)

```env
DB_PASSWORD=tu_password_seguro_aqui
```

**IMPORTANTE**: Agregar `.env` al `.gitignore`

## 6. Deployment

```bash
# 1. Crear archivo .env con password seguro
echo "DB_PASSWORD=$(openssl rand -base64 32)" > .env

# 2. Levantar todo el stack
docker compose up -d --build

# 3. Verificar que todo está corriendo
docker compose ps
```

## 7. Ver Analytics

```bash
# Opción 1: Curl
curl https://devapis.cloud/api/analytics

# Opción 2: Navegador
https://devapis.cloud/api/analytics
```

## 8. Dashboard HTML Simple (Opcional)

Puedes crear un dashboard simple en `/api/dashboard` o hacer queries directas a la DB:

```bash
# Conectar a la DB
docker exec -it analytics-db psql -U analytics -d analytics

# Queries útiles
SELECT * FROM visits ORDER BY visited_at DESC LIMIT 10;
SELECT COUNT(*) FROM visits;
SELECT ip_address, COUNT(*) FROM visits GROUP BY ip_address ORDER BY COUNT(*) DESC;
```

## Ventajas de Esta Solución

✅ **100% bajo tu control**
✅ **IPs reales sin anonimizar**
✅ **Sin bloqueo de ad-blockers**
✅ **Extensible** (agregar geolocalización, mapas, etc.)
✅ **Cumple GDPR** si implementas política de privacidad
✅ **Muestra tus habilidades** de fullstack
✅ **Gratis** (solo infraestructura)

## Próximos Pasos

1. Agregar geolocalización de IPs (MaxMind GeoIP2)
2. Dashboard visual con gráficos (Chart.js)
3. Alertas cuando alguien visita (email/Telegram)
4. Heatmap de clicks
5. Tiempo de permanencia en página

## Costos

- **Infraestructura**: Misma que ya tienes (Docker)
- **Base de datos**: ~10MB para miles de visitas
- **CPU/RAM**: Mínimo (FastAPI es muy eficiente)

## GDPR / Privacidad

⚠️ **Importante**: Si vas a guardar IPs, debes:
1. Agregar política de privacidad en el CV
2. Mencionar que se registran IPs con fines estadísticos
3. Ofrecer forma de eliminar datos (derecho al olvido)
4. No compartir datos con terceros

Ejemplo de aviso:

```html
<!-- Footer del CV -->
<p class="footer__privacy">
  Este sitio registra estadísticas de visitas (IP, navegador) con fines analíticos.
  <a href="/privacy">Política de Privacidad</a>
</p>
```
