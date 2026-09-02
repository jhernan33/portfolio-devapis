"""
Utilidades compartidas por los tests del backend.

Dos decisiones que condicionan todo lo demás:

1. **No se levanta PostgreSQL.** El pool se sustituye por un doble en memoria.
   Lo que hay que verificar aquí es la lógica de la aplicación —qué se
   anonimiza, qué exige autenticación, qué SQL se emite— y eso no necesita una
   base real. Una suite que exige un contenedor no se ejecuta, y una suite que
   no se ejecuta no protege nada.

2. **No se dispara el `lifespan`.** `ASGITransport` entra directamente al
   enrutado sin ejecutar el arranque, así que ni se leen variables de entorno
   ni se crea el pool. Cada test inyecta en `app.state` la configuración y el
   pool que necesita, que además es la única forma de probar configuraciones
   distintas dentro del mismo proceso.
"""

import dataclasses
import pathlib
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# El backend no es un paquete instalable: se importa desde su directorio.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import main
from app.config import Settings
from app.logs import LOGGER
from app.repositories.visits import Visit

# El orden de los parámetros del INSERT es el de los campos de `Visit`, porque
# el repositorio lo construye con `astuple`. Derivarlo de la clase en lugar de
# copiarlo aquí evita que los tests sigan pasando mientras comprueban la
# columna equivocada, que es lo que ocurre cuando alguien añade un campo en
# medio y los índices se desplazan en silencio.
CAMPOS_INSERT = [c.name for c in dataclasses.fields(Visit)]

USUARIO = "reclutador"
CLAVE = "clave-de-prueba"
SAL = "sal-de-prueba"


class FilaCero(dict):
    """Una fila en la que toda columna vale 0: el resumen de una base vacía."""

    def __missing__(self, _columna):
        return 0


class ConexionFalsa:
    """
    Sustituye a una conexión de asyncpg.

    Registra todo lo que se ejecuta para que un test pueda afirmar sobre el SQL
    y —más importante— sobre los ARGUMENTOS: es ahí donde se comprueba que a la
    base nunca llega una IP en claro.
    """

    def __init__(self):
        self.ejecutados = []  # [(sql, args)] de execute()
        self.consultados = []  # [(sql, args)] de fetch()/fetchval()/fetchrow()
        self.respuestas = {}  # subcadena del SQL -> valor a devolver
        self.error = None  # excepción a lanzar, para simular la BD caída

    def _buscar(self, sql, por_defecto):
        for clave, valor in self.respuestas.items():
            if clave in sql:
                return valor
        return por_defecto

    async def execute(self, sql, *args):
        if self.error:
            raise self.error
        self.ejecutados.append((sql, args))
        return "INSERT 0 1"

    async def executemany(self, sql, args):
        if self.error:
            raise self.error
        self.ejecutados.append((sql, tuple(args)))

    async def fetchval(self, sql, *args):
        if self.error:
            raise self.error
        self.consultados.append((sql, args))
        return self._buscar(sql, 0)

    async def fetchrow(self, sql, *args):
        if self.error:
            raise self.error
        self.consultados.append((sql, args))
        return self._buscar(sql, FilaCero())

    async def fetch(self, sql, *args):
        if self.error:
            raise self.error
        self.consultados.append((sql, args))
        return self._buscar(sql, [])

    def transaction(self):
        """Las migraciones envuelven cada versión en una transacción."""
        return _Transaccion(self)

    # --- ayudas para los asertos -------------------------------------------

    @property
    def inserciones(self):
        return [(sql, args) for sql, args in self.ejecutados if "INSERT INTO cv_visits" in sql]

    def argumentos_insertados(self):
        """Argumentos del último INSERT, o None si no hubo ninguno."""
        return self.inserciones[-1][1] if self.inserciones else None

    def visita_insertada(self):
        """El último INSERT como diccionario, por nombre de columna."""
        argumentos = self.argumentos_insertados()
        return dict(zip(CAMPOS_INSERT, argumentos, strict=True)) if argumentos else None


class _Transaccion:
    """
    Transacción de mentira que sí respeta lo esencial: si el bloque lanza, lo
    escrito dentro no cuenta. Sin esto no se podría comprobar que una migración
    a medias no queda anotada como aplicada.
    """

    def __init__(self, conexion):
        self._conexion = conexion
        self._marca = 0

    async def __aenter__(self):
        self._marca = len(self._conexion.ejecutados)
        return self

    async def __aexit__(self, tipo, *_resto):
        if tipo is not None:
            del self._conexion.ejecutados[self._marca :]
        return False


class _Adquisicion:
    def __init__(self, conexion):
        self._conexion = conexion

    async def __aenter__(self):
        return self._conexion

    async def __aexit__(self, *_excepcion):
        return False


class PoolFalso:
    """
    Lo justo del pool de asyncpg que usa la aplicación.

    `get_size`/`get_idle_size` existen porque el diagnóstico autenticado los
    consulta: el doble imita la interfaz real contra la que se usa, en lugar de
    obligar al código de producción a preguntar si el pool los tiene.
    """

    def __init__(self, conexion):
        self.conexion = conexion

    def acquire(self):
        return _Adquisicion(self.conexion)

    def get_size(self):
        return 1

    def get_idle_size(self):
        return 1


@pytest.fixture
def conexion():
    return ConexionFalsa()


@pytest.fixture
def registro(caplog):
    """
    Da acceso a lo que registra la aplicación.

    `caplog` por sí solo no lo ve: el logger de la aplicación no propaga al
    raíz, a propósito, para que uvicorn no duplique cada línea. Aquí se le
    engancha el handler de caplog y se retira al terminar.
    """
    LOGGER.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        LOGGER.removeHandler(caplog.handler)


@pytest.fixture
def configurar(monkeypatch, conexion):
    """
    Deja la aplicación lista: credenciales, sal y pool falso.

    Devuelve una función para ajustar la configuración por test (por ejemplo,
    para añadir redes a ignorar) sin que se filtre a los demás: monkeypatch
    revierte `app.state` al terminar.
    """

    def _aplicar(**extra):
        valores = {
            "db_user": "test",
            "db_password": "test",
            "db_name": "test",
            "db_host": "localhost",
            "db_port": 5432,
            "analytics_user": USUARIO,
            "analytics_password": CLAVE,
            "ip_salt": SAL,
            "ignore_networks": (),
        }
        valores.update(extra)
        ajustes = Settings(**valores)
        monkeypatch.setattr(main.app.state, "settings", ajustes, raising=False)
        monkeypatch.setattr(main.app.state, "pool", PoolFalso(conexion), raising=False)
        return ajustes

    _aplicar()
    return _aplicar


@pytest_asyncio.fixture
async def cliente(configurar):
    """Cliente HTTP contra la app en memoria, sin lifespan ni red."""
    transporte = ASGITransport(app=main.app)
    async with AsyncClient(transport=transporte, base_url="https://test") as c:
        yield c
