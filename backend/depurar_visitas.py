#!/usr/bin/env python3
"""
DEPURACIÓN: retira el User-Agent y el referente de las visitas antiguas.

Por qué
-------
La tabla crece sin límite y `user_agent` es, con diferencia, el campo con más
entropía de cada fila: la cadena completa identifica una combinación de
navegador, versión y sistema mucho más estrecha que cualquier otra cosa que se
guarde. Conservarla indefinidamente contradice la promesa del pie del CV, que
es no poder reidentificar a nadie.

Qué se pierde y qué se conserva
-------------------------------
Se conservan `browser`, `os` y `device_type`, que es lo que alimenta las
estadísticas, y por supuesto el prefijo de red y el hash. Se pierde la cadena
original, con dos consecuencias que conviene saber:

- `migrar_user_agents.py` ya no podrá recalcular esas filas. Ejecútalo antes si
  alguna vez cambia `parse_user_agent`.
- Un navegador nuevo no se podrá reclasificar hacia atrás en esas visitas.

Uso
---
    set -a; . ./.env; set +a
    python backend/depurar_visitas.py                 # simulacro
    python backend/depurar_visitas.py --aplicar       # escribe
    python backend/depurar_visitas.py --meses 12 --aplicar

Desde el contenedor:

    docker compose exec analytics-api python /app/depurar_visitas.py --aplicar
"""

import argparse

from mantenimiento import avisar_simulacro, conectar, ejecutar_script

MESES_POR_DEFECTO = 24

CONTAR = """
    SELECT COUNT(*) FROM cv_visits
    WHERE visited_at < NOW() - ($1 || ' months')::interval
      AND (user_agent IS NOT NULL OR referer IS NOT NULL)
"""

DEPURAR = """
    UPDATE cv_visits SET user_agent = NULL, referer = NULL
    WHERE visited_at < NOW() - ($1 || ' months')::interval
      AND (user_agent IS NOT NULL OR referer IS NOT NULL)
"""


async def ejecutar(argumentos: argparse.Namespace) -> int:
    meses = str(argumentos.meses)
    conexion = await conectar()

    try:
        total = await conexion.fetchval("SELECT COUNT(*) FROM cv_visits")
        afectadas = await conexion.fetchval(CONTAR, meses)

        print(f"Visitas en la base: {total}")
        print(f"Con más de {meses} meses y datos que depurar: {afectadas}")

        if not afectadas:
            print("✅ Nada que depurar.")
            return 0

        if not argumentos.aplicar:
            avisar_simulacro()
            return 0

        # En una transacción: o se depuran todas o ninguna. A medias no habría
        # forma de saber qué filas quedaron con la cadena original.
        async with conexion.transaction():
            await conexion.execute(DEPURAR, meses)

        print(f"\n✅ {afectadas} visitas depuradas.")
        return 0
    finally:
        await conexion.close()


def opciones(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--meses",
        type=int,
        default=MESES_POR_DEFECTO,
        help=f"antigüedad a partir de la cual depurar (por defecto {MESES_POR_DEFECTO})",
    )


if __name__ == "__main__":
    raise SystemExit(
        ejecutar_script("Retira user_agent y referer de las visitas antiguas.", ejecutar, opciones)
    )
