#!/usr/bin/env python3
"""
MIGRACIÓN: recalcular navegador, sistema y dispositivo de las visitas antiguas.

Contexto
--------
`parse_user_agent` tenía mal el orden de sus comprobaciones. Cada cadena de
User-Agent contiene varias pistas a la vez y gana la primera que se mira, así
que Opera se registraba como Chrome, Android como Linux e iOS como macOS: ni
una sola visita desde un móvil se guardó nunca con su sistema real.

El arreglo solo afecta a las visitas nuevas. Este script corrige las que ya
están guardadas, que se puede porque `user_agent` conserva la cadena completa:
basta con volver a derivar las tres columnas a partir de ella.

Por qué en Python y no en SQL
-----------------------------
Reimplementar el parseo en SQL significaría mantener dos copias de la lógica
que acaba de demostrar lo fácil que es equivocarse en ella. Aquí se importa la
misma función que usa el servicio, de modo que la migración no puede
discrepar del código en producción.

Seguridad
---------
- Por defecto NO escribe: enseña lo que cambiaría y termina. Hay que pasar
  `--aplicar` explícitamente. Una operación sobre datos de producción no debe
  ocurrir por inercia.
- Es idempotente: recalcular es determinista, así que ejecutarlo dos veces
  deja la segunda vez cero cambios.
- Solo toca `browser`, `os` y `device_type`. No lee ni escribe nada
  relacionado con IPs.

Uso
---
    set -a; . ./.env; set +a
    python backend/migrar_user_agents.py              # simulacro
    python backend/migrar_user_agents.py --aplicar    # escribe

Desde el contenedor, si no hay Python con asyncpg en el host:

    docker compose exec analytics-api python /app/migrar_user_agents.py --aplicar

(requiere que la imagen incluya este fichero; si no, cópialo con `docker cp`).
"""

import argparse
from collections import Counter

from app.useragent import parse_user_agent
from mantenimiento import avisar_simulacro, conectar, ejecutar_script

# Solo estas tres columnas se derivan del User-Agent.
CAMPOS = ("browser", "os", "device_type")


def recalcular(filas):
    """
    Devuelve las correcciones necesarias, sin tocar la base.

    Separado del acceso a datos a propósito: es la parte con lógica, y así se
    puede probar sin levantar PostgreSQL.

    Cada elemento es `(id, browser, os, device_type)`. Las filas que ya están
    bien no se devuelven: no tiene sentido reescribir una fila para dejarla
    igual, y así el recuento final dice algo real.
    """
    correcciones = []
    for fila in filas:
        agente = fila["user_agent"]
        if not agente:
            # Sin la cadena original no hay nada de donde derivar. Se deja como
            # está en lugar de sobrescribir con "Unknown": lo que hay guardado,
            # aunque sea impreciso, es más de lo que se puede recuperar.
            continue

        nuevo = parse_user_agent(agente)
        if any(nuevo[c] != fila[c] for c in CAMPOS):
            correcciones.append((fila["id"], *(nuevo[c] for c in CAMPOS)))

    return correcciones


def resumir(filas, correcciones):
    """Qué cambia y en qué cantidad, para poder revisarlo antes de aplicar."""
    por_id = {c[0]: c for c in correcciones}
    cambios = Counter()
    for fila in filas:
        correccion = por_id.get(fila["id"])
        if not correccion:
            continue
        _, navegador, sistema, dispositivo = correccion
        if fila["browser"] != navegador:
            cambios[f"navegador: {fila['browser']} → {navegador}"] += 1
        if fila["os"] != sistema:
            cambios[f"sistema: {fila['os']} → {sistema}"] += 1
        if fila["device_type"] != dispositivo:
            cambios[f"dispositivo: {fila['device_type']} → {dispositivo}"] += 1
    return cambios


async def ejecutar(argumentos: argparse.Namespace) -> int:
    conexion = await conectar()

    try:
        filas = await conexion.fetch(
            "SELECT id, user_agent, browser, os, device_type FROM cv_visits"
        )
        print(f"Visitas en la base: {len(filas)}")

        correcciones = recalcular(filas)
        if not correcciones:
            print("✅ Nada que corregir: todas las filas ya coinciden con el parseo actual.")
            return 0

        print(f"Filas a corregir: {len(correcciones)}\n")
        for descripcion, cuantas in resumir(filas, correcciones).most_common():
            print(f"  {cuantas:>5}  {descripcion}")

        if not argumentos.aplicar:
            avisar_simulacro()
            return 0

        # En una transacción: o se corrigen todas o ninguna. Dejar la tabla a
        # medias sería peor que no haber empezado, porque no habría forma de
        # saber qué filas quedaron sin migrar.
        async with conexion.transaction():
            await conexion.executemany(
                """
                UPDATE cv_visits
                SET browser = $2, os = $3, device_type = $4
                WHERE id = $1
                """,
                correcciones,
            )
        print(f"\n✅ {len(correcciones)} filas corregidas.")
        return 0

    finally:
        await conexion.close()


if __name__ == "__main__":
    raise SystemExit(
        ejecutar_script("Recalcula browser/os/device_type de las visitas ya guardadas.", ejecutar)
    )
