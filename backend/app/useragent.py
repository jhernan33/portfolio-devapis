"""
Parse básico de User-Agent, sin librería externa.

Lo delicado aquí no son las palabras que se buscan, sino EL ORDEN en que se
buscan: una misma cadena contiene varias pistas a la vez y gana la primera
que se mira. Tres reglas estuvieron mal ordenadas y falseaban la estadística
en silencio (lo destapó backend/tests):

- Opera y Edge se anuncian además como `Chrome/…`, así que van antes.
- Android declara `Linux` en la cadena: comprobar Linux primero hacía que
  NINGÚN Android se registrara nunca como Android.
- iPhone y iPad declaran `like Mac OS X`: comprobar Mac primero contaba
  todo el tráfico de iOS como escritorio macOS.

Por eso las reglas son TABLAS ordenadas y no una cadena de `if`: el orden es
un dato visible, no una propiedad emergente del código. Para añadir un
navegador o un sistema se añade una fila en su sitio —lo más específico
primero— y un test.
"""

# (pista en minúsculas, etiqueta). Gana la primera fila que aparece en la cadena.
BROWSERS = (
    ("edg", "Edge"),
    ("opr", "Opera"),
    ("opera", "Opera"),
    ("chrome", "Chrome"),
    ("firefox", "Firefox"),
    ("safari", "Safari"),
)

# Los móviles antes que los de escritorio a los que imitan.
SYSTEMS = (
    ("windows", "Windows"),
    ("android", "Android"),
    ("iphone", "iOS"),
    ("ipad", "iOS"),
    ("ipod", "iOS"),
    ("mac", "macOS"),
    ("darwin", "macOS"),
    ("linux", "Linux"),
)

MOBILE_HINTS = ("mobile", "android", "iphone", "ipad", "phone", "tablet")

# Cadenas que delatan a algo que no es una persona leyendo el CV.
#
# La lista no aspira a ser exhaustiva —ninguna lo es— sino a quitar el ruido
# que de verdad llega: rastreadores de buscadores y de redes sociales (que
# piden la página cada vez que alguien comparte el enlace), auditorías
# automáticas y las herramientas de línea de órdenes con las que uno mismo
# comprueba que el sitio responde.
#
# Se busca por subcadena y en minúsculas, igual que el resto del módulo. Los
# guiones y las barras van a propósito: "bot" suelto también aparecería dentro
# de palabras normales de un User-Agent legítimo.
BOTS = (
    "bot",  # googlebot, bingbot, twitterbot, telegrambot…
    "crawler",
    "spider",
    "slurp",  # Yahoo
    "headless",  # Chrome sin interfaz: auditorías y capturas
    "lighthouse",
    "pagespeed",
    "curl/",
    "wget",
    "python-requests",
    "httpx",
    "go-http-client",
    "libwww-perl",
    "facebookexternalhit",
    "whatsapp",
    "slackbot",
    "linkedinbot",
    "embedly",
    "preview",
    "monitor",
    "uptime",
)

UNKNOWN = "Unknown"


def _first_match(ua_lower: str, rules, default: str) -> str:
    return next((label for hint, label in rules if hint in ua_lower), default)


def es_bot(ua_string: str) -> bool:
    """
    ¿Esto es un rastreador y no una persona?

    Se decide al registrar, no al consultar: la lista de arriba crecerá, y lo
    que interesa saber de una visita es cómo se veía cuando ocurrió. Igual que
    con el tráfico interno, la fila se guarda de todas formas y sigue
    apareciendo en /api/analytics/recent; solo queda fuera de los agregados.
    """
    ua_lower = (ua_string or "").lower()
    return any(pista in ua_lower for pista in BOTS)


def parse_user_agent(ua_string: str) -> dict:
    """Devuelve {"browser", "os", "device_type"} a partir de la cadena."""
    ua_lower = (ua_string or "").lower()
    return {
        "browser": _first_match(ua_lower, BROWSERS, UNKNOWN),
        "os": _first_match(ua_lower, SYSTEMS, UNKNOWN),
        "device_type": "Mobile" if any(h in ua_lower for h in MOBILE_HINTS) else "Desktop",
    }
