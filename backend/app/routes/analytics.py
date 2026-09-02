"""
Endpoints autenticados: estadísticas, visitas recientes y el panel.

Toda ruta de aquí toma `Depends(require_analytics_auth)`, incluidos los
ficheros estáticos del panel: la CI lo comprueba estáticamente y los tests
lo ejecutan. Añadir una ruta sin la dependencia es publicar datos de visitas.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response

from ..dependencies import get_visits
from ..models import AnalyticsResponse, RecentResponse
from ..repositories.visits import VisitRepository
from ..security import require_analytics_auth

router = APIRouter()

# El panel son tres ficheros normales en static/, no una cadena dentro de
# Python: así pasan por el editor y el linter, y el HTML no lleva script
# inline, con lo que se le puede poner la misma CSP que al CV. Se leen una vez
# al importar el módulo; no cambian en caliente.
_STATIC = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD_HTML = (_STATIC / "dashboard.html").read_text(encoding="utf-8")
_DASHBOARD_CSS = (_STATIC / "dashboard.css").read_text(encoding="utf-8")
_DASHBOARD_JS = (_STATIC / "dashboard.js").read_text(encoding="utf-8")

_DASHBOARD_CSP = (
    "default-src 'self'; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; img-src 'self'; frame-ancestors 'none'"
)


@router.get("/api/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    _user: str = Depends(require_analytics_auth),
    visits: VisitRepository = Depends(get_visits),
):
    """Estadísticas agregadas de visitas. Requiere autenticación."""
    return await visits.overview()


@router.get("/api/analytics/recent", response_model=RecentResponse)
async def get_recent_visits(
    limit: int = Query(20, ge=1, le=100),
    _user: str = Depends(require_analytics_auth),
    visits: VisitRepository = Depends(get_visits),
):
    """Visitas recientes, tráfico interno incluido y marcado. Requiere autenticación."""
    return await visits.recent(limit)


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(_user: str = Depends(require_analytics_auth)):
    """Dashboard HTML. Requiere autenticación."""
    return HTMLResponse(
        content=_DASHBOARD_HTML,
        headers={"Content-Security-Policy": _DASHBOARD_CSP, "Cache-Control": "no-store"},
    )


@router.get("/analytics/dashboard.css")
async def analytics_dashboard_css(_user: str = Depends(require_analytics_auth)):
    return Response(content=_DASHBOARD_CSS, media_type="text/css")


@router.get("/analytics/dashboard.js")
async def analytics_dashboard_js(_user: str = Depends(require_analytics_auth)):
    return Response(content=_DASHBOARD_JS, media_type="text/javascript")
