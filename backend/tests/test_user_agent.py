"""
Parseo de User-Agent.

Se hace a mano, sin librería externa, para no añadir dependencias por una
estadística. El riesgo de hacerlo a mano es el ORDEN de las comprobaciones:
casi todas las cadenas contienen varias pistas a la vez y gana la primera que
se mira. Estos tests fijan ese orden.
"""

import pytest

from app.useragent import parse_user_agent

# Cadenas reales, no inventadas: son las que sirven de referencia.
CHROME_ESCRITORIO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
EDGE = CHROME_ESCRITORIO + " Edg/120.0.2210.91"
OPERA = CHROME_ESCRITORIO + " OPR/106.0.0.0"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
SAFARI_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15"
)
ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
)
IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
)
LINUX_ESCRITORIO = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================
# Navegador
# ============================================================


@pytest.mark.parametrize(
    "ua, esperado",
    [
        (CHROME_ESCRITORIO, "Chrome"),
        (EDGE, "Edge"),
        (OPERA, "Opera"),
        (FIREFOX, "Firefox"),
        (SAFARI_MAC, "Safari"),
        ("curl/8.4.0", "Unknown"),
        ("", "Unknown"),
    ],
)
def test_navegador(ua, esperado):
    assert parse_user_agent(ua)["browser"] == esperado


def test_edge_no_se_confunde_con_chrome():
    """Edge se identifica como Chrome además de como Edg: gana el más específico."""
    assert "chrome" in EDGE.lower()
    assert parse_user_agent(EDGE)["browser"] == "Edge"


def test_opera_no_se_confunde_con_chrome():
    """Mismo caso que Edge: Opera lleva `Chrome/` en la cadena."""
    assert "chrome" in OPERA.lower()
    assert parse_user_agent(OPERA)["browser"] == "Opera"


# ============================================================
# Sistema operativo
# ============================================================


@pytest.mark.parametrize(
    "ua, esperado",
    [
        (CHROME_ESCRITORIO, "Windows"),
        (SAFARI_MAC, "macOS"),
        (LINUX_ESCRITORIO, "Linux"),
        (FIREFOX, "Linux"),
        (ANDROID, "Android"),
        (IPHONE, "iOS"),
        (IPAD, "iOS"),
        ("curl/8.4.0", "Unknown"),
    ],
)
def test_sistema_operativo(ua, esperado):
    assert parse_user_agent(ua)["os"] == esperado


def test_android_no_se_confunde_con_linux():
    """
    Android declara `Linux` en su User-Agent. Si se comprueba Linux primero,
    ningún móvil Android se cuenta jamás como Android.
    """
    assert "linux" in ANDROID.lower()
    assert parse_user_agent(ANDROID)["os"] == "Android"


def test_ios_no_se_confunde_con_macos():
    """
    iPhone y iPad declaran `like Mac OS X`. Si se comprueba Mac primero, todo
    el tráfico de iOS se contabiliza como escritorio macOS.
    """
    assert "mac" in IPHONE.lower()
    assert parse_user_agent(IPHONE)["os"] == "iOS"


# ============================================================
# Tipo de dispositivo
# ============================================================


@pytest.mark.parametrize(
    "ua, esperado",
    [
        (CHROME_ESCRITORIO, "Desktop"),
        (SAFARI_MAC, "Desktop"),
        (LINUX_ESCRITORIO, "Desktop"),
        (ANDROID, "Mobile"),
        (IPHONE, "Mobile"),
        (IPAD, "Mobile"),
    ],
)
def test_tipo_de_dispositivo(ua, esperado):
    assert parse_user_agent(ua)["device_type"] == esperado


# ============================================================
# Robustez
# ============================================================


@pytest.mark.parametrize("ua", ["", "   ", "?", "x" * 5000, "<script>alert(1)</script>"])
def test_no_revienta_con_entradas_raras(ua):
    resultado = parse_user_agent(ua)
    assert set(resultado) == {"browser", "os", "device_type"}
    assert all(isinstance(v, str) for v in resultado.values())
