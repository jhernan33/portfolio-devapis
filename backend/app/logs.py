"""
Configuración del registro de la aplicación.

Antes todo salía por `print`: sin nivel, sin marca de tiempo y sin forma de
silenciarlo ni de subirlo a depuración. El servicio estuvo meses en bucle de
reinicio y el motivo estaba en esos `print`, mezclado con el ruido de uvicorn,
sin que nadie lo leyera.

El nivel se controla con `LOG_LEVEL` (INFO por defecto). No es un secreto ni
tiene efecto en la seguridad, así que a diferencia del resto de la
configuración tiene un valor por defecto razonable.
"""

import logging
import os
import sys

FORMATO = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

LOGGER = logging.getLogger("cv-analytics")


def configurar_logging() -> logging.Logger:
    """
    Deja el logger de la aplicación listo. Es idempotente: llamarla dos veces
    no duplica los mensajes, que es exactamente lo que pasa cuando se añade un
    handler sin comprobar si ya hay uno.
    """
    nivel = os.getenv("LOG_LEVEL", "INFO").upper()
    LOGGER.setLevel(getattr(logging, nivel, logging.INFO))

    if not LOGGER.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMATO))
        LOGGER.addHandler(handler)

    # El logger raíz ya lo gobierna uvicorn; propagar duplicaría cada línea.
    LOGGER.propagate = False
    return LOGGER
