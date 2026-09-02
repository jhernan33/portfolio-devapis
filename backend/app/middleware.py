"""
Cabeceras de seguridad de las respuestas del backend.

Nginx las pone en el CV, pero este servicio contesta directamente a través de
Traefik y salía sin ninguna: ni `nosniff`, ni política de referente, ni
protección contra enmarcado.

Se aplican con `setdefault`, nunca sobrescribiendo: el panel declara su propia
Content-Security-Policy —más permisiva, porque carga su CSS y su JS— y tiene
que ganar sobre la de aquí, que es la de una API que no sirve nada incrustable.
"""

from starlette.middleware.base import BaseHTTPMiddleware

# Rutas que devuelven datos de visitas. No deben quedar en ninguna caché
# intermedia ni en el disco del navegador.
PREFIJOS_PRIVADOS = ("/api/analytics", "/analytics")

CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Una respuesta JSON no carga nada. El panel sustituye esta política por la
    # suya, que sí permite su propio CSS y su propio JS.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        respuesta = await call_next(request)

        for nombre, valor in CABECERAS.items():
            respuesta.headers.setdefault(nombre, valor)

        if request.url.path.startswith(PREFIJOS_PRIVADOS):
            respuesta.headers.setdefault("Cache-Control", "no-store")

        return respuesta
