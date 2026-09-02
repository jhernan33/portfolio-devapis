"""Conversión de las fechas almacenadas (UTC) a la hora de presentación."""

from datetime import UTC, datetime, timedelta, timezone

VENEZUELA = timezone(timedelta(hours=-4))


def to_venezuela_time(dt: datetime | None) -> datetime | None:
    """Convierte un datetime UTC (con o sin tzinfo) a hora de Venezuela (UTC-4)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(VENEZUELA)
