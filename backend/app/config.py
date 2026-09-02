"""
Configuración del servicio.

Los secretos son obligatorios: si falta uno, el servicio no arranca. Antes
`DB_PASSWORD` caía en "postgres" por defecto, lo que permitía levantar el
servicio contra la base de producción con credenciales por defecto sin que
nada lo delatara.

`Settings` es inmutable a propósito: la configuración se lee una vez en el
arranque y viaja como valor. Nada la modifica después, y los tests construyen
la suya sin tocar variables de entorno.
"""
import ipaddress
import os
from dataclasses import dataclass

# Variables sin las que el servicio no debe arrancar.
REQUIRED_ENV = ("DB_PASSWORD", "ANALYTICS_USER", "ANALYTICS_PASSWORD", "ANALYTICS_IP_SALT")


@dataclass(frozen=True)
class Settings:
    db_user: str
    db_password: str
    db_name: str
    db_host: str
    db_port: int
    analytics_user: str
    analytics_password: str
    ip_salt: str
    ignore_networks: tuple = ()

    @property
    def auth_configured(self) -> bool:
        """Sin usuario y contraseña no se sirve ningún dato de visitas."""
        return bool(self.analytics_user and self.analytics_password)


def parse_ignore_networks(raw: str) -> list:
    """
    Redes cuyo tráfico se registra pero no cuenta como visita.

    Acepta IPs sueltas o notación CIDR, separadas por comas:

        ANALYTICS_IGNORE_NETWORKS=195.26.247.93,203.0.113.0/24

    Existe porque los rangos privados no bastan. La IP pública del propio
    servidor es una IP pública perfectamente válida, así que `is_private` no la
    detecta: sin esta lista, cada `curl` de comprobación lanzado desde el VPS
    se contabiliza como una visita. En la primera medición con tráfico real,
    entre eso y la red interna, el 70% de las "visitas" no eran visitantes.

    Va por entorno y no escrita en el código porque la IP del servidor cambia
    al migrar de proveedor, y ese es justo el momento en que nadie se acuerda
    de tocar el código.

    Una entrada mal escrita se descarta con aviso en lugar de impedir el
    arranque: perder una exclusión ensucia una estadística, pero dejar el
    servicio caído por una coma de más es peor.
    """
    redes = []
    for entrada in raw.split(","):
        entrada = entrada.strip()
        if not entrada:
            continue
        try:
            redes.append(ipaddress.ip_network(entrada, strict=False))
        except ValueError:
            print(f"⚠️  ANALYTICS_IGNORE_NETWORKS: '{entrada}' no es una red válida, se ignora")
    return redes


def load_settings() -> Settings:
    """Lee y valida la configuración desde el entorno. Falla si falta un secreto."""
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno obligatorias: " + ", ".join(missing) +
            ". Defínelas en el archivo .env (ver .env.example)."
        )

    return Settings(
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD"),
        db_name=os.getenv("DB_NAME", "postgres"),
        db_host=os.getenv("DB_HOST", "postgres17"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        analytics_user=os.getenv("ANALYTICS_USER"),
        analytics_password=os.getenv("ANALYTICS_PASSWORD"),
        ip_salt=os.getenv("ANALYTICS_IP_SALT"),
        ignore_networks=tuple(parse_ignore_networks(os.getenv("ANALYTICS_IGNORE_NETWORKS", ""))),
    )
