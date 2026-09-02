"""
Registro de la aplicación.

Antes todo salía por `print`: sin nivel, sin marca de tiempo y sin forma de
subirlo a depuración. El servicio estuvo meses en bucle de reinicio con el
motivo escrito en esos `print`, mezclado con el ruido de uvicorn.
"""

import logging

import pytest

from app.logs import LOGGER, configurar_logging


@pytest.mark.asyncio
async def test_un_fallo_al_registrar_la_visita_queda_en_el_log_con_su_traza(
    cliente, conexion, registro
):
    """
    Al cliente se le devuelve un error genérico a propósito. Si además no
    quedara nada en el registro, un fallo de escritura sería invisible: el
    visitante no lo nota y las estadísticas simplemente dejan de crecer.
    """
    conexion.error = RuntimeError("password authentication failed for user cv")

    respuesta = await cliente.post("/api/track")

    assert respuesta.json() == {"status": "error"}
    assert "password" not in respuesta.text
    assert "password authentication failed" in registro.text  # sí en el log
    assert "Traceback" in registro.text


@pytest.mark.asyncio
async def test_el_health_fallido_tambien_se_registra(cliente, conexion, registro):
    conexion.error = RuntimeError("connection refused a postgres17")
    assert (await cliente.get("/health")).status_code == 503
    assert "postgres17" in registro.text


def test_configurar_logging_es_idempotente():
    """
    Llamarla dos veces no puede duplicar los mensajes. Es justo lo que pasa
    cuando se añade un handler sin comprobar si ya hay uno, y el síntoma —cada
    línea repetida— se confunde con dos peticiones.
    """
    antes = len(LOGGER.handlers)
    configurar_logging()
    configurar_logging()
    assert len(LOGGER.handlers) == antes


def test_el_nivel_se_lee_del_entorno(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert configurar_logging().level == logging.DEBUG
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configurar_logging()


def test_un_nivel_sin_sentido_no_tumba_el_arranque(monkeypatch):
    """Mismo criterio que con las redes a ignorar: una variable mal escrita no
    puede impedir que el servicio arranque."""
    monkeypatch.setenv("LOG_LEVEL", "MUY-HABLADOR")
    assert configurar_logging().level == logging.INFO
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configurar_logging()
