"""
CV Analytics API
================
FastAPI backend para tracking de visitas al CV.

Principios de seguridad de este módulo:
- Las IPs de los visitantes NUNCA se almacenan en claro. Se guardan un prefijo
  de red truncado (para geografía aproximada) y un hash SHA-256 con sal (para
  contar visitantes únicos sin poder reidentificarlos).
- Los endpoints de consulta exigen autenticación HTTP Basic a nivel de
  aplicacion, de modo que la proteccion viaja con el repositorio y no depende
  de la configuracion del reverse proxy.
- Los secretos son obligatorios: si faltan, el servicio no arranca.
"""

from fastapi import FastAPI, Request, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta, timezone
import asyncpg
import hashlib
import ipaddress
import os
import secrets
from contextlib import asynccontextmanager

# Variable global para el pool de conexiones
DB_POOL = None

# ============================================
# CONFIGURACIÓN
# ============================================

# Variables obligatorias: sin ellas el servicio no debe arrancar.
# (Antes DB_PASSWORD caía en "postgres" por defecto, lo que permitía arrancar
#  silenciosamente contra la base de producción con credenciales por defecto.)
REQUIRED_ENV = ("DB_PASSWORD", "ANALYTICS_USER", "ANALYTICS_PASSWORD", "ANALYTICS_IP_SALT")


def get_settings() -> dict:
    """Lee y valida la configuración desde el entorno."""
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno obligatorias: " + ", ".join(missing) +
            ". Defínelas en el archivo .env (ver .env.example)."
        )

    return {
        "db_user": os.getenv("DB_USER", "postgres"),
        "db_password": os.getenv("DB_PASSWORD"),
        "db_name": os.getenv("DB_NAME", "postgres"),
        "db_host": os.getenv("DB_HOST", "postgres17"),
        "db_port": int(os.getenv("DB_PORT", "5432")),
        "analytics_user": os.getenv("ANALYTICS_USER"),
        "analytics_password": os.getenv("ANALYTICS_PASSWORD"),
        "ip_salt": os.getenv("ANALYTICS_IP_SALT"),
    }


SETTINGS: dict = {}


# ============================================
# AUTENTICACIÓN
# ============================================

security = HTTPBasic(realm="cv-analytics")


def require_analytics_auth(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """Protege los endpoints que exponen datos de visitas."""
    expected_user = SETTINGS.get("analytics_user") or ""
    expected_password = SETTINGS.get("analytics_password") or ""

    if not expected_user or not expected_password:
        # Fail closed: si no hay credenciales configuradas, no se sirve nada.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics authentication is not configured",
        )

    # Se comparan ambos siempre (sin cortocircuito) y en tiempo constante.
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_password.encode("utf-8")
    )

    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="cv-analytics"'},
        )

    return credentials.username


# ============================================
# ANONIMIZACIÓN DE IPs
# ============================================

def anonymize_ip(raw_ip: str):
    """
    Convierte una IP en (prefijo_de_red, hash_con_sal).

    - Valida que la entrada sea realmente una IP. Esto neutraliza la inyección
      vía cabecera `X-Forwarded-For`, que es controlable por el cliente.
    - IPv4 se trunca a /24 y IPv6 a /48: suficiente para estadísticas
      aproximadas, insuficiente para identificar a una persona.
    - El hash permite contar visitantes únicos sin conservar la IP.

    Devuelve (None, None) si la entrada no es una IP válida.
    """
    if not raw_ip:
        return None, None

    try:
        ip = ipaddress.ip_address(raw_ip.strip())
    except ValueError:
        return None, None

    network = 24 if ip.version == 4 else 48
    prefix = str(ipaddress.ip_network(f"{ip}/{network}", strict=False).network_address)
    digest = hashlib.sha256(
        f"{SETTINGS.get('ip_salt', '')}:{ip}".encode("utf-8")
    ).hexdigest()

    return prefix, digest


