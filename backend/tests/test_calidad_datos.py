"""
Separar visitas de ruido: rastreadores, recargas, página e identidad.

Hasta ahora "visita" era cualquier POST a /api/track. Con siete visitas
externas reales, una persona curiosa que recarga tres veces movía la métrica
un 40%, y un rastreador que ejecuta JavaScript contaba como lector.
"""

import json

import pytest
from conftest import CLAVE, SAL, USUARIO

from app.paginas import IDIOMAS, normalizar_pagina
from app.privacy import visitor_fingerprint
from app.useragent import es_bot

BUENAS = (USUARIO, CLAVE)

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"


# ============================================================
# Rastreadores
# ============================================================


@pytest.mark.parametrize(
    "ua",
    [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "Twitterbot/1.0",
        "facebookexternalhit/1.1",
        "WhatsApp/2.23.20.0",
        "Slackbot-LinkExpanding 1.0",
        "LinkedInBot/1.0",
        "Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/120.0.0.0",
        "Chrome-Lighthouse",
        "curl/8.4.0",
        "Wget/1.21.3",
        "python-requests/2.31.0",
    ],
)
def test_los_rastreadores_conocidos_se_reconocen(ua):
    assert es_bot(ua) is True


@pytest.mark.parametrize("ua", [CHROME, FIREFOX, "", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1)"])
def test_un_navegador_de_verdad_no_es_un_rastreador(ua):
    assert es_bot(ua) is False


async def test_la_visita_de_un_rastreador_se_guarda_marcada(cliente, conexion):
    """
    No se descarta: se guarda y se ve en /recent. Descartarla dejaría sin
    forma de distinguir "no llega nada" de "llega y se está filtrando".
    """
    await cliente.post(
        "/api/track",
        headers={"user-agent": "Googlebot/2.1", "x-forwarded-for": "8.8.8.8"},
    )
    assert conexion.visita_insertada()["is_bot"] is True


async def test_una_persona_no_se_marca_como_rastreador(cliente, conexion):
    await cliente.post("/api/track", headers={"user-agent": CHROME, "x-forwarded-for": "8.8.8.8"})
    assert conexion.visita_insertada()["is_bot"] is False


async def test_las_estadisticas_excluyen_a_los_rastreadores(cliente, conexion):
    await cliente.get("/api/analytics", auth=BUENAS)
    consultas = [sql for sql, _ in conexion.consultados if "FROM cv_visits" in sql]
    assert consultas
    assert all("NOT is_bot" in sql for sql in consultas)


# ============================================================
# Recargas
# ============================================================


async def test_la_recarga_la_decide_la_base_en_el_propio_insert(cliente, conexion):
    """
    Preguntar antes y escribir después son dos viajes y una ventana en la que
    dos peticiones simultáneas se declaran la primera cada una.
    """
    await cliente.post("/api/track", headers={"x-forwarded-for": "8.8.8.8"})
    sql, _ = conexion.inserciones[-1]
    assert "is_repeat" in sql
    assert "EXISTS" in sql and "30 minutes" in sql


async def test_las_visitas_no_cuentan_las_recargas_pero_los_unicos_si(cliente, conexion):
    await cliente.get("/api/analytics", auth=BUENAS)
    resumen = next(sql for sql, _ in conexion.consultados if "total_visits" in sql)

    total = resumen[resumen.index("total_visits") - 80 : resumen.index("total_visits")]
    assert "NOT is_repeat" in total

    unicos = resumen[resumen.index("unique_visitors") - 120 : resumen.index("unique_visitors")]
    assert "NOT is_repeat" not in unicos
    assert "COALESCE(visitor_hash, ip_hash)" in unicos


# ============================================================
# Identidad del visitante
# ============================================================


def test_la_huella_separa_a_dos_personas_de_la_misma_red():
    """
    El caso que lo motiva: una oficina detrás de un NAT contaba como un solo
    visitante, por muchas personas que abrieran el CV.
    """
    una = visitor_fingerprint("93.184.216.34", CHROME, SAL)
    otra = visitor_fingerprint("93.184.216.34", FIREFOX, SAL)
    assert una != otra
    assert len(una) == 64


def test_la_misma_persona_da_la_misma_huella():
    assert visitor_fingerprint("93.184.216.34", CHROME, SAL) == visitor_fingerprint(
        "93.184.216.34", CHROME, SAL
    )


def test_la_huella_no_contiene_la_ip_ni_el_agente():
    huella = visitor_fingerprint("93.184.216.34", CHROME, SAL)
    assert "93.184.216.34" not in huella
    assert "Chrome" not in huella


def test_sin_ip_valida_no_hay_huella():
    assert visitor_fingerprint("no-es-una-ip", CHROME, SAL) is None
    assert visitor_fingerprint("", CHROME, SAL) is None


def test_la_huella_tambien_depende_de_la_sal():
    """Mismo motivo que con ip_hash: sin sal, el hash de una IP es reversible
    con una tabla de todo el espacio IPv4."""
    assert visitor_fingerprint("8.8.8.8", CHROME, "una") != visitor_fingerprint(
        "8.8.8.8", CHROME, "otra"
    )


# ============================================================
# Qué versión del CV se ha visto
# ============================================================


@pytest.mark.parametrize(
    "enviado, guardado",
    [
        ("/cv", "/cv"),
        ("/cv/", "/cv"),
        ("/cv/index.html", "/cv"),
        ("/cv/en", "/cv/en"),
        ("/cv/en/", "/cv/en"),
        ("/cv/en/index.html", "/cv/en"),
    ],
)
def test_las_rutas_conocidas_se_normalizan(enviado, guardado):
    assert normalizar_pagina(enviado) == guardado


@pytest.mark.parametrize(
    "entrada",
    [
        "/otra-cosa",
        "<script>alert(1)</script>",
        "'; DROP TABLE cv_visits; --",
        "x" * 500,
        123,
        {"a": 1},
        [],
    ],
)
def test_nada_desconocido_llega_a_la_base_en_crudo(entrada):
    """El valor lo manda el navegador: se reduce a un conjunto cerrado."""
    assert normalizar_pagina(entrada) == "otro"


def test_sin_valor_no_se_inventa_ninguno():
    """El frontend antiguo no manda cuerpo y esas visitas siguen siendo válidas."""
    assert normalizar_pagina(None) is None


def test_cada_etiqueta_conocida_tiene_idioma():
    assert set(IDIOMAS) == {"/cv", "/cv/en"}


async def test_la_pagina_llega_desde_el_cuerpo(cliente, conexion):
    await cliente.post(
        "/api/track",
        headers={"x-forwarded-for": "8.8.8.8"},
        content=json.dumps({"page": "/cv/en/"}),
    )
    assert conexion.visita_insertada()["page"] == "/cv/en"


async def test_sin_cuerpo_la_visita_se_registra_igual(cliente, conexion):
    respuesta = await cliente.post("/api/track", headers={"x-forwarded-for": "8.8.8.8"})
    assert respuesta.json()["status"] == "tracked"
    assert conexion.visita_insertada()["page"] is None


@pytest.mark.parametrize(
    "cuerpo",
    [
        "no es json",
        "[1, 2, 3]",
        '{"page": ',
        '{"otra": "cosa"}',
    ],
)
async def test_un_cuerpo_ilegible_no_rompe_el_tracking(cliente, conexion, cuerpo):
    """El tracking nunca debe fallar por lo que mande el cliente."""
    respuesta = await cliente.post(
        "/api/track", headers={"x-forwarded-for": "8.8.8.8"}, content=cuerpo
    )
    assert respuesta.json()["status"] == "tracked"
    assert conexion.visita_insertada()["page"] in (None, "otro")


async def test_un_cuerpo_enorme_se_descarta_sin_leerlo_entero(cliente, conexion):
    """
    /api/track es público. Aceptar cuerpos arbitrarios por cortesía es regalar
    un vector de agotamiento de memoria.
    """
    respuesta = await cliente.post(
        "/api/track",
        headers={"x-forwarded-for": "8.8.8.8"},
        content=json.dumps({"page": "/cv", "relleno": "x" * 10_000}),
    )
    assert respuesta.json()["status"] == "tracked"
    assert conexion.visita_insertada()["page"] is None


async def test_el_desglose_por_pagina_esta_en_la_respuesta(cliente):
    datos = (await cliente.get("/api/analytics", auth=BUENAS)).json()
    assert "page_stats" in datos
