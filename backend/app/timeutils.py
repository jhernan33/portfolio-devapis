"""
Conversión de las fechas almacenadas (UTC) a la zona de presentación.

La zona sale de la configuración, no del código: el titular puede cambiar de
país y eso no debería ser un cambio de fuente. Se usa en dos sitios y por dos
motivos distintos:

- Aquí, para que las fechas que devuelve la API se lean en hora local.
- En el SQL del repositorio, para que "hoy" signifique el día del titular y no
  el de UTC. Un CV consultado desde Caracas a las 21:00 cuenta como hoy, no
  como mañana.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .logs import LOGGER

ZONA_POR_DEFECTO = "America/Caracas"


def zona(nombre: str) -> ZoneInfo:
    """
    Resuelve un nombre de zona horaria. Si no existe, avisa y cae en UTC.

    Mismo criterio que con las redes a ignorar y el nivel de log: una variable
    de entorno mal escrita ensucia una presentación, pero no puede impedir que
    el servicio arranque.
    """
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        LOGGER.warning("ANALYTICS_DISPLAY_TZ: %r no es una zona conocida, se usa UTC", nombre)
        return ZoneInfo("UTC")


def to_display_time(dt: datetime | None, tz: ZoneInfo) -> datetime | None:
    """Convierte un datetime UTC (con o sin tzinfo) a la zona de presentación."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Solo debería ocurrir con filas anteriores a la migración a TIMESTAMPTZ.
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz)
