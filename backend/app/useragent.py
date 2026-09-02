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

UNKNOWN = "Unknown"


def _first_match(ua_lower: str, rules, default: str) -> str:
    return next((label for hint, label in rules if hint in ua_lower), default)


def parse_user_agent(ua_string: str) -> dict:
    """Devuelve {"browser", "os", "device_type"} a partir de la cadena."""
    ua_lower = (ua_string or "").lower()
    return {
        "browser": _first_match(ua_lower, BROWSERS, UNKNOWN),
        "os": _first_match(ua_lower, SYSTEMS, UNKNOWN),
        "device_type": "Mobile" if any(h in ua_lower for h in MOBILE_HINTS) else "Desktop",
    }
