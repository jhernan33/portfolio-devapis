"""
Dependencias inyectables en las rutas.

Configuración y pool viven en `app.state`, no en variables globales de módulo.
Las rutas los reciben por `Depends`, así que ni la lógica ni los tests tienen
que saber dónde se guardan: los tests sustituyen `app.state.pool` por un
doble en memoria y todo lo demás funciona igual.
"""

from fastapi import Request

from .config import Settings
from .repositories.visits import VisitRepository
from .timeutils import zona


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_visits(request: Request) -> VisitRepository:
    """
    El repositorio recibe la zona de presentación porque la necesita para dos
    cosas distintas: convertir las fechas que devuelve y decidir dónde empieza
    el día en las consultas agregadas.
    """
    ajustes: Settings = request.app.state.settings
    return VisitRepository(request.app.state.pool, zona(ajustes.display_tz))
