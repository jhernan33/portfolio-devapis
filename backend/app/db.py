"""
Pool de conexiones y puesta a punto de la base al arrancar.

El esquema ya no vive aquí: está en `migrations/`, versionado y anotado en la
tabla `schema_migrations` (ver `app/migrations.py`). Este módulo solo abre el
pool y encadena lo que hay que hacer en cada arranque.
"""

import ipaddress

import asyncpg

from .config import Settings
from .logs import LOGGER
from .migrations import aplicar_migraciones


async def create_pool(settings: Settings):
    return await asyncpg.create_pool(
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        host=settings.db_host,
        port=settings.db_port,
        min_size=1,
        max_size=10,
        # La sesión trabaja en UTC pase lo que pase en el servidor. Sin esto,
        # `NOW()` y cualquier conversión dependían de la zona del contenedor de
        # PostgreSQL, que nadie fija y que puede cambiar al recrearlo. Los
        # cortes por día se calculan explícitamente en ANALYTICS_DISPLAY_TZ,
        # que es una decisión del producto, no un accidente del despliegue.
        server_settings={"timezone": "UTC"},
    )


async def reconciliar_trafico_interno(conn, ignore_networks) -> int:
    """
    Marca como internas las visitas que hoy encajarían en las redes a ignorar.

    NO es una migración, y por eso corre en cada arranque en lugar de una sola
    vez: `ANALYTICS_IGNORE_NETWORKS` cambia. El caso que la justifica es
    encontrar meses después que la IP pública del propio servidor llevaba
    contándose como visitante; al añadirla a la lista, esto repara lo ya
    registrado. Una migración anotada como aplicada no volvería a mirar.

    Limitación conocida: de las filas antiguas solo queda `ip_prefix`, la red
    ya truncada a /24, no la IP original. Así que en lugar de comprobar
    pertenencia se comprueba SOLAPAMIENTO: si la lista trae `195.26.247.93/32`,
    el prefijo `195.26.247.0` no está *dentro* de esa /32, pero sí se solapa
    con ella. Es más grosero que la comprobación en tiempo de registro, que sí
    usa la IP exacta; a cambio marca de más, nunca de menos, que es el lado
    correcto por el que equivocarse cuando lo que se mide son visitas propias.
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
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or any(red.overlaps(otra) for otra in ignore_networks)
        )
        if interna:
            marcar.append(fila["id"])

    if not marcar:
        return 0

    await conn.execute("UPDATE cv_visits SET is_internal = TRUE WHERE id = ANY($1::int[])", marcar)
    return len(marcar)


async def init_database(pool, settings: Settings) -> None:
    """Migra el esquema y reconcilia lo que dependa de la configuración actual."""
    await aplicar_migraciones(pool, settings)

    async with pool.acquire() as conn:
        internas = await reconciliar_trafico_interno(conn, settings.ignore_networks)
        if internas:
            LOGGER.info("%d visitas marcadas como tráfico interno", internas)

    if settings.ignore_networks:
        LOGGER.info(
            "Redes excluidas del conteo: %s",
            ", ".join(str(r) for r in settings.ignore_networks),
        )
    else:
        LOGGER.warning(
            "ANALYTICS_IGNORE_NETWORKS sin definir: solo se excluyen los "
            "rangos privados, no la IP pública de este servidor"
        )
