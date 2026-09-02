"""
Migración que recalcula browser/os/device_type de las visitas ya guardadas.

Se prueba la parte con lógica (`recalcular`), que está separada del acceso a
datos justamente para poder ejercitarla sin PostgreSQL. Lo que hay que
garantizar es que corrija lo que estaba mal, que no toque lo que ya estaba
bien y que no invente nada donde no hay de dónde derivarlo.
"""

import migrar_user_agents as migracion

ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
)
OPERA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0"
)
WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fila(id_, agente, navegador, sistema, dispositivo):
    """Una fila tal como la devuelve asyncpg (se comporta como un mapping)."""
    return {
        "id": id_,
        "user_agent": agente,
        "browser": navegador,
        "os": sistema,
        "device_type": dispositivo,
    }


# ============================================================
# Qué corrige
# ============================================================


def test_corrige_android_guardado_como_linux():
    filas = [fila(1, ANDROID, "Chrome", "Linux", "Mobile")]
    assert migracion.recalcular(filas) == [(1, "Chrome", "Android", "Mobile")]


def test_corrige_ios_guardado_como_macos():
    filas = [fila(2, IPHONE, "Safari", "macOS", "Mobile")]
    assert migracion.recalcular(filas) == [(2, "Safari", "iOS", "Mobile")]


def test_corrige_opera_guardada_como_chrome():
    filas = [fila(3, OPERA, "Chrome", "Windows", "Desktop")]
    assert migracion.recalcular(filas) == [(3, "Opera", "Windows", "Desktop")]


def test_corrige_varias_a_la_vez():
    filas = [
        fila(1, ANDROID, "Chrome", "Linux", "Mobile"),
        fila(2, IPHONE, "Safari", "macOS", "Mobile"),
        fila(3, WINDOWS, "Chrome", "Windows", "Desktop"),  # esta ya está bien
    ]
    assert [c[0] for c in migracion.recalcular(filas)] == [1, 2]


# ============================================================
# Qué NO toca
# ============================================================


def test_una_fila_correcta_no_se_reescribe():
    """
    Reescribir una fila para dejarla igual ensucia el recuento final, que es
    lo único que se mira para decidir si la migración hizo algo.
    """
    filas = [fila(1, WINDOWS, "Chrome", "Windows", "Desktop")]
    assert migracion.recalcular(filas) == []


def test_sin_user_agent_no_se_inventa_nada():
    """
    Sin la cadena original no hay de dónde derivar. Lo guardado, aunque sea
    impreciso, es más que sobrescribirlo con "Unknown".
    """
    for vacio in (None, ""):
        filas = [fila(1, vacio, "Chrome", "Windows", "Desktop")]
        assert migracion.recalcular(filas) == []


def test_una_base_vacia_no_da_problemas():
    assert migracion.recalcular([]) == []


# ============================================================
# Idempotencia
# ============================================================


def test_ejecutarla_dos_veces_no_cambia_nada_la_segunda():
    """
    Recalcular es determinista: tras aplicar las correcciones, una segunda
    pasada no debe encontrar nada. Si esto falla, la migración oscila y no se
    puede lanzar sin miedo.
    """
    filas = [
        fila(1, ANDROID, "Chrome", "Linux", "Mobile"),
        fila(2, IPHONE, "Safari", "macOS", "Mobile"),
        fila(3, OPERA, "Chrome", "Windows", "Desktop"),
    ]

    correcciones = migracion.recalcular(filas)
    assert len(correcciones) == 3

    # Aplicar lo que haría el UPDATE, y volver a pasar.
    por_id = {c[0]: c for c in correcciones}
    ya_migradas = []
    for f in filas:
        _, navegador, sistema, dispositivo = por_id[f["id"]]
        ya_migradas.append(fila(f["id"], f["user_agent"], navegador, sistema, dispositivo))

    assert migracion.recalcular(ya_migradas) == []


def test_el_resultado_coincide_con_lo_que_guardaria_el_servicio():
    """
    La migración y el servicio tienen que derivar lo mismo de la misma cadena;
    si no, las filas antiguas y las nuevas contarían distinto.
    """
    from app.useragent import parse_user_agent

    for agente in (ANDROID, IPHONE, OPERA, WINDOWS):
        esperado = parse_user_agent(agente)
        filas = [fila(1, agente, "x", "x", "x")]
        _, navegador, sistema, dispositivo = migracion.recalcular(filas)[0]
        assert (navegador, sistema, dispositivo) == (
            esperado["browser"],
            esperado["os"],
            esperado["device_type"],
        )


# ============================================================
# Resumen previo
# ============================================================


def test_el_resumen_cuenta_cada_tipo_de_cambio():
    filas = [
        fila(1, ANDROID, "Chrome", "Linux", "Mobile"),
        fila(2, ANDROID, "Chrome", "Linux", "Mobile"),
        fila(3, OPERA, "Chrome", "Windows", "Desktop"),
    ]
    resumen = migracion.resumir(filas, migracion.recalcular(filas))

    assert resumen["sistema: Linux → Android"] == 2
    assert resumen["navegador: Chrome → Opera"] == 1


def test_el_resumen_ignora_las_filas_que_no_cambian():
    filas = [fila(1, WINDOWS, "Chrome", "Windows", "Desktop")]
    assert migracion.resumir(filas, migracion.recalcular(filas)) == {}
