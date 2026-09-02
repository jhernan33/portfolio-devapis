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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_visits(request: Request) -> VisitRepository:
    return VisitRepository(request.app.state.pool)
