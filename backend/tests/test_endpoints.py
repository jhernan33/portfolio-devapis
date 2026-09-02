"""
Contrato HTTP: qué es público, qué exige credenciales y qué llega a la base.

La CI ya comprueba estáticamente que toda ruta de datos declare
`Depends(require_analytics_auth)`. Esto lo comprueba ejecutándolo, que es lo
único que descarta que la dependencia esté puesta pero no surta efecto.
"""
import pytest

from conftest import CLAVE, USUARIO

pytestmark = pytest.mark.asyncio


BUENAS = (USUARIO, CLAVE)

# Incluye los ficheros del panel: se sirven bajo el mismo prefijo y con las
# mismas credenciales, para que nada del panel quede fuera de la protección.
RUTAS_PRIVADAS = [
    "/api/analytics", "/api/analytics/recent", "/analytics",
    "/analytics/dashboard.js", "/analytics/dashboard.css",
]


# ============================================================
# Rutas públicas
# ============================================================

async def test_health_responde_si_la_base_contesta(cliente):
    respuesta = await cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "healthy", "database": "connected"}


async def test_health_da_503_si_la_base_falla(cliente, conexion):
    conexion.error = RuntimeError("connection refused a postgres17")
    respuesta = await cliente.get("/health")
    assert respuesta.status_code == 503
    # El motivo se registra, no se publica.
    assert "postgres17" not in respuesta.text


async def test_track_es_publico(cliente):
    respuesta = await cliente.post("/api/track")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "tracked"


async def test_track_no_filtra_el_error_al_cliente(cliente, conexion):
    conexion.error = RuntimeError("password authentication failed for user cv")
    respuesta = await cliente.post("/api/track")
    assert respuesta.status_code == 200          # nunca degrada la experiencia
    assert respuesta.json() == {"status": "error"}
    assert "password" not in respuesta.text


# ============================================================
# Matriz de autenticación
# ============================================================

@pytest.mark.parametrize("ruta", RUTAS_PRIVADAS)
async def test_sin_credenciales_401(cliente, ruta):
    respuesta = await cliente.get(ruta)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("ruta", RUTAS_PRIVADAS)
async def test_el_401_lo_firma_la_aplicacion_no_traefik(cliente, ruta):
    """
    El realm distingue quién contestó. `realm="traefik"` significaría que la
    petición ni siquiera llegó aquí: es el síntoma del fallo de prioridades de
    routers que tuvo el tracking roto durante meses.
    """
    respuesta = await cliente.get(ruta)
    assert 'realm="cv-analytics"' in respuesta.headers.get("www-authenticate", "")


@pytest.mark.parametrize("ruta", RUTAS_PRIVADAS)
@pytest.mark.parametrize("credenciales", [
    ("otro", CLAVE),
    (USUARIO, "clave-incorrecta"),
    ("", ""),
    (USUARIO.upper(), CLAVE),      # el usuario distingue mayúsculas
])
async def test_credenciales_incorrectas_401(cliente, ruta, credenciales):
    respuesta = await cliente.get(ruta, auth=credenciales)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("ruta", RUTAS_PRIVADAS)
async def test_credenciales_correctas_200(cliente, ruta):
    respuesta = await cliente.get(ruta, auth=BUENAS)
    assert respuesta.status_code == 200


@pytest.mark.parametrize("ruta", RUTAS_PRIVADAS)
async def test_sin_credenciales_configuradas_no_se_sirve_nada(cliente, configurar, ruta):
    """Fail closed: si falta la configuración, 503, nunca datos."""
    configurar(analytics_user="", analytics_password="")
    respuesta = await cliente.get(ruta, auth=BUENAS)
    assert respuesta.status_code == 503


async def test_la_documentacion_interactiva_esta_deshabilitada(cliente):
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert (await cliente.get(ruta)).status_code == 404


# ============================================================
# Qué llega a la base de datos
# ============================================================

async def test_la_ip_del_visitante_no_llega_en_claro(cliente, conexion):
    ip = "93.184.216.34"
    await cliente.post("/api/track", headers={"x-forwarded-for": ip})

    sql, argumentos = conexion.inserciones[-1]
    assert ip not in sql
    assert ip not in [str(a) for a in argumentos]
    assert "93.184.216.0" in argumentos          # el prefijo truncado sí


async def test_se_guarda_el_prefijo_y_el_hash(cliente, conexion):
    await cliente.post("/api/track", headers={"x-forwarded-for": "93.184.216.34"})

    prefijo, digest = conexion.argumentos_insertados()[:2]
    assert prefijo == "93.184.216.0"
    assert len(digest) == 64


async def test_una_cabecera_falseada_con_basura_no_rompe_el_registro(cliente, conexion):
    """
    `X-Forwarded-For` la controla el cliente. Con basura dentro, la visita se
    registra igual pero sin datos de red, en lugar de propagar el valor.
    """
    await cliente.post(
        "/api/track",
        headers={"x-forwarded-for": "'; DROP TABLE cv_visits; --"},
    )
    prefijo, digest = conexion.argumentos_insertados()[:2]
    assert prefijo is None and digest is None


async def test_se_toma_la_primera_ip_de_la_cadena(cliente, conexion):
    await cliente.post(
        "/api/track",
        headers={"x-forwarded-for": "93.184.216.34, 10.0.0.1, 172.17.0.5"},
    )
    assert conexion.argumentos_insertados()[0] == "93.184.216.0"


async def test_el_trafico_propio_se_marca_como_interno(cliente, conexion, configurar):
    import ipaddress
    configurar(ignore_networks=[ipaddress.ip_network("93.184.216.34/32")])

    await cliente.post("/api/track", headers={"x-forwarded-for": "93.184.216.34"})
    assert conexion.argumentos_insertados()[8] is True

    await cliente.post("/api/track", headers={"x-forwarded-for": "8.8.8.8"})
    assert conexion.argumentos_insertados()[8] is False


