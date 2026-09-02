"""
Contrato de la API: la forma exacta de cada respuesta.

Antes las rutas devolvían diccionarios montados a mano y la forma de la API no
estaba escrita en ningún sitio. Con modelos, un campo mal escrito falla en el
test y no en el panel; y como `/docs` está deshabilitado, esto es además la
única documentación del contrato.

Las fechas se guardan en UTC y se sirven en hora de Venezuela. La conversión
vive en `DisplayDateTime`, un solo tipo compartido por todos los campos de
fecha, para que nadie tenga que acordarse de convertir.
"""
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

from .timeutils import to_venezuela_time

DisplayDateTime = Annotated[
    datetime,
    PlainSerializer(lambda dt: to_venezuela_time(dt).isoformat(), return_type=str),
]


# ---------------------------------------------------------------- públicas

class TrackResponse(BaseModel):
    status: str
    timestamp: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str


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
    last_visit: DisplayDateTime | None


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
    visited_at: DisplayDateTime


class RecentResponse(BaseModel):
    visits: list[RecentVisit]
