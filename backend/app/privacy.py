"""
Anonimización de IPs y detección de tráfico propio.

Es el invariante central del proyecto: las IPs de los visitantes NUNCA se
almacenan en claro. Se guarda un prefijo de red truncado (para geografía
aproximada) y un hash SHA-256 con sal (para contar visitantes únicos sin
poder reidentificarlos).

Las funciones reciben la sal y las redes a ignorar como parámetros en lugar
de leerlas de un estado global: así su firma dice de qué dependen y se
prueban sin preparar nada.
"""

import hashlib
import ipaddress

from fastapi import Request


def anonymize_ip(raw_ip: str, salt: str):
    """
    Convierte una IP en (prefijo_de_red, hash_con_sal).

    - Valida que la entrada sea realmente una IP. Esto neutraliza la inyección
      vía cabecera `X-Forwarded-For`, que es controlable por el cliente.
    - IPv4 se trunca a /24 y IPv6 a /48: suficiente para estadísticas
      aproximadas, insuficiente para identificar a una persona.
    - El hash permite contar visitantes únicos sin conservar la IP.

    Devuelve (None, None) si la entrada no es una IP válida.
    """
    if not raw_ip:
        return None, None

    try:
        ip = ipaddress.ip_address(raw_ip.strip())
    except ValueError:
        return None, None

    network = 24 if ip.version == 4 else 48
    prefix = str(ipaddress.ip_network(f"{ip}/{network}", strict=False).network_address)
    digest = hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()

    return prefix, digest


def visitor_fingerprint(raw_ip: str, user_agent: str, salt: str) -> str | None:
    """
    Huella del visitante: hash con sal de la IP y su User-Agent.

    `ip_hash` por sí solo cuenta como un visitante a toda una oficina detrás de
    un NAT, y como varios a quien tiene IP dinámica. Añadir el User-Agent no lo
    resuelve del todo —nada lo hace sin cookies, y aquí no se quieren— pero sí
    separa a dos personas distintas de la misma red, que es el error que más se
    nota cuando el total de visitas se cuenta con los dedos de una mano.

    Devuelve None si la IP no es válida, por el mismo motivo que anonymize_ip:
    lo que no se entiende no se guarda.
    """
    try:
        ip = ipaddress.ip_address((raw_ip or "").strip())
    except ValueError:
        return None
    return hashlib.sha256(f"{salt}:{ip}:{user_agent or ''}".encode()).hexdigest()


def is_internal_ip(raw_ip: str, ignore_networks=()) -> bool:
    """
    ¿Esta visita es tráfico propio en lugar de un visitante?

    Descarta dos cosas distintas, y hacen falta las dos:

    1. Rangos no enrutables: privados (RFC1918), loopback, link-local y
       reservados. Cubre la navegación que sale por la red Docker, el health
       check y el desarrollo local.
    2. Las redes de `ignore_networks` (ANALYTICS_IGNORE_NETWORKS), pensadas
       para la IP pública del propio servidor. `is_private` NO la detecta,
       porque es pública de pleno derecho: la máquina llamándose a sí misma
       por su nombre de dominio.

    Una IP que no se puede interpretar cuenta como interna: si no se sabe de
    dónde viene, no debería inflar la métrica que el CV usa para medirse.
    """
    if not raw_ip:
        return True

    try:
        ip = ipaddress.ip_address(raw_ip.strip())
    except ValueError:
        return True

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True

    return any(ip in red for red in ignore_networks)


def client_ip_from_request(request: Request) -> str:
    """Extrae la IP del cliente respetando la cadena X-Forwarded-For de Traefik."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Tomar la PRIMERA de la cadena solo es seguro mientras el proxy
        # sobrescriba la cabecera en lugar de añadirse a la que mande el
        # cliente. Traefik lo hace así salvo que la petición venga de una IP
        # listada en `forwardedHeaders.trustedIPs`, que aquí no está definida:
        # verificado enviando `X-Forwarded-For: 8.8.8.8` y comprobando que se
        # registra igualmente la red real.
        #
        # Si algún día se pone Cloudflare delante y se configura trustedIPs
        # para leer la IP real del visitante, esta línea pasa a leer un valor
        # que controla el cliente y cualquiera podrá falsear su red. La
        # validación de anonymize_ip no protege de eso: descarta basura, pero
        # 8.8.8.8 es una IP perfectamente válida.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""