def client_ip_from_request(request: Request) -> str:
    """Extrae la IP del cliente respetando la cadena X-Forwarded-For de Traefik."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Tomar la PRIMERA de la cadena solo es seguro mientras el proxy
        # sobrescriba la cabecera en lugar de añadirse a la que mande el
        # cliente. Traefik lo hace así salvo que la petición venga de una IP
        # listada en `forwardedHeaders.trustedIPs`, que aquí no está definida:
        # verificado enviando `X-Forwarded-For: 8.8.8.8` y comprobando que se
        # registra igualmente la red real.
        #
        # Si algún día se pone Cloudflare delante y se configura trustedIPs
        # para leer la IP real del visitante, esta línea pasa a leer un valor
        # que controla el cliente y cualquiera podrá falsear su red. La
        # validación de anonymize_ip no protege de eso: descarta basura, pero
        # 8.8.8.8 es una IP perfectamente válida.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# ============================================
# BASE DE DATOS
# ============================================

DDL_SCRIPT = """
-- Tabla de visitas (sin IPs en claro)
CREATE TABLE IF NOT EXISTS cv_visits (
    id SERIAL PRIMARY KEY,
    ip_prefix VARCHAR(45),
    ip_hash CHAR(64),
    user_agent TEXT,
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(20),
    referer TEXT,
    language VARCHAR(50),
    visited_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Migración para instalaciones anteriores que aún tienen ip_address
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_prefix VARCHAR(45);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_hash CHAR(64);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE cv_visits ALTER COLUMN ip_address DROP NOT NULL;
    END IF;
END $$;

-- Índices
DROP INDEX IF EXISTS idx_cv_visits_ip;
CREATE INDEX IF NOT EXISTS idx_cv_visits_ip_hash ON cv_visits(ip_hash);
CREATE INDEX IF NOT EXISTS idx_cv_visits_visited_at ON cv_visits(visited_at DESC);
CREATE INDEX IF NOT EXISTS idx_cv_visits_device ON cv_visits(device_type);
CREATE INDEX IF NOT EXISTS idx_cv_visits_browser ON cv_visits(browser);

-- Vista para analytics rápidos.
-- Se recrea sobre ip_hash para eliminar la dependencia con ip_address y
-- permitir que la columna antigua pueda purgarse.
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_hash) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') as visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d,
    COUNT(*) FILTER (WHERE visited_at::date = CURRENT_DATE) as visits_today
FROM cv_visits;
"""


async def backfill_anonymized_ips(conn) -> int:
    """
    Rellena ip_prefix/ip_hash de las filas antiguas que aún tengan ip_address.

    No borra nada: la purga de la columna ip_address es un paso explícito y
    manual (database/migrate-anonymize-ips.sql), porque es irreversible.
    """
    has_legacy_column = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
        )
    """)
    if not has_legacy_column:
        return 0

    rows = await conn.fetch("""
        SELECT id, ip_address FROM cv_visits
        WHERE ip_hash IS NULL AND ip_address IS NOT NULL
    """)
    if not rows:
        return 0

    updates = []
    for row in rows:
        prefix, digest = anonymize_ip(row["ip_address"])
        updates.append((prefix, digest, row["id"]))

    await conn.executemany(
        "UPDATE cv_visits SET ip_prefix = $1, ip_hash = $2 WHERE id = $3",
        updates,
    )
    return len(updates)


