"""
Arranque y configuración.

El servicio debe negarse a arrancar si falta un secreto. No es una comodidad
perdida: `DB_PASSWORD` caía antes en "postgres" por defecto —lo que permitía
levantar el servicio contra la base de producción con credenciales por
defecto— y un `DB_HOST` con valor por defecto apuntó meses a un contenedor
inexistente sin que nadie lo notara.
"""
import pytest

import main


OBLIGATORIAS = {
    "DB_PASSWORD": "secreto",
    "ANALYTICS_USER": "usuario",
    "ANALYTICS_PASSWORD": "clave",
    "ANALYTICS_IP_SALT": "sal",
}


@pytest.fixture
def entorno_limpio(monkeypatch):
    """Parte de un entorno sin ninguna variable del servicio."""
    for nombre in list(OBLIGATORIAS) + [
        "DB_USER", "DB_NAME", "DB_HOST", "DB_PORT", "ANALYTICS_IGNORE_NETWORKS"
    ]:
        monkeypatch.delenv(nombre, raising=False)
    return monkeypatch


def test_con_todo_definido_arranca(entorno_limpio):
    for nombre, valor in OBLIGATORIAS.items():
        entorno_limpio.setenv(nombre, valor)

    ajustes = main.get_settings()
    assert ajustes["analytics_user"] == "usuario"
    assert ajustes["ip_salt"] == "sal"


@pytest.mark.parametrize("ausente", sorted(OBLIGATORIAS))
def test_sin_un_secreto_obligatorio_no_arranca(entorno_limpio, ausente):
    for nombre, valor in OBLIGATORIAS.items():
        if nombre != ausente:
            entorno_limpio.setenv(nombre, valor)

    with pytest.raises(RuntimeError) as error:
        main.get_settings()

    # El mensaje nombra la que falta y dónde definirla: es lo que se lee en
    # los logs del contenedor cuando el despliegue se queda parado.
    assert ausente in str(error.value)
    assert ".env" in str(error.value)


def test_una_variable_vacia_cuenta_como_ausente(entorno_limpio):
    for nombre, valor in OBLIGATORIAS.items():
        entorno_limpio.setenv(nombre, valor)
    entorno_limpio.setenv("ANALYTICS_PASSWORD", "")

    with pytest.raises(RuntimeError, match="ANALYTICS_PASSWORD"):
        main.get_settings()


def test_se_listan_todas_las_que_faltan_de_una_vez(entorno_limpio):
    entorno_limpio.setenv("DB_PASSWORD", "secreto")

    with pytest.raises(RuntimeError) as error:
        main.get_settings()

    mensaje = str(error.value)
    assert all(n in mensaje for n in
               ("ANALYTICS_USER", "ANALYTICS_PASSWORD", "ANALYTICS_IP_SALT"))


def test_las_redes_a_ignorar_son_opcionales(entorno_limpio):
    for nombre, valor in OBLIGATORIAS.items():
        entorno_limpio.setenv(nombre, valor)

    assert main.get_settings()["ignore_networks"] == []


def test_las_redes_a_ignorar_se_leen_del_entorno(entorno_limpio):
    for nombre, valor in OBLIGATORIAS.items():
        entorno_limpio.setenv(nombre, valor)
    entorno_limpio.setenv("ANALYTICS_IGNORE_NETWORKS", "93.184.216.34,198.51.100.0/24")

    redes = main.get_settings()["ignore_networks"]
    assert [str(r) for r in redes] == ["93.184.216.34/32", "198.51.100.0/24"]


def test_el_puerto_se_convierte_a_entero(entorno_limpio):
    for nombre, valor in OBLIGATORIAS.items():
        entorno_limpio.setenv(nombre, valor)
    entorno_limpio.setenv("DB_PORT", "6543")

    assert main.get_settings()["db_port"] == 6543
