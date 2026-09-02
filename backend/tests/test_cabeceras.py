"""
Cabeceras de seguridad de las respuestas del backend.

Nginx las pone en el CV, pero este servicio contesta directamente a través de
Traefik y salía sin ninguna. Se comprueban aquí porque son invisibles: nada
falla si desaparecen, simplemente el navegador deja de proteger.
"""

import pytest
from conftest import CLAVE, USUARIO

pytestmark = pytest.mark.asyncio

BUENAS = (USUARIO, CLAVE)

# Una respuesta que no lleve estas cuatro es una respuesta sin endurecer.
BASICAS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


@pytest.mark.parametrize(
    "ruta, metodo, auth",
    [
        ("/health", "get", None),
        ("/api/track", "post", None),
        ("/api/analytics", "get", BUENAS),
        ("/api/analytics/recent", "get", BUENAS),
        ("/analytics", "get", BUENAS),
        ("/analytics/dashboard.js", "get", BUENAS),
    ],
)
async def test_toda_respuesta_lleva_las_cabeceras_basicas(cliente, ruta, metodo, auth):
    respuesta = await getattr(cliente, metodo)(ruta, auth=auth)
    for nombre, valor in BASICAS.items():
        assert respuesta.headers.get(nombre) == valor, f"{ruta} sin {nombre}"


async def test_incluso_un_401_las_lleva(cliente):
    """Un rechazo también es una respuesta: sin esto, la ruta más atacada es
    justo la que sale sin endurecer."""
    respuesta = await cliente.get("/api/analytics")
    assert respuesta.status_code == 401
    assert respuesta.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("ruta", ["/api/analytics", "/api/analytics/recent", "/analytics"])
async def test_los_datos_de_visitas_no_se_cachean(cliente, ruta):
    respuesta = await cliente.get(ruta, auth=BUENAS)
    assert "no-store" in respuesta.headers.get("cache-control", "")


async def test_el_tracking_publico_no_lleva_no_store(cliente):
    """`no-store` solo en lo privado: /api/track no devuelve datos de nadie."""
    respuesta = await cliente.post("/api/track")
    assert "no-store" not in respuesta.headers.get("cache-control", "")


async def test_la_api_declara_una_csp_que_no_carga_nada(cliente):
    respuesta = await cliente.get("/api/analytics", auth=BUENAS)
    assert respuesta.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )


async def test_el_panel_conserva_su_propia_csp(cliente):
    """
    El middleware usa setdefault: el panel necesita cargar su CSS y su JS, y su
    política, más permisiva, tiene que ganar sobre la de la API.
    """
    respuesta = await cliente.get("/analytics", auth=BUENAS)
    assert "script-src 'self'" in respuesta.headers["content-security-policy"]