async def init_database():
    """Inicializa el esquema y migra instalaciones anteriores."""
    async with DB_POOL.acquire() as conn:
        await conn.execute(DDL_SCRIPT)
        print("✅ Database schema initialized")

        migrated = await backfill_anonymized_ips(conn)
        if migrated:
            print(f"✅ {migrated} visitas antiguas anonimizadas")
            print("   Ejecuta database/migrate-anonymize-ips.sql para purgar ip_address")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    global DB_POOL, SETTINGS

    # Falla de forma ruidosa si falta configuración, en lugar de arrancar
    # con credenciales por defecto.
    SETTINGS = get_settings()

    DB_POOL = await asyncpg.create_pool(
        user=SETTINGS["db_user"],
        password=SETTINGS["db_password"],
        database=SETTINGS["db_name"],
        host=SETTINGS["db_host"],
        port=SETTINGS["db_port"],
        min_size=1,
        max_size=10,
    )
    print("✅ Database pool created")

    await init_database()

    yield

    await DB_POOL.close()
    print("🔴 Database pool closed")


app = FastAPI(
    title="CV Analytics API",
    description="Sistema de tracking para el CV de José Hernán Varela",
    version="2.0.0",
    lifespan=lifespan,
    # La documentación interactiva queda deshabilitada: expone el inventario
    # completo de la API sin aportar nada en producción.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# CORS restringido al dominio propio
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://devapis.cloud",
        "http://localhost:8000",
        "http://localhost",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)


def parse_user_agent(ua_string: str) -> dict:
    """Parse básico de user agent (sin librería externa)."""
    ua_lower = ua_string.lower()

    # Detectar navegador
    if "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    else:
        browser = "Unknown"

    # Detectar OS
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac" in ua_lower or "darwin" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    else:
        os_name = "Unknown"

    # Detectar tipo de dispositivo
    mobile_keywords = ["mobile", "android", "iphone", "ipad", "phone", "tablet"]
    device_type = "Mobile" if any(kw in ua_lower for kw in mobile_keywords) else "Desktop"

    return {"browser": browser, "os": os_name, "device_type": device_type}


