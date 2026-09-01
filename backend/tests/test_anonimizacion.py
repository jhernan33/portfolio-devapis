"""
Anonimización de IPs y detección de tráfico propio.

Es el invariante central del proyecto: la promesa que el pie de página del CV
le hace a quien lo visita. La CI ya vigila que la columna en claro no se cree
ni se escriba; esto vigila que lo que sí se escribe esté efectivamente
anonimizado.
"""
import hashlib

import pytest

import main


# ============================================================
# anonymize_ip
# ============================================================

@pytest.mark.parametrize("ip, prefijo", [
    ("203.0.113.45", "203.0.113.0"),
    ("203.0.113.1", "203.0.113.0"),
    ("8.8.8.8", "8.8.8.0"),
    ("192.168.1.77", "192.168.1.0"),
])
def test_ipv4_se_trunca_a_24(configurar, ip, prefijo):
    assert main.anonymize_ip(ip)[0] == prefijo


@pytest.mark.parametrize("ip, prefijo", [
    ("2001:db8:1234:5678::1", "2001:db8:1234::"),
    ("2001:db8:1234::abcd", "2001:db8:1234::"),
])
def test_ipv6_se_trunca_a_48(configurar, ip, prefijo):
    assert main.anonymize_ip(ip)[0] == prefijo


def test_el_prefijo_pierde_al_host(configurar):
    """Dos hosts de la misma /24 son indistinguibles por su prefijo."""
    uno = main.anonymize_ip("203.0.113.10")[0]
    otro = main.anonymize_ip("203.0.113.200")[0]
    assert uno == otro == "203.0.113.0"


def test_la_ip_completa_no_aparece_en_ningun_valor_devuelto(configurar):
    ip = "203.0.113.45"
    prefijo, digest = main.anonymize_ip(ip)
    assert ip not in prefijo
    assert ip not in digest


def test_el_hash_es_sha256_con_sal(configurar):
    _, digest = main.anonymize_ip("203.0.113.45")
    esperado = hashlib.sha256(f"sal-de-prueba:203.0.113.45".encode()).hexdigest()
    assert digest == esperado
    assert len(digest) == 64


def test_misma_ip_mismo_hash(configurar):
    """Sin esto no se pueden contar visitantes únicos."""
    assert main.anonymize_ip("203.0.113.45")[1] == main.anonymize_ip("203.0.113.45")[1]


def test_ips_distintas_hashes_distintos(configurar):
    assert main.anonymize_ip("203.0.113.45")[1] != main.anonymize_ip("203.0.113.46")[1]


def test_cambiar_la_sal_rompe_la_continuidad(configurar):
    """
    Documenta por qué ANALYTICS_IP_SALT no se rota: el mismo visitante pasa a
    contarse como uno nuevo. Si este test empieza a fallar es que alguien
    quitó la sal del hash.
    """
    configurar(ip_salt="una-sal")
    con_una = main.anonymize_ip("203.0.113.45")[1]
    configurar(ip_salt="otra-sal")
    con_otra = main.anonymize_ip("203.0.113.45")[1]
    assert con_una != con_otra


@pytest.mark.parametrize("entrada", [
    "",
    None,
    "no-es-una-ip",
    "999.999.999.999",
    "203.0.113.45; DROP TABLE cv_visits",   # inyección por X-Forwarded-For
    "<script>alert(1)</script>",
    "203.0.113.45, 10.0.0.1",               # cadena entera, sin partir
    "0x7f000001",
])
def test_entradas_invalidas_no_se_almacenan(configurar, entrada):
    """
    La validación con `ipaddress` es lo que neutraliza la cabecera
    `X-Forwarded-For`, que la controla el cliente. Nada que no sea una IP
    llega a la base de datos.
    """
    assert main.anonymize_ip(entrada) == (None, None)


def test_se_toleran_los_espacios(configurar):
    assert main.anonymize_ip("  203.0.113.45  ")[0] == "203.0.113.0"


# ============================================================
# is_internal_ip
# ============================================================

@pytest.mark.parametrize("ip", [
    "192.168.1.10",     # RFC1918
    "10.0.0.5",         # red de Docker
    "172.17.0.2",       # bridge por defecto de Docker
    "127.0.0.1",        # health check
    "::1",
    "169.254.1.1",      # link-local
    "240.0.0.1",        # reservada
])
def test_los_rangos_no_enrutables_son_internos(configurar, ip):
    assert main.is_internal_ip(ip) is True


# Ojo con las IPs de ejemplo: Python clasifica los rangos de documentación
# (203.0.113.0/24, 198.51.100.0/24, 2001:db8::/32) como PRIVADOS, así que no
# sirven para simular a un visitante. Aquí van direcciones públicas de verdad.
@pytest.mark.parametrize("ip", [
    "8.8.8.8",
    "93.184.216.34",
    "2606:2800:220:1:248:1893:25c8:1946",
])
def test_una_ip_publica_cualquiera_es_visita(configurar, ip):
    assert main.is_internal_ip(ip) is False


def test_los_rangos_de_documentacion_cuentan_como_privados(configurar):
    """
    Documenta la trampa de arriba, que hizo fallar a estos mismos tests: si
    alguien escribe un caso nuevo con una IP de TEST-NET esperando que sea
    tratada como visitante, esta prueba explica por qué no lo es.
    """
    assert main.is_internal_ip("203.0.113.45") is True


def test_la_ip_publica_del_propio_servidor_se_excluye(configurar):
    """
    El caso que motivó ANALYTICS_IGNORE_NETWORKS: `is_private` no detecta la IP
    pública del VPS, así que cada curl lanzado desde él contaba como visita.
    """
    import ipaddress
    configurar(ignore_networks=[ipaddress.ip_network("93.184.216.34/32")])
    assert main.is_internal_ip("93.184.216.34") is True
    assert main.is_internal_ip("93.184.216.35") is False


def test_se_admite_una_red_entera_en_la_lista(configurar):
    import ipaddress
    configurar(ignore_networks=[ipaddress.ip_network("93.184.216.0/24")])
    assert main.is_internal_ip("93.184.216.7") is True
    assert main.is_internal_ip("93.184.217.7") is False


@pytest.mark.parametrize("entrada", ["", None, "no-es-una-ip"])
def test_lo_que_no_se_entiende_cuenta_como_interno(configurar, entrada):
    """Ante la duda, no inflar la métrica."""
    assert main.is_internal_ip(entrada) is True


# ============================================================
# parse_ignore_networks
# ============================================================

def test_se_leen_ips_sueltas_y_cidr():
    redes = main.parse_ignore_networks("203.0.113.93, 198.51.100.0/24")
    assert [str(r) for r in redes] == ["203.0.113.93/32", "198.51.100.0/24"]


def test_una_entrada_mal_escrita_no_tumba_el_arranque(capsys):
    """
    Perder una exclusión ensucia una estadística; dejar el servicio caído por
    una coma de más es peor.
    """
    redes = main.parse_ignore_networks("203.0.113.93, ESTO-NO-VA, 198.51.100.0/24")
    assert len(redes) == 2
    assert "ESTO-NO-VA" in capsys.readouterr().out


@pytest.mark.parametrize("entrada", ["", "   ", ",,,"])
def test_sin_configurar_no_hay_redes(entrada):
    assert main.parse_ignore_networks(entrada) == []


def test_se_normaliza_una_red_con_bits_de_host():
    """`strict=False`: 198.51.100.7/24 se entiende como la red 198.51.100.0/24."""
    redes = main.parse_ignore_networks("198.51.100.7/24")
    assert str(redes[0]) == "198.51.100.0/24"
