#!/usr/bin/env python3
"""
Genera la imagen de previsualización (Open Graph) del CV:
src/assets/images/og-cover.png y su equivalente en inglés.

Por qué existe: cuando pegas https://devapis.cloud/cv en LinkedIn, WhatsApp,
Slack o X, esas plataformas no renderizan la página. Leen las etiquetas
`og:` de la cabecera y dibujan una tarjeta. Sin `og:image` la tarjeta sale
como una línea de texto gris, justo en el momento en que más importa: cuando
alguien comparte tu perfil con quien decide.

La imagen es tipográfica a propósito. No hay foto del titular en el
repositorio, y una tarjeta de texto bien compuesta se lee mejor a 552 px de
ancho —el tamaño real al que LinkedIn la muestra en el feed— que una foto
recortada.

Medidas: 1200x630 es la proporción 1.91:1 que piden Open Graph y
`twitter:card=summary_large_image`. LinkedIn no recorta a ese tamaño; X puede
recortar unos píxeles arriba y abajo, así que el contenido va centrado
verticalmente con margen de sobra.

Los colores y la tipografía salen del mismo sistema de diseño que el sitio
(los tokens de src/styles.css), para que la tarjeta y la página se reconozcan
como la misma cosa.

    python3 tools/generar-og.py            # regenera las dos imágenes
    python3 tools/generar-og.py --check    # las valida sin reescribirlas

Sobre --check: comprueba lo que debe cumplirse siempre (que existan, que sean
PNG de 1200x630, que no engorden, y que el HTML las referencie con una URL
absoluta), no que los bytes coincidan. El texto se dibuja con las fuentes de
la máquina, así que exigir igualdad binaria haría fallar la comprobación en
cualquier equipo con otro juego de fuentes instalado, sin que nada esté mal.

Todo dato factual sale de PERFIL-CANONICO.md. No inventar nada aquí: los
textos de abajo son los mismos que ya están aprobados en las etiquetas
`og:title` y `og:description` de src/index.html y src/en/index.html.
"""
import argparse
import pathlib
import struct
import sys

# Pillow se importa dentro de generar() y no aquí: --check corre en CI, donde
# no hay motivo para instalar una dependencia solo para leer el ancho y el
# alto de un PNG, que están en los primeros 24 bytes del fichero.

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "src" / "assets" / "images"

ANCHO, ALTO = 1200, 630
PESO_MAXIMO_KB = 150

# ------------------------------------------------------------------ colores
# Tomados de los tokens de src/styles.css. Si allí cambian, cámbialos aquí.
FONDO = "#0f172a"          # --color-gray-900, el mismo <meta name="theme-color">
MARCA = "#0ea5e9"          # --color-primary
TITULO = "#f8fafc"         # --color-gray-50
CUERPO = "#cbd5e1"         # --color-gray-300
BORDE = "#334155"          # --color-gray-700
CHIP = "#e2e8f0"           # --color-gray-200

# ---------------------------------------------------------------- contenido

ES = {
    "salida": "og-cover.png",
    "eyebrow": "DEVAPIS.CLOUD/CV",
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend / Full-Stack Developer",
    "resumen": "15 años en TI · 5 construyendo APIs",
    "chips": ["Python", "Django", "FastAPI", "Node.js", "React", "PostgreSQL", "Docker"],
}

EN = {
    "salida": "og-cover-en.png",
    "eyebrow": "DEVAPIS.CLOUD/CV/EN",
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend / Full-Stack Developer",
    "resumen": "15 years in IT · 5 building APIs",
    "chips": ["Python", "Django", "FastAPI", "Node.js", "React", "PostgreSQL", "Docker"],
}