def to_venezuela_time(dt):
    """Convierte datetime UTC a hora de Venezuela (UTC-4)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    venezuela_tz = timezone(timedelta(hours=-4))
    return dt.astimezone(venezuela_tz)


# ============================================
# ENDPOINTS PÚBLICOS
# ============================================

@app.post("/api/track")
async def track_visit(request: Request):
    """
    Registra una visita al CV. Público (lo llama el frontend).

    La IP se anonimiza antes de tocar la base de datos: nunca se persiste
    en claro. El rate limiting vive en Traefik (ver docker-compose.yaml).
    """
    try:
        raw_ip = client_ip_from_request(request)
        ip_prefix, ip_hash = anonymize_ip(raw_ip)

        user_agent_string = request.headers.get("user-agent", "Unknown")
        ua_info = parse_user_agent(user_agent_string)

        referer = request.headers.get("referer")
        language = request.headers.get("accept-language", "Unknown")
        if language and "," in language:
            language = language.split(",")[0].strip()

        async with DB_POOL.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cv_visits (
                    ip_prefix, ip_hash, user_agent, browser, os,
                    device_type, referer, language, visited_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                ip_prefix,
                ip_hash,
                user_agent_string,
                ua_info["browser"],
                ua_info["os"],
                ua_info["device_type"],
                referer,
                language,
                datetime.now(timezone.utc).replace(tzinfo=None),
            )

        return {
            "status": "tracked",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        # Se registra internamente, pero no se devuelve el detalle al cliente.
        print(f"❌ Error tracking visit: {e}")
        return {"status": "error"}


@app.get("/health")
async def health():
    """Health check. No revela detalles internos al cliente."""
    try:
        async with DB_POOL.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# ============================================
# ENDPOINTS AUTENTICADOS
# ============================================

@app.get("/api/analytics")
async def get_analytics(_user: str = Depends(require_analytics_auth)):
    """Estadísticas agregadas de visitas. Requiere autenticación."""
    async with DB_POOL.acquire() as conn:
        total_visits = await conn.fetchval("SELECT COUNT(*) FROM cv_visits")

        unique_visitors = await conn.fetchval(
            "SELECT COUNT(DISTINCT ip_hash) FROM cv_visits"
        )

        recent_visits = await conn.fetchval("""
            SELECT COUNT(*) FROM cv_visits
            WHERE visited_at > NOW() - INTERVAL '7 days'
        """)

        today_visits = await conn.fetchval("""
            SELECT COUNT(*) FROM cv_visits
            WHERE visited_at::date = CURRENT_DATE
        """)

        top_browsers = await conn.fetch("""
            SELECT browser, COUNT(*) as count
            FROM cv_visits
            GROUP BY browser
            ORDER BY count DESC
            LIMIT 5
        """)

        # Redes de origen (prefijo truncado), no IPs individuales.
        top_networks = await conn.fetch("""
            SELECT
                ip_prefix,
                COUNT(*) as visits,
                MAX(visited_at) as last_visit
            FROM cv_visits
            WHERE ip_prefix IS NOT NULL
            GROUP BY ip_prefix
            ORDER BY visits DESC
            LIMIT 10
        """)

        device_stats = await conn.fetch("""
            SELECT device_type, COUNT(*) as count
            FROM cv_visits
            GROUP BY device_type
        """)

        os_stats = await conn.fetch("""
            SELECT os, COUNT(*) as count
            FROM cv_visits
            GROUP BY os
            ORDER BY count DESC
            LIMIT 5
        """)

        daily_visits = await conn.fetch("""
            SELECT
                DATE(visited_at) as date,
                COUNT(*) as visits
            FROM cv_visits
            WHERE visited_at > NOW() - INTERVAL '30 days'
            GROUP BY DATE(visited_at)
            ORDER BY date DESC
        """)

    return {
        "summary": {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "recent_visits_7d": recent_visits,
            "today_visits": today_visits,
        },
        "top_browsers": [dict(r) for r in top_browsers],
        "top_networks": [
            {
                "ip_prefix": r["ip_prefix"],
                "visits": r["visits"],
                "last_visit": to_venezuela_time(r["last_visit"]).isoformat()
                if r["last_visit"]
                else None,
            }
            for r in top_networks
        ],
        "device_stats": [dict(r) for r in device_stats],
        "os_stats": [dict(r) for r in os_stats],
        "daily_visits": [
            {"date": r["date"].isoformat(), "visits": r["visits"]}
            for r in daily_visits
        ],
    }


@app.get("/api/analytics/recent")
async def get_recent_visits(
    limit: int = Query(20, ge=1, le=100),
    _user: str = Depends(require_analytics_auth),
):
    """Visitas recientes. Requiere autenticación."""
    async with DB_POOL.acquire() as conn:
        visits = await conn.fetch("""
            SELECT
                ip_prefix,
                browser,
                os,
                device_type,
                referer,
                language,
                visited_at
            FROM cv_visits
            ORDER BY visited_at DESC
            LIMIT $1
        """, limit)

    return {
        "visits": [
            {
                **dict(v),
                "visited_at": to_venezuela_time(v["visited_at"]).isoformat(),
            }
            for v in visits
        ]
    }


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(_user: str = Depends(require_analytics_auth)):
    """Dashboard HTML. Requiere autenticación."""
    return HTMLResponse(content=DASHBOARD_HTML)


# El dashboard construye el DOM con createElement/textContent en lugar de
# innerHTML: cualquier valor procedente de una petición se trata como texto,
# nunca como marcado.
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>CV Analytics Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a;
            color: #f1f5f9;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 0.5rem; color: #0ea5e9; }
        .privacy-note {
            color: #94a3b8;
            font-size: 0.875rem;
            margin-bottom: 2rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: #1e293b;
            padding: 1.5rem;
            border-radius: 0.5rem;
            border: 1px solid #334155;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #0ea5e9;
            margin-bottom: 0.5rem;
        }
        .stat-label { color: #94a3b8; font-size: 0.875rem; }
        .section {
            background: #1e293b;
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid #334155;
            overflow-x: auto;
        }
        .section h2 { margin-bottom: 1rem; color: #e2e8f0; font-size: 1.25rem; }
        table { width: 100%; border-collapse: collapse; }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #334155;
        }
        th { color: #94a3b8; font-weight: 600; }
        .refresh-btn {
            background: #0ea5e9;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 1rem;
            margin-bottom: 1rem;
        }
        .refresh-btn:hover { background: #0284c7; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 CV Analytics Dashboard</h1>
        <p class="privacy-note">
            Las IPs no se almacenan. Se muestran redes de origen truncadas
            (/24 en IPv4, /48 en IPv6); los visitantes únicos se cuentan
            mediante un hash con sal.
        </p>

        <button class="refresh-btn" id="refresh">🔄 Actualizar</button>

        <div class="stats-grid" id="stats-grid"></div>

        <div class="section">
            <h2>Top Navegadores</h2>
            <table id="browsers-table"></table>
        </div>

        <div class="section">
            <h2>Redes de Origen</h2>
            <table id="networks-table"></table>
        </div>

        <div class="section">
            <h2>Dispositivos</h2>
            <table id="devices-table"></table>
        </div>

        <div class="section">
            <h2>Visitas Recientes</h2>
            <table id="recent-table"></table>
        </div>
    </div>

    <script>
        // Todo el contenido dinámico se inserta con textContent.
        function renderTable(tableId, headers, rows) {
            const table = document.getElementById(tableId);
            table.replaceChildren();

            const headRow = document.createElement('tr');
            for (const label of headers) {
                const th = document.createElement('th');
                th.textContent = label;
                headRow.appendChild(th);
            }
            table.appendChild(headRow);

            for (const cells of rows) {
                const tr = document.createElement('tr');
                for (const value of cells) {
                    const td = document.createElement('td');
                    td.textContent = value === null || value === undefined ? '—' : String(value);
                    tr.appendChild(td);
                }
                table.appendChild(tr);
            }
        }

        function renderStats(summary) {
            const grid = document.getElementById('stats-grid');
            grid.replaceChildren();

            const cards = [
                [summary.total_visits, 'Visitas Totales'],
                [summary.unique_visitors, 'Visitantes Únicos'],
                [summary.recent_visits_7d, 'Últimos 7 Días'],
                [summary.today_visits, 'Hoy']
            ];

            for (const [value, label] of cards) {
                const card = document.createElement('div');
                card.className = 'stat-card';

                const valueEl = document.createElement('div');
                valueEl.className = 'stat-value';
                valueEl.textContent = value;

                const labelEl = document.createElement('div');
                labelEl.className = 'stat-label';
                labelEl.textContent = label;

                card.append(valueEl, labelEl);
                grid.appendChild(card);
            }
        }

        function formatDate(value) {
            if (!value) return '—';
            const date = new Date(value);
            return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('es');
        }

        async function loadData() {
            try {
                const [analytics, recent] = await Promise.all([
                    fetch('/api/analytics', { credentials: 'same-origin' }).then(r => r.json()),
                    fetch('/api/analytics/recent?limit=10', { credentials: 'same-origin' }).then(r => r.json())
                ]);

                renderStats(analytics.summary);

                renderTable('browsers-table', ['Navegador', 'Visitas'],
                    analytics.top_browsers.map(b => [b.browser, b.count]));

                renderTable('networks-table', ['Red (truncada)', 'Visitas', 'Última Visita'],
                    analytics.top_networks.map(n => [n.ip_prefix, n.visits, formatDate(n.last_visit)]));

                renderTable('devices-table', ['Dispositivo', 'Visitas'],
                    analytics.device_stats.map(d => [d.device_type, d.count]));

                renderTable('recent-table', ['Red', 'Navegador', 'OS', 'Dispositivo', 'Fecha'],
                    recent.visits.map(v => [v.ip_prefix, v.browser, v.os, v.device_type, formatDate(v.visited_at)]));
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }

        document.getElementById('refresh').addEventListener('click', loadData);
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""
