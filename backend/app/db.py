"""
Pool de conexiones, esquema y migraciones de instalaciones anteriores.

El esquema vive aquí y en database/init-analytics.sql, y tienen que coincidir
(lo vigila la CI). Si cambias una columna, cámbiala en los dos.
"""
import ipaddress

import asyncpg

from .config import Settings
from .privacy import anonymize_ip

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
    -- Tráfico propio: red interna, health checks y el servidor llamándose a
    -- sí mismo. Se guarda igualmente, porque sirve para diagnosticar, pero
    -- queda fuera de las estadísticas.
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    visited_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Migración para instalaciones anteriores que aún tienen ip_address
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_prefix VARCHAR(45);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_hash CHAR(64);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS is_internal BOOLEAN NOT NULL DEFAULT FALSE;

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

-- Índice parcial: todas las consultas de estadísticas filtran por
-- `NOT is_internal`, así que el índice solo cubre esas filas.
CREATE INDEX IF NOT EXISTS idx_cv_visits_externas
    ON cv_visits(visited_at DESC) WHERE NOT is_internal;

-- Vista para analytics rápidos.
-- Se recrea sobre ip_hash para eliminar la dependencia con ip_address y
-- permitir que la columna antigua pueda purgarse.
--
-- Excluye el tráfico interno. En la primera medición con tráfico real, de 23
-- visitas registradas 16 eran navegación propia o comprobaciones lanzadas
-- desde el propio servidor: el 70%. Contarlas convierte la única métrica que
-- el CV usa para medirse en ruido.
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_hash) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') as visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d,
    COUNT(*) FILTER (WHERE visited_at::date = CURRENT_DATE) as visits_today
FROM cv_visits
WHERE NOT is_internal;
"""


async def create_pool(settings: Settings):
    return await asyncpg.create_pool(
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        host=settings.db_host,
        port=settings.db_port,
        min_size=1,
        max_size=10,
    )


async def backfill_anonymized_ips(conn, salt: str) -> int:
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
        prefix, digest = anonymize_ip(row["ip_address"], salt)
        updates.append((prefix, digest, row["id"]))

    await conn.executemany(
        "UPDATE cv_visits SET ip_prefix = $1, ip_hash = $2 WHERE id = $3",
        updates,
    )
    return len(updates)


async def backfill_internal_flag(conn, ignore_networks) -> int:
    """
    Marca como internas las visitas anteriores a que existiera la columna.

    Limitación conocida: de las filas antiguas solo queda `ip_prefix`, la red
    ya truncada a /24, no la IP original. Así que en lugar de comprobar
    pertenencia se comprueba SOLAPAMIENTO con las redes a ignorar: si la lista
    trae `195.26.247.93/32`, el prefijo `195.26.247.0` no está *dentro* de esa
    /32, pero sí se solapa con ella.

    Es más grosero que la comprobación en tiempo de registro, que sí usa la IP
    exacta. Para filas históricas es el precio de no haber guardado la IP —que
    es exactamente lo que se quería— y a cambio marca de más, nunca de menos.
    """
    filas = await conn.fetch("""
        SELECT id, ip_prefix FROM cv_visits
        WHERE NOT is_internal AND ip_prefix IS NOT NULL
    """)
    if not filas:
        return 0

    marcar = []
    for fila in filas:
        try:
            red = ipaddress.ip_network(f"{fila['ip_prefix']}/24", strict=False)
        except ValueError:
            continue
        ip = red.network_address
        interna = (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or any(red.overlaps(otra) for otra in ignore_networks)
        )
        if interna:
            marcar.append(fila["id"])

    if not marcar:
        return 0

    await conn.execute(
        "UPDATE cv_visits SET is_internal = TRUE WHERE id = ANY($1::int[])", marcar
    )
    return len(marcar)


async def init_database(pool, settings: Settings) -> None:
    """Inicializa el esquema y migra instalaciones anteriores."""
    async with pool.acquire() as conn:
        await conn.execute(DDL_SCRIPT)
        print("✅ Database schema initialized")

        migrated = await backfill_anonymized_ips(conn, settings.ip_salt)
        if migrated:
            print(f"✅ {migrated} visitas antiguas anonimizadas")
            print("   Ejecuta database/migrate-anonymize-ips.sql para purgar ip_address")

        internas = await backfill_internal_flag(conn, settings.ignore_networks)
        if internas:
            print(f"✅ {internas} visitas marcadas como tráfico interno")

        if settings.ignore_networks:
            redes = ", ".join(str(r) for r in settings.ignore_networks)
            print(f"ℹ️  Redes excluidas del conteo: {redes}")
        else:
            print("ℹ️  ANALYTICS_IGNORE_NETWORKS sin definir: solo se excluyen "
                  "los rangos privados, no la IP pública de este servidor")
