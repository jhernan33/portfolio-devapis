"""
Andamiaje común de los scripts que tocan datos de producción.

Existe para que las dos operaciones de mantenimiento —recalcular User-Agents y
depurar visitas antiguas— compartan exactamente el mismo contrato en lugar de
copiarlo. El contrato es el que importa:

- **Por defecto no escriben.** Enseñan lo que harían y terminan. Hay que pasar
  `--aplicar`. Una operación sobre datos de producción no debe ocurrir por
  inercia ni por recuperar un comando del historial.
- **La configuración sale del entorno**, la misma que usa el servicio, así que
  no hay una segunda copia de las credenciales.
- **Un fallo de configuración se cuenta, no se vuelca.** Quien ejecuta esto
  suele estar dentro de un contenedor, con prisa.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable

import asyncpg

from app.config import load_settings


async def conectar() -> asyncpg.Connection:
    """Conexión suelta con las credenciales del servicio."""
    ajustes = load_settings()
    return await asyncpg.connect(
        user=ajustes.db_user,
        password=ajustes.db_password,
        database=ajustes.db_name,
        host=ajustes.db_host,
        port=ajustes.db_port,
        server_settings={"timezone": "UTC"},
    )


def ejecutar_script(
    descripcion: str,
    tarea: Callable[[argparse.Namespace], Awaitable[int]],
    opciones: Callable[[argparse.ArgumentParser], None] | None = None,
) -> int:
    """
    Monta la línea de órdenes, ejecuta la tarea y traduce los fallos esperados.

    `tarea` recibe los argumentos ya leídos y devuelve el código de salida.
    """
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="escribe los cambios; sin esta opción solo se muestran",
    )
    if opciones:
        opciones(parser)

    argumentos = parser.parse_args()

    try:
        return asyncio.run(tarea(argumentos))
    except RuntimeError as error:  # falta configuración
        print(f"❌ {error}", file=sys.stderr)
        return 1


def avisar_simulacro() -> None:
    print("\nSimulacro: no se ha escrito nada.")
    print("Vuelve a lanzarlo con --aplicar para guardar los cambios.")
