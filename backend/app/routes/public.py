"""
Endpoints públicos: el tracking que llama el frontend y el health check.

El rate limiting de `/api/track` vive en Traefik (ver docker-compose.yaml).
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import Settings
from ..dependencies import get_settings, get_visits
from ..logs import LOGGER
from ..models import HealthResponse, TrackResponse
from ..paginas import normalizar_pagina
from ..privacy import (
    anonymize_ip,
    client_ip_from_request,
    is_internal_ip,
    visitor_fingerprint,
)
from ..repositories.visits import Visit, VisitRepository
from ..useragent import es_bot, parse_user_agent

# El cuerpo del tracking es un objeto de un solo campo. Cualquier cosa más
# grande que esto no es el frontend de este CV, y leerla entera en memoria por
# cortesía sería regalar un vector de agotamiento a una ruta pública.
CUERPO_MAXIMO = 512

router = APIRouter()


def pagina_del_cuerpo(bruto: bytes) -> str | None:
    """
    Extrae qué versión del CV se ha visitado, si el frontend lo dice.

    Todo lo que llega aquí es opcional y no fiable: el frontend antiguo no
    manda cuerpo, y quien llame a mano puede mandar cualquier cosa. Nada de lo
    que venga se guarda en crudo —`normalizar_pagina` lo reduce a un conjunto
    cerrado— y un cuerpo ilegible se descarta sin ruido, porque el tracking
    nunca debe fallar por lo que mande el cliente.
    """
    if not bruto or len(bruto) > CUERPO_MAXIMO:
        return None
    try:
        datos = json.loads(bruto)
    except ValueError:
        return None
    return normalizar_pagina(datos.get("page")) if isinstance(datos, dict) else None


def visit_from_request(request: Request, settings: Settings, cuerpo: bytes) -> Visit:
    """
    Construye la visita a partir de las cabeceras y del cuerpo, si lo hay.

    La IP se anonimiza aquí, antes de que exista siquiera el objeto que se va
    a persistir: nunca hay una IP en claro camino de la base.
    """
    raw_ip = client_ip_from_request(request)
    ip_prefix, ip_hash = anonymize_ip(raw_ip, settings.ip_salt)

    user_agent = request.headers.get("user-agent", "Unknown")
    ua_info = parse_user_agent(user_agent)

    language = request.headers.get("accept-language", "Unknown")
    if language and "," in language:
        language = language.split(",")[0].strip()

    return Visit(
        ip_prefix=ip_prefix,
        ip_hash=ip_hash,
        visitor_hash=visitor_fingerprint(raw_ip, user_agent, settings.ip_salt),
        user_agent=user_agent,
        browser=ua_info["browser"],
        os=ua_info["os"],
        device_type=ua_info["device_type"],
        referer=request.headers.get("referer"),
        language=language,
        page=pagina_del_cuerpo(cuerpo),
        # Se marca en el momento de registrar, no al consultar: la lista de
        # redes a ignorar puede cambiar, y lo que interesa es cómo se veía la
        # visita cuando ocurrió.
        is_internal=is_internal_ip(raw_ip, settings.ignore_networks),
        # Un rastreador se guarda igual, pero no cuenta como visita: los que
        # ejecutan JavaScript llegan aquí exactamente igual que una persona.
        is_bot=es_bot(user_agent),
        # Con tzinfo: la columna es TIMESTAMPTZ desde la migración 0002 y
        # PostgreSQL guarda el instante, no una hora suelta sin contexto.
        visited_at=datetime.now(UTC),
    )


@router.post("/api/track", response_model=TrackResponse, response_model_exclude_none=True)
async def track_visit(
    request: Request,
    settings: Settings = Depends(get_settings),
    visits: VisitRepository = Depends(get_visits),
):
    """Registra una visita al CV. Público (lo llama el frontend)."""
    try:
        await visits.record(visit_from_request(request, settings, await request.body()))
        return TrackResponse(
            status="tracked",
            timestamp=datetime.now(UTC).isoformat(),
        )
    except Exception:
        # Se registra con la traza completa, pero al cliente no se le devuelve
        # el detalle y nunca se degrada la experiencia del visitante.
        LOGGER.exception("Error registrando una visita")
        return TrackResponse(status="error")


@router.get("/health", response_model=HealthResponse)
async def health(visits: VisitRepository = Depends(get_visits)):
    """
    Health check público: 200 si el servicio atiende, 503 si no.

    No dice qué componente falla. Es una ruta abierta, la usan el health check
    de Docker y el monitor externo, y ninguno de los dos necesita el detalle:
    para eso está /api/analytics/health, que pide credenciales.
    """
    try:
        await visits.ping()
    except Exception:
        LOGGER.exception("Health check fallido")
        raise HTTPException(status_code=503, detail="Service unavailable") from None
    return HealthResponse(status="ok")
