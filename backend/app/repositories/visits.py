"""
Repositorio de visitas: el único sitio que habla SQL con `cv_visits`.

Separar el SQL de las rutas permite probar cada capa por su lado y deja las
reglas de negocio en un solo lugar. La más importante: toda estadística
agregada filtra el tráfico propio (`EXTERNAS`). En la primera medición con
tráfico real, el 70% de las "visitas" era navegación propia o comprobaciones
lanzadas desde el propio servidor.

Devuelve directamente los modelos de `models.py`. No hay una capa de dominio
intermedia porque no hay lógica que la justifique: una tabla, un servicio.

Se acuñan conexiones del pool por método, nunca conexiones sueltas.

Las fechas salen de la base en UTC y se devuelven ya convertidas a la zona de
presentación. El corte por día de las consultas agregadas también se hace en
esa zona: "hoy" es el día del titular, no el de UTC, y con una diferencia de
cuatro horas eso decide en qué casilla cae toda visita de la tarde.
"""

from dataclasses import astuple, dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import (
    AnalyticsResponse,
    BrowserCount,
    DailyCount,
    DeviceCount,
    DiagnosticsResponse,
    NetworkCount,
    OsCount,
    RecentResponse,
    RecentVisit,
    Summary,
)
from ..timeutils import to_display_time

# Toda consulta agregada lleva este filtro. Definido una vez para que no se
# pueda olvidar en una consulta nueva.
EXTERNAS = "NOT is_internal"


@dataclass(frozen=True)
class Visit:
    """Una visita ya anonimizada, lista para persistir. El orden de los campos
    es el orden de las columnas del INSERT."""

    ip_prefix: str | None
    ip_hash: str | None
    user_agent: str
    browser: str
    os: str
    device_type: str
    referer: str | None
    language: str | None
    is_internal: bool
    visited_at: datetime


class VisitRepository:
    def __init__(self, pool, tz: ZoneInfo):
        self._pool = pool
        self._tz = tz

    @property
    def _tz_sql(self) -> str:
        """Nombre de la zona tal y como lo entiende `AT TIME ZONE` en PostgreSQL."""
        return self._tz.key

    def _local(self, dt):
        return to_display_time(dt, self._tz)

    async def ping(self) -> None:
        """Comprueba que la base responde. Lanza si no."""
        async with self._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

    async def diagnostics(self) -> DiagnosticsResponse:
        """
        Estado detallado para depurar. Requiere autenticación.

        Aquí sí interesa el tráfico interno: si algo no llega, lo primero que
        hay que saber es si no llega nada o si llega y se está descartando.
        """
        async with self._pool.acquire() as conn:
            fila = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE is_internal) AS internas,
                    MAX(visited_at) AS ultima
                FROM cv_visits
            """)

        return DiagnosticsResponse(
            status="healthy",
            visits_total=fila["total"],
            visits_internal=fila["internas"],
            # `or None`: con la tabla vacía no hay última visita, y el doble de
            # los tests devuelve 0 en lugar de una fecha.
            last_visit=self._local(fila["ultima"] or None),
            pool_size=self._pool.get_size(),
            pool_idle=self._pool.get_idle_size(),
        )

    async def record(self, visit: Visit) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cv_visits (
                    ip_prefix, ip_hash, user_agent, browser, os,
                    device_type, referer, language, is_internal, visited_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                *astuple(visit),
            )

    async def overview(self) -> AnalyticsResponse:
        """Estadísticas agregadas. Excluyen el tráfico interno."""
        async with self._pool.acquire() as conn:
            # Los cuatro contadores del resumen salen de una sola pasada por
            # la tabla, no de cuatro consultas.
            resumen = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total_visits,
                    COUNT(DISTINCT ip_hash) AS unique_visitors,
                    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days')
                        AS recent_visits_7d,
                    -- "Hoy" en la zona del titular. Con `visited_at::date` era
                    -- el día de la sesión de PostgreSQL, y una visita de las
                    -- ocho de la tarde en Caracas ya contaba como de mañana.
                    COUNT(*) FILTER (
                        WHERE (visited_at AT TIME ZONE $1)::date
                            = (NOW() AT TIME ZONE $1)::date
                    ) AS today_visits
                FROM cv_visits
                WHERE {EXTERNAS}
            """,
                self._tz_sql,
            )

            navegadores = await conn.fetch(f"""
                SELECT browser, COUNT(*) AS count
                FROM cv_visits
                WHERE {EXTERNAS}
                GROUP BY browser
                ORDER BY count DESC
                LIMIT 5
            """)

            # Redes de origen (prefijo truncado), no IPs individuales.
            redes = await conn.fetch(f"""
                SELECT ip_prefix, COUNT(*) AS visits, MAX(visited_at) AS last_visit
                FROM cv_visits
                WHERE {EXTERNAS} AND ip_prefix IS NOT NULL
                GROUP BY ip_prefix
                ORDER BY visits DESC
                LIMIT 10
            """)

            dispositivos = await conn.fetch(f"""
                SELECT device_type, COUNT(*) AS count
                FROM cv_visits
                WHERE {EXTERNAS}
                GROUP BY device_type
            """)

            sistemas = await conn.fetch(f"""
                SELECT os, COUNT(*) AS count
                FROM cv_visits
                WHERE {EXTERNAS}
                GROUP BY os
                ORDER BY count DESC
                LIMIT 5
            """)

            diarias = await conn.fetch(
                f"""
                SELECT (visited_at AT TIME ZONE $1)::date AS date, COUNT(*) AS visits
                FROM cv_visits
                WHERE {EXTERNAS} AND visited_at > NOW() - INTERVAL '30 days'
                GROUP BY 1
                ORDER BY date DESC
            """,
                self._tz_sql,
            )

        return AnalyticsResponse(
            # Por nombre de columna: deja escrito qué devuelve la consulta y
            # permite que el doble de los tests sirva una fila vacía en ceros.
            summary=Summary(
                total_visits=resumen["total_visits"],
                unique_visitors=resumen["unique_visitors"],
                recent_visits_7d=resumen["recent_visits_7d"],
                today_visits=resumen["today_visits"],
            ),
            top_browsers=[BrowserCount(**r) for r in navegadores],
            top_networks=[
                NetworkCount(
                    ip_prefix=r["ip_prefix"],
                    visits=r["visits"],
                    last_visit=self._local(r["last_visit"]),
                )
                for r in redes
            ],
            device_stats=[DeviceCount(**r) for r in dispositivos],
            os_stats=[OsCount(**r) for r in sistemas],
            daily_visits=[DailyCount(**r) for r in diarias],
        )

    async def recent(self, limit: int) -> RecentResponse:
        """
        Últimas visitas. A diferencia de las estadísticas, SÍ incluye el
        tráfico interno, marcado con `is_internal`.

        Es la única ventana a lo que está llegando de verdad: si se filtrara
        también aquí, en desarrollo local —donde todo es privado— el panel se
        vería vacío y sería imposible distinguir "no llega nada" de "llega y
        se está descartando".

        No expone `ip_hash`: identifica a un visitante entre visitas y no
        hace falta enseñarlo.
        """
        async with self._pool.acquire() as conn:
            filas = await conn.fetch(
                """
                SELECT
                    ip_prefix, browser, os, device_type,
                    referer, language, is_internal, visited_at
                FROM cv_visits
                ORDER BY visited_at DESC
                LIMIT $1
            """,
                limit,
            )

        return RecentResponse(
            visits=[RecentVisit(**{**f, "visited_at": self._local(f["visited_at"])}) for f in filas]
        )
