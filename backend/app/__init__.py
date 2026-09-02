"""
CV Analytics API
================
FastAPI backend para tracking de visitas al CV.

Principios de seguridad de este servicio:
- Las IPs de los visitantes NUNCA se almacenan en claro (`privacy.py`).
- Los endpoints de consulta exigen autenticación HTTP Basic a nivel de
  aplicación (`security.py`), de modo que la protección viaja con el
  repositorio y no depende de la configuración del reverse proxy.
- Los secretos son obligatorios: si faltan, el servicio no arranca
  (`config.py`).

`create_app()` es la única pieza que sabe cómo se ensambla todo. No hay
estado global de módulo: configuración y pool viven en `app.state` y las
rutas los reciben por dependencia.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .db import create_pool, init_database
from .routes import analytics, public

ALLOWED_ORIGINS = [
    "https://devapis.cloud",
    "http://localhost:8000",
    "http://localhost",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranque y parada: configuración, pool y esquema."""
    # Falla de forma ruidosa si falta configuración, en lugar de arrancar
    # con credenciales por defecto.
    settings = load_settings()
    pool = await create_pool(settings)
    print("✅ Database pool created")

    app.state.settings = settings
    app.state.pool = pool

    await init_database(pool, settings)

    yield

    await pool.close()
    print("🔴 Database pool closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CV Analytics API",
        description="Sistema de tracking para el CV de José Hernán Varela",
        version="2.1.0",
        lifespan=lifespan,
        # La documentación interactiva queda deshabilitada: expone el
        # inventario completo de la API sin aportar nada en producción.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # CORS restringido al dominio propio
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(public.router)
    app.include_router(analytics.router)
    return app
