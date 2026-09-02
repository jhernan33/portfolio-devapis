"""
Migraciones de esquema.

Antes el DDL vivía duplicado en el código y en `database/init-analytics.sql`,
con una guarda de CI que solo comprobaba que las dos copias siguieran
pareciéndose. Cambiar una columna existente no lo cubría ningún `CREATE TABLE
IF NOT EXISTS`, así que cada cambio real acababa en un script SQL suelto
ejecutado a mano contra producción y recordado por quien estuviera delante.

Aquí hay una sola fuente de verdad —el directorio `migrations/`— y una tabla
que anota lo aplicado. Sin dependencias nuevas: son cuarenta líneas y un
`CREATE TABLE`, no hacía falta traerse Alembic para una tabla.

Reglas:

- Los ficheros se aplican en orden alfabético, que con el prefijo numérico es
  el orden cronológico. Nunca se edita una migración ya aplicada: se añade otra.
- Cada una corre dentro de una transacción. En PostgreSQL el DDL es
  transaccional, así que una migración a medias no existe.
- Una migración de Python es para lo que no se puede expresar en SQL, como
  derivar un hash con sal. Comparte numeración con las de SQL.
"""

import pathlib

from .config import Settings
from .logs import LOGGER
from .privacy import anonymize_ip
from .useragent import es_bot

DIRECTORIO = pathlib.Path(__file__).resolve().parent.parent / "migrations"

TABLA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


async def _anonimizar_ips_heredadas(conn, settings: Settings) -> str:
    """
    Rellena ip_prefix/ip_hash de las filas que aún tengan ip_address en claro.

    No borra la columna: la purga es irreversible y sigue siendo un paso
    explícito y manual (`database/migrate-anonymize-ips.sql`). Esta migración
    solo garantiza que no quede ninguna fila sin su versión anonimizada antes
    de que alguien decida purgar.
    """
    hay_columna = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
        )
    """)
    if not hay_columna:
        return "sin columna heredada"

    filas = await conn.fetch("""
        SELECT id, ip_address FROM cv_visits
        WHERE ip_hash IS NULL AND ip_address IS NOT NULL
    """)
    if not filas:
        return "nada que anonimizar"

    await conn.executemany(
        "UPDATE cv_visits SET ip_prefix = $1, ip_hash = $2 WHERE id = $3",
        [(*anonymize_ip(f["ip_address"], settings.ip_salt), f["id"]) for f in filas],
    )
    return f"{len(filas)} visitas anonimizadas; ya se puede purgar ip_address"


async def _marcar_bots_heredados(conn, _settings: Settings) -> str:
    """
    Reclasifica las visitas ya guardadas usando la misma función que el
    servicio, no una copia en SQL: mantener dos veces la lista de rastreadores
    es garantizar que se separen.

    Las filas cuyo `user_agent` ya se depuró por retención no se pueden
    clasificar y se quedan como están. Es preferible a inventar: lo guardado,
    aunque sea impreciso, es más de lo que se puede recuperar.
    """
    filas = await conn.fetch(
        "SELECT id, user_agent FROM cv_visits WHERE NOT is_bot AND user_agent IS NOT NULL"
    )
    marcar = [f["id"] for f in filas if es_bot(f["user_agent"])]
    if not marcar:
        return "ninguna visita antigua era un rastreador"

    await conn.execute("UPDATE cv_visits SET is_bot = TRUE WHERE id = ANY($1::int[])", marcar)
    return f"{len(marcar)} visitas antiguas marcadas como rastreador"


# Comparten numeración con los ficheros .sql y se ordenan junto a ellos.
MIGRACIONES_PYTHON = {
    "0003_anonimizar_ips_heredadas": _anonimizar_ips_heredadas,
    "0005_marcar_bots_heredados": _marcar_bots_heredados,
}


def migraciones_disponibles() -> list[str]:
    """Versiones conocidas, en el orden en que deben aplicarse."""
    sql = [f.stem for f in DIRECTORIO.glob("*.sql")]
    return sorted(sql + list(MIGRACIONES_PYTHON))


async def aplicar_migraciones(pool, settings: Settings) -> list[str]:
    """Aplica las pendientes y devuelve las versiones aplicadas en esta pasada."""
    aplicadas_ahora = []

    async with pool.acquire() as conn:
        await conn.execute(TABLA)
        ya = {f["version"] for f in await conn.fetch("SELECT version FROM schema_migrations")}

        for version in migraciones_disponibles():
            if version in ya:
                continue

            async with conn.transaction():
                if version in MIGRACIONES_PYTHON:
                    detalle = await MIGRACIONES_PYTHON[version](conn, settings)
                else:
                    await conn.execute((DIRECTORIO / f"{version}.sql").read_text(encoding="utf-8"))
                    detalle = "SQL aplicado"
                await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", version)

            LOGGER.info("Migración %s: %s", version, detalle)
            aplicadas_ahora.append(version)

    if not aplicadas_ahora:
        LOGGER.info("Esquema al día: %d migraciones ya aplicadas", len(ya))

    return aplicadas_ahora
