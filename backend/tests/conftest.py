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
import pathlib
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# El backend no es un paquete instalable: se importa desde su directorio.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from app.config import Settings  # noqa: E402


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
        self.ejecutados = []      # [(sql, args)] de execute()
        self.consultados = []     # [(sql, args)] de fetch()/fetchval()/fetchrow()
        self.respuestas = {}      # subcadena del SQL -> valor a devolver
        self.error = None         # excepción a lanzar, para simular la BD caída

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

    # --- ayudas para los asertos -------------------------------------------

    @property
    def inserciones(self):
        return [(sql, args) for sql, args in self.ejecutados
                if "INSERT INTO cv_visits" in sql]

    def argumentos_insertados(self):
        """Argumentos del último INSERT, o None si no hubo ninguno."""
        return self.inserciones[-1][1] if self.inserciones else None


class _Adquisicion:
    def __init__(self, conexion):
        self._conexion = conexion

    async def __aenter__(self):
        return self._conexion

    async def __aexit__(self, *_excepcion):
        return False


class PoolFalso:
    """Lo justo del pool de asyncpg que usa la aplicación: `acquire()`."""

    def __init__(self, conexion):
        self.conexion = conexion

    def acquire(self):
        return _Adquisicion(self.conexion)


@pytest.fixture
def conexion():
    return ConexionFalsa()


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
