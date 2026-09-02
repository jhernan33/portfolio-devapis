"""
Qué versión del CV se ha visitado.

El valor lo manda el navegador, así que se trata como lo que es: una entrada
no fiable. No se guarda nunca en crudo; se compara contra un conjunto cerrado
y todo lo que no esté en él se registra como "otro". Así la columna no puede
crecer con rutas inventadas ni convertirse en un vector para meter texto
arbitrario en la base y, de rebote, en el panel.

Existe porque hasta ahora no había forma de saber si la versión en inglés
—que se genera, se traduce y se mantiene— la lee alguien.
"""

# Ruta que envía el navegador -> etiqueta que se guarda.
RUTAS = {
    "/cv": "/cv",
    "/cv/": "/cv",
    "/cv/index.html": "/cv",
    "/cv/en": "/cv/en",
    "/cv/en/": "/cv/en",
    "/cv/en/index.html": "/cv/en",
}

OTRA = "otro"

# Etiqueta -> idioma, para leer el desglose sin tener que interpretar rutas.
IDIOMAS = {"/cv": "es", "/cv/en": "en"}


def normalizar_pagina(valor) -> str | None:
    """
    Traduce lo que manda el navegador a una de las etiquetas conocidas.

    Devuelve None si no viene nada (el frontend antiguo no manda cuerpo, y esas
    visitas siguen siendo válidas) y "otro" si viene algo que no reconocemos.
    """
    if valor is None:
        return None
    if not isinstance(valor, str):
        return OTRA
    return RUTAS.get(valor.strip().rstrip() or "/", OTRA)