# ---------------------------------------------------------------- tipografía
# Se resuelve por ruta de fichero y no por nombre de familia: fontconfig
# sustituye en silencio una fuente que no encuentra, y el fallo aparecería
# como una imagen fea en vez de como un error.
CANDIDATAS = {
    "bold": [
        "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "semibold": [
        "/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf",
        "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


def fuente(peso: str, tamano: int):
    from PIL import ImageFont
    for ruta in CANDIDATAS[peso]:
        if pathlib.Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    sys.exit(
        f"No hay ninguna fuente '{peso}' de las conocidas en este sistema.\n"
        f"Buscadas: {', '.join(CANDIDATAS[peso])}\n"
        "Instala google-noto-sans-fonts (Fedora) o fonts-noto-core (Debian), "
        "o añade la ruta de tu fuente a CANDIDATAS."
    )


def ancho_de(dibujo, texto, font, espaciado=0):
    if not espaciado:
        return dibujo.textlength(texto, font=font)
    return sum(dibujo.textlength(c, font=font) for c in texto) + espaciado * (len(texto) - 1)


def texto_espaciado(dibujo, xy, texto, font, fill, espaciado):
    """PIL no sabe de letter-spacing, así que se dibuja carácter a carácter."""
    x, y = xy
    for caracter in texto:
        dibujo.text((x, y), caracter, font=font, fill=fill)
        x += dibujo.textlength(caracter, font=font) + espaciado


# ------------------------------------------------------------------ dibujo

def generar(datos: dict) -> pathlib.Path:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Falta Pillow. Instálalo con: pip install --user Pillow")

    imagen = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(imagen)

    # Barra de marca a la izquierda. Es lo único decorativo: da identidad
    # sin competir con el texto cuando la tarjeta se ve en miniatura.
    d.rectangle([0, 0, 13, ALTO], fill=MARCA)

    x = 96
    f_eyebrow = fuente("semibold", 24)
    f_nombre = fuente("bold", 78)
    f_titular = fuente("semibold", 44)
    f_resumen = fuente("regular", 32)
    f_chip = fuente("semibold", 25)

    y = 118
    texto_espaciado(d, (x, y), datos["eyebrow"], f_eyebrow, MARCA, espaciado=3.5)

    y += 76
    d.text((x, y), datos["nombre"], font=f_nombre, fill=TITULO)

    y += 104
    d.text((x, y), datos["titular"], font=f_titular, fill=MARCA)

    y += 74
    d.text((x, y), datos["resumen"], font=f_resumen, fill=CUERPO)

    # Fila de tecnologías: lo que un reclutador busca de un vistazo.
    y += 84
    alto_chip, pad_x, hueco = 52, 22, 14
    cx = x
    for etiqueta in datos["chips"]:
        ancho_chip = int(d.textlength(etiqueta, font=f_chip)) + pad_x * 2
        d.rounded_rectangle(
            [cx, y, cx + ancho_chip, y + alto_chip],
            radius=alto_chip // 2, outline=BORDE, width=2,
        )
        centro = (y + alto_chip / 2)
        d.text((cx + pad_x, centro), etiqueta, font=f_chip, fill=CHIP, anchor="lm")
        cx += ancho_chip + hueco

    destino = SALIDA / datos["salida"]
    imagen.save(destino, "PNG", optimize=True)
    return destino


# --------------------------------------------------------------- validación

def medidas_png(ruta: pathlib.Path):
    """Ancho y alto de un PNG leyendo su cabecera IHDR, sin Pillow."""
    cabecera = ruta.read_bytes()[:24]
    if len(cabecera) < 24 or cabecera[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", cabecera[16:24])


def comprobar() -> int:
    fallos = []
    for datos, pagina, url in (
        (ES, RAIZ / "src" / "index.html", "https://devapis.cloud/cv/assets/images/og-cover.png"),
        (EN, RAIZ / "src" / "en" / "index.html", "https://devapis.cloud/cv/assets/images/og-cover-en.png"),
    ):
        ruta = SALIDA / datos["salida"]
        if not ruta.exists():
            fallos.append(f"falta {ruta.relative_to(RAIZ)} — ejecuta tools/generar-og.py")
            continue
        medidas = medidas_png(ruta)
        if medidas is None:
            fallos.append(f"{ruta.name} no es un PNG válido")
        elif medidas != (ANCHO, ALTO):
            fallos.append(
                f"{ruta.name} mide {medidas[0]}x{medidas[1]}, "
                f"y las tarjetas exigen {ANCHO}x{ALTO}"
            )
        kb = ruta.stat().st_size / 1024
        if kb > PESO_MAXIMO_KB:
            fallos.append(f"{ruta.name} pesa {kb:.0f} KB, más del máximo de {PESO_MAXIMO_KB} KB")

        html = pagina.read_text(encoding="utf-8")
        # La URL tiene que ser absoluta: los rastreadores de LinkedIn y X no
        # resuelven rutas relativas ni respetan la etiqueta <base>.
        for etiqueta in (f'property="og:image" content="{url}"',
                         f'name="twitter:image" content="{url}"'):
            if etiqueta not in html:
                fallos.append(f"{pagina.relative_to(RAIZ)} no declara {etiqueta}")
        if 'name="twitter:card" content="summary_large_image"' not in html:
            fallos.append(
                f"{pagina.relative_to(RAIZ)} sigue en twitter:card=summary, "
                "que dibuja la tarjeta pequeña y sin imagen"
            )

    for fallo in fallos:
        print(f"  ✗ {fallo}")
    if fallos:
        return 1
    print("  ✓ las dos imágenes Open Graph existen, miden 1200x630 y están referenciadas")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--check", action="store_true",
                        help="valida las imágenes ya generadas sin reescribirlas")
    args = parser.parse_args()

    if args.check:
        return comprobar()

    SALIDA.mkdir(parents=True, exist_ok=True)
    for datos in (ES, EN):
        destino = generar(datos)
        kb = destino.stat().st_size / 1024
        print(f"  ✓ {destino.relative_to(RAIZ)} — {ANCHO}x{ALTO}, {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
