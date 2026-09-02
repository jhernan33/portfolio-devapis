"""
Contrato de la API: la forma exacta de cada respuesta.

Antes las rutas devolvían diccionarios montados a mano y la forma de la API no
estaba escrita en ningún sitio. Con modelos, un campo mal escrito falla en el
test y no en el panel; y como `/docs` está deshabilitado, esto es además la
única documentación del contrato.

Las fechas se guardan en UTC y se sirven en la zona de ANALYTICS_DISPLAY_TZ.
La conversión la hace el repositorio, que es quien tiene la configuración: si
viviera aquí, en una anotación de tipo, habría que leerla de una variable
global, que es justo lo que se quitó del backend.

Los modelos reciben datetimes que ya saben en qué zona están, y Pydantic los
serializa en ISO-8601 con su desplazamiento.
"""

from datetime import date, datetime

from pydantic import BaseModel

# ---------------------------------------------------------------- públicas


class TrackResponse(BaseModel):
    status: str
    timestamp: str | None = None


class HealthResponse(BaseModel):
    """
    Respuesta del health check público. Solo dice si el servicio atiende.

    No detalla el estado de la base: es una ruta abierta a cualquiera y no hay
    razón para publicar qué componente concreto está caído. El diagnóstico
    completo vive en /api/analytics/health, tras autenticación.
    """

    status: str


# ---------------------------------------------------------------- estadísticas


class Summary(BaseModel):
    total_visits: int
    unique_visitors: int
    recent_visits_7d: int
    today_visits: int


class BrowserCount(BaseModel):
    browser: str | None
    count: int


class NetworkCount(BaseModel):
    """Redes de origen (prefijo truncado), nunca IPs individuales."""

    ip_prefix: str
    visits: int
    last_visit: datetime | None


class DeviceCount(BaseModel):
    device_type: str | None
    count: int


class OsCount(BaseModel):
    os: str | None
    count: int


class DailyCount(BaseModel):
    date: date
    visits: int


class AnalyticsResponse(BaseModel):
    summary: Summary
    top_browsers: list[BrowserCount]
    top_networks: list[NetworkCount]
    device_stats: list[DeviceCount]
    os_stats: list[OsCount]
    daily_visits: list[DailyCount]


class RecentVisit(BaseModel):
    ip_prefix: str | None
    browser: str | None
    os: str | None
    device_type: str | None
    referer: str | None
    language: str | None
    is_internal: bool
    visited_at: datetime


class RecentResponse(BaseModel):
    visits: list[RecentVisit]


class DiagnosticsResponse(BaseModel):
    """Diagnóstico detallado. Autenticado: dice más de lo que conviene publicar."""

    status: str
    visits_total: int
    visits_internal: int
    last_visit: datetime | None
    pool_size: int
    pool_idle: int
