"""
Autenticación HTTP Basic de los endpoints que exponen datos de visitas.

Vive en la aplicación y no en el reverse proxy, de modo que la protección
viaja con el repositorio y sobrevive a la recreación del contenedor.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import Settings
from .dependencies import get_settings

REALM = "cv-analytics"

security = HTTPBasic(realm=REALM)


def require_analytics_auth(
    credentials: HTTPBasicCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> str:
    """Protege los endpoints que exponen datos de visitas."""
    if not settings.auth_configured:
        # Fail closed: si no hay credenciales configuradas, no se sirve nada.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics authentication is not configured",
        )

    # Se comparan ambos siempre (sin cortocircuito) y en tiempo constante.
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.analytics_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), settings.analytics_password.encode("utf-8")
    )

    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": f'Basic realm="{REALM}"'},
        )

    return credentials.username
