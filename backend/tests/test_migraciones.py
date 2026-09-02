"""
Migraciones de esquema.

El esquema vivía duplicado en el código y en un .sql, y cambiar una columna
existente no lo cubría ningún `CREATE TABLE IF NOT EXISTS`: acababa en un
script suelto ejecutado a mano contra producción. Lo que hay que garantizar
aquí es que el orden sea el correcto, que nada se aplique dos veces y que una
migración que falla no quede anotada como hecha.
"""

import re

import pytest
from conftest import PoolFalso

from app import migrations
from app.config import Settings

AJUSTES = Settings(
    db_user="t",
    db_password="t",
    db_name="t",
    db_host="localhost",
    db_port=5432,
    analytics_user="u",
    analytics_password="c",
    ip_salt="sal",
)


# ============================================================
# El catálogo
# ============================================================


def test_las_versiones_estan_numeradas_y_ordenadas():
    versiones = migrations.migraciones_disponibles()
    assert versiones == sorted(versiones)
    assert all(re.match(r"^\d{4}_[a-z0-9_]+$", v) for v in versiones), versiones


def test_no_hay_huecos_ni_numeros_repetidos():
    """
    Un hueco casi siempre significa una migración que alguien borró tras
    aplicarla en su máquina; un número repetido, dos ramas que la añadieron a
    la vez. Las dos cosas dejan bases distintas creyendo estar al día.
    """
    numeros = [int(v.split("_")[0]) for v in migrations.migraciones_disponibles()]
    assert numeros == list(range(1, len(numeros) + 1)), numeros


def test_todo_fichero_sql_del_directorio_esta_en_el_catalogo():
    del_disco = {f.stem for f in migrations.DIRECTORIO.glob("*.sql")}
    assert del_disco <= set(migrations.migraciones_disponibles())


# ============================================================
# Aplicación
# ============================================================

# Sin marcas: `asyncio_mode = auto` en pytest.ini recoge los async por su cuenta.


async def test_sobre_una_base_virgen_se_aplican_todas(conexion):
    aplicadas = await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES)
    assert aplicadas == migrations.migraciones_disponibles()


async def test_se_anota_cada_una_al_aplicarla(conexion):
    await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES)
    anotadas = [
        args[0] for sql, args in conexion.ejecutados if "INSERT INTO schema_migrations" in sql
    ]
    assert anotadas == migrations.migraciones_disponibles()


async def test_lo_ya_aplicado_no_se_repite(conexion):
    """Arrancar dos veces no puede volver a tocar el esquema."""
    conexion.respuestas = {
        "SELECT version FROM schema_migrations": [
            {"version": v} for v in migrations.migraciones_disponibles()
        ]
    }
    assert await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES) == []


async def test_solo_se_aplica_lo_pendiente(conexion):
    todas = migrations.migraciones_disponibles()
    conexion.respuestas = {"SELECT version FROM schema_migrations": [{"version": todas[0]}]}
    assert await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES) == todas[1:]


async def test_la_tabla_de_control_se_crea_antes_de_nada(conexion):
    await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES)
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in conexion.ejecutados[0][0]


async def test_una_migracion_que_falla_no_queda_anotada(conexion, monkeypatch):
    """
    Si se anotara igualmente, la siguiente vez se daría por hecha y el esquema
    quedaría a medias para siempre, sin que nada volviera a intentarlo.
    """

    async def explota(_conn, _ajustes):
        raise RuntimeError("la migración falla")

    monkeypatch.setitem(migrations.MIGRACIONES_PYTHON, "0003_anonimizar_ips_heredadas", explota)

    with pytest.raises(RuntimeError):
        await migrations.aplicar_migraciones(PoolFalso(conexion), AJUSTES)

    anotadas = [
        args[0] for sql, args in conexion.ejecutados if "INSERT INTO schema_migrations" in sql
    ]
    assert "0003_anonimizar_ips_heredadas" not in anotadas


# ============================================================
# La migración de datos
# ============================================================


async def test_sin_columna_heredada_no_toca_nada(conexion):
    conexion.respuestas = {"information_schema.columns": False}
    detalle = await migrations._anonimizar_ips_heredadas(conexion, AJUSTES)
    assert "sin columna" in detalle
    assert not [s for s, _ in conexion.ejecutados if "UPDATE" in s]


async def test_las_ips_heredadas_se_anonimizan_con_la_sal(conexion):
    conexion.respuestas = {
        "information_schema.columns": True,
        "SELECT id, ip_address FROM cv_visits": [
            {"id": 1, "ip_address": "93.184.216.34"},
        ],
    }
    detalle = await migrations._anonimizar_ips_heredadas(conexion, AJUSTES)

    sql, args = conexion.ejecutados[-1]
    assert "UPDATE cv_visits SET ip_prefix" in sql
    prefijo, digest, id_ = args[0]
    assert (prefijo, len(digest), id_) == ("93.184.216.0", 64, 1)
    assert "93.184.216.34" not in str(args)  # la IP completa no viaja
    assert "1 visitas anonimizadas" in detalle