async def test_se_guardan_navegador_sistema_y_dispositivo(cliente, conexion):
    android = (
        "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    )
    await cliente.post(
        "/api/track",
        headers={"user-agent": android, "x-forwarded-for": "8.8.8.8"},
    )
    agente, navegador, sistema, dispositivo = conexion.argumentos_insertados()[2:6]
    assert agente == android             # el user_agent se guarda entero
    assert (navegador, sistema, dispositivo) == ("Chrome", "Android", "Mobile")


async def test_solo_se_guarda_el_primer_idioma(cliente, conexion):
    await cliente.post(
        "/api/track",
        headers={"accept-language": "es-VE,es;q=0.9,en;q=0.8", "x-forwarded-for": "8.8.8.8"},
    )
    assert conexion.argumentos_insertados()[7] == "es-VE"


# ============================================================
# Forma de las respuestas
# ============================================================

async def test_analytics_devuelve_la_estructura_que_espera_el_panel(cliente):
    datos = (await cliente.get("/api/analytics", auth=BUENAS)).json()
    assert set(datos) == {
        "summary", "top_browsers", "top_networks",
        "device_stats", "os_stats", "daily_visits",
    }
    assert set(datos["summary"]) == {
        "total_visits", "unique_visitors", "recent_visits_7d", "today_visits",
    }


async def test_las_estadisticas_excluyen_el_trafico_interno(cliente, conexion):
    """
    Cada consulta agregada tiene que filtrar. En la primera medición real, el
    70% de las "visitas" era tráfico propio.
    """
    await cliente.get("/api/analytics", auth=BUENAS)
    consultas = [sql for sql, _ in conexion.consultados if "cv_visits" in sql]
    assert consultas
    assert all("NOT is_internal" in sql for sql in consultas)


async def test_las_visitas_recientes_no_filtran_el_trafico_interno(cliente, conexion):
    """
    Deliberadamente sin filtrar: en local todo es privado y, filtrando, el
    panel se vería vacío sin poder distinguir "no llega nada" de "llega y se
    descarta".
    """
    await cliente.get("/api/analytics/recent", auth=BUENAS)
    sql = conexion.consultados[-1][0]
    assert "NOT is_internal" not in sql
    assert "is_internal" in sql          # pero sí se expone la marca


async def test_las_visitas_recientes_no_exponen_el_hash(cliente, conexion):
    """El hash identifica a un visitante entre visitas; no hace falta enseñarlo."""
    sql = None
    await cliente.get("/api/analytics/recent", auth=BUENAS)
    sql = conexion.consultados[-1][0]
    assert "ip_hash" not in sql


@pytest.mark.parametrize("limite, codigo", [
    (1, 200), (20, 200), (100, 200),
    (0, 422), (101, 422), (-1, 422), ("muchas", 422),
])
async def test_el_limite_de_recientes_se_valida(cliente, limite, codigo):
    respuesta = await cliente.get(
        "/api/analytics/recent", params={"limit": limite}, auth=BUENAS
    )
    assert respuesta.status_code == codigo


async def test_las_fechas_se_devuelven_en_hora_de_venezuela(cliente, conexion):
    import datetime
    conexion.respuestas = {
        "LIMIT $1": [
            {
                "ip_prefix": "93.184.216.0", "browser": "Chrome", "os": "Linux",
                "device_type": "Desktop", "referer": None, "language": "es",
                "is_internal": False,
                "visited_at": datetime.datetime(2026, 9, 1, 16, 0, 0),   # UTC
            }
        ]
    }
    datos = (await cliente.get("/api/analytics/recent", auth=BUENAS)).json()
    assert datos["visits"][0]["visited_at"].startswith("2026-09-01T12:00:00")
    assert datos["visits"][0]["visited_at"].endswith("-04:00")


async def test_el_panel_se_sirve_como_html(cliente):
    respuesta = await cliente.get("/analytics", auth=BUENAS)
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "CV Analytics Dashboard" in respuesta.text


async def test_el_panel_no_lleva_script_inline_y_declara_csp(cliente):
    """
    El panel construye el DOM desde un fichero JS aparte, así que puede
    llevar la misma CSP que el CV: `script-src 'self'`. Un script inline
    volvería a quedar fuera de cualquier política.
    """
    respuesta = await cliente.get("/analytics", auth=BUENAS)
    assert "script-src 'self'" in respuesta.headers.get("content-security-policy", "")
    assert "<script>" not in respuesta.text
    assert 'src="/analytics/dashboard.js"' in respuesta.text


async def test_los_ficheros_del_panel_se_sirven_con_su_tipo(cliente):
    js = await cliente.get("/analytics/dashboard.js", auth=BUENAS)
    css = await cliente.get("/analytics/dashboard.css", auth=BUENAS)
    assert js.headers["content-type"].startswith("text/javascript")
    assert css.headers["content-type"].startswith("text/css")
    assert "innerHTML" not in js.text        # solo textContent/createElement


async def test_el_resumen_sale_de_una_sola_consulta(cliente, conexion):
    """
    Los cuatro contadores del resumen se calculan en una pasada por la tabla.
    Cuatro consultas separadas cuentan lo mismo cuatro veces.
    """
    await cliente.get("/api/analytics", auth=BUENAS)
    resumenes = [sql for sql, _ in conexion.consultados if "total_visits" in sql]
    assert len(resumenes) == 1
    assert "unique_visitors" in resumenes[0] and "today_visits" in resumenes[0]
