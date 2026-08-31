#!/usr/bin/env python3
"""
Genera el CV en formato ATS: documentos/Jose-Hernan-Varela-Backend-Developer.docx
y su PDF.

Qué es un CV "ATS" y por qué hace falta uno aparte: los portales de empleo
pasan el fichero por un lector automático antes de que lo vea una persona.
Esos lectores se atragantan con lo que hace bonita a la versión web —columnas,
tablas, iconos, cuadros de texto, texto dentro de imágenes— y devuelven los
campos desordenados o vacíos. Un candidato bueno se descarta por un problema
de maquetación.

Por eso este documento es deliberadamente feo: una sola columna, sin tablas,
sin iconos, encabezados en mayúsculas con los nombres que esos lectores
esperan, fechas en MM/AAAA y tipografía estándar. La versión bonita sigue
siendo devapis.cloud/cv y su botón de impresión.

El .docx se construye a mano (es un ZIP con XML) para no añadir dependencias
al repositorio, y el PDF sale de él con LibreOffice, de modo que ambos
formatos vienen del mismo origen y no pueden divergir.

    python3 tools/generar-cv-ats.py
    python3 tools/generar-cv-ats.py --en     # versión en inglés

Todo dato factual sale de PERFIL-CANONICO.md. No inventar nada aquí.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "src" / "documentos"

# ---------------------------------------------------------------- contenido

ES = {
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend Developer",
    "contacto": [
        "jhernan33@gmail.com | Táchira, Venezuela | UTC-4 | Disponible para trabajo totalmente remoto",
        "https://devapis.cloud/cv | https://github.com/jhernan33 | https://www.linkedin.com/in/jhernan-13465028",
    ],
    "resumen_titulo": "PERFIL PROFESIONAL",
    "resumen": (
        "Senior Backend Developer con 14 años en tecnologías de la información, "
        "7 de ellos construyendo APIs con Python. Trabajo tanto el backend como la "
        "infraestructura donde corre: servidores Linux, contenedores, proxy inverso "
        "y bases de datos. Disponible para trabajo remoto con equipos de "
        "Latinoamérica, Estados Unidos y Europa."
    ),
    "experiencia_titulo": "EXPERIENCIA PROFESIONAL",
    "experiencia": [
        {
            "puesto": "Jefe de Informática",
            "empresa": "PCVARELAVENEZUELA",
            "fechas": "05/2011 - Presente",
            "vinculo": "Tiempo completo",
            "puntos": [
                "Lidero el departamento de TI y la infraestructura tecnológica completa.",
                "Desarrollo sistemas internos con Python y Django que automatizan procesos antes manuales.",
                "Administro la infraestructura Linux que sostiene la operación en producción.",
                "Implanté despliegues contenerizados y reproducibles con Docker, en sustitución del despliegue manual.",
            ],
            "stack": "Python, Django, PostgreSQL, Docker, Linux, Traefik, Nginx",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Delzam",
            "fechas": "06/2022 - 12/2023",
            "vinculo": "Freelance, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "APIs REST con Django y Django REST Framework para un sistema de gestión empresarial.",
                "Integración de servicios sobre esa API.",
                "Optimización de consultas PostgreSQL en las rutas de mayor uso.",
            ],
            "stack": "Django, Django REST Framework, PostgreSQL, Docker, Vue.js",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Zippyttech Tecnología e Innovación",
            "fechas": "12/2019 - 12/2022",
            "vinculo": "Consultoría, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "Arquitectura de microservicios en PHP con Laravel y Lumen.",
                "Integración con APIs de terceros y comunicación en tiempo real con WebSockets.",
                "Automatización de despliegues mediante CI/CD.",
                "Seguridad con JWT y control de acceso granular.",
            ],
            "stack": "PHP, Laravel, Lumen, microservicios, WebSockets, PostgreSQL, MySQL",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Alcaldía del Municipio Guásimos",
            "fechas": "02/2020 - 05/2022",
            "vinculo": "Contrato, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "Plataforma de gestión municipal para trámites ciudadanos.",
                "Sistemas de información geográfica con PostGIS.",
                "Administración de los servidores que dan servicio a la plataforma.",
                "Integración con sistemas gubernamentales existentes.",
            ],
            "stack": "Python, Django, PostgreSQL, PostGIS",
        },
    ],
    "habilidades_titulo": "HABILIDADES TÉCNICAS",
    "habilidades": [
        ("Lenguajes", "Python, JavaScript (ES6+), PHP, SQL / PL-pgSQL"),
        ("Frameworks backend", "Django, Django REST Framework, FastAPI, Laravel, Lumen, Express.js"),
        ("Frontend", "Vue.js, HTML5, CSS3, JavaScript sin dependencias"),
        ("Bases de datos", "PostgreSQL, PostGIS, MySQL, Redis, SQL Server"),
        ("Infraestructura", "Docker, Docker Compose, Traefik, Nginx, Linux (Ubuntu, Debian, Fedora), Git, Shell scripting"),
        ("APIs y arquitectura", "REST, JWT, WebSockets, microservicios"),
    ],
    "proyectos_titulo": "PROYECTOS",
    "proyectos": [
        {
            "nombre": "Portafolio profesional y backend de analítica",
            "url": "https://github.com/jhernan33/portfolio-devapis",
            "puntos": [
                "Sitio estático sin dependencias servido por Nginx, con servicio propio de analítica en FastAPI y PostgreSQL, tras Traefik y sobre Docker Compose.",
                "Las direcciones IP de los visitantes no se almacenan: se guardan la red truncada y un hash con sal.",
                "La autenticación vive en la aplicación y no en el proxy, de modo que la protección viaja con el código.",
            ],
            "stack": "FastAPI, PostgreSQL, Docker, Traefik, Nginx",
        },
        {
            "nombre": "Sistema de gestión municipal",
            "url": "",
            "puntos": [
                "API REST para la tramitación de solicitudes ciudadanas.",
                "Información geográfica del municipio con PostGIS.",
                "Panel administrativo con Vue.js.",
            ],
            "stack": "Django, PostgreSQL, PostGIS, Docker",
        },
        {
            "nombre": "Migración de sistema legacy a microservicios",
            "url": "",
            "puntos": [
                "Migración de un monolito a una arquitectura de microservicios.",
                "Automatización de los despliegues mediante CI/CD.",
            ],
            "stack": "Laravel, Lumen, PostgreSQL",
        },
    ],
    "educacion_titulo": "EDUCACIÓN",
    "educacion": [
        ("TSU en Informática", "IUFRONT", "1998 - 2000"),
        ("Desarrollador e-Business", "IUTAI", "2008 - 2009"),
    ],
    "certificaciones_titulo": "CERTIFICACIONES",
    "certificaciones_intro": "21 certificaciones y más de 229 horas de formación continua entre 2023 y 2026, todas de Platzi. Las más relevantes para un puesto backend:",
    "certificaciones": [
        "Fundamentos de Python - Platzi - 10/2025",
        "FastAPI - Platzi - 08/2025",
        "Django - Platzi - 09/2024",
        "PostgreSQL - Platzi - 05/2025",
        "Docker: Fundamentos - Platzi - 10/2025",
        "Introducción a la Administración de Servidores Linux - Platzi - 07/2026",
        "Ciberseguridad Preventiva - Platzi - 03/2026",
        "Backend con ExpressJS - Platzi - 04/2025",
        "Claude Code - Platzi - 01/2026",
    ],
    "idiomas_titulo": "IDIOMAS",
    "idiomas": [
        "Español: nativo.",
        "Inglés: lectura y escritura técnica fluidas (B2). Conversacional en desarrollo (A2-B1). "
        "Cómodo trabajando con documentación, revisiones de código y comunicación asíncrona en inglés.",
    ],
}

EN = {
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend Developer",
    "contacto": [
        "jhernan33@gmail.com | Táchira, Venezuela | UTC-4 | Available for fully remote work",
        "https://devapis.cloud/cv/en/ | https://github.com/jhernan33 | https://www.linkedin.com/in/jhernan-13465028",
    ],
    "resumen_titulo": "PROFESSIONAL SUMMARY",
    "resumen": (
        "Senior Backend Developer with 14 years in IT, 7 of them building APIs with "
        "Python. I work across both the backend and the infrastructure it runs on: "
        "Linux servers, containers, reverse proxy and databases. Available for remote "
        "work with teams in Latin America, the United States and Europe."
    ),
    "experiencia_titulo": "PROFESSIONAL EXPERIENCE",
    "experiencia": [
        {
            "puesto": "IT Manager",
            "empresa": "PCVARELAVENEZUELA",
            "fechas": "05/2011 - Present",
            "vinculo": "Full-time",
            "puntos": [
                "I lead the IT department and the full technology infrastructure.",
                "I build internal systems in Python and Django that automate previously manual processes.",
                "I administer the Linux infrastructure that keeps production running.",
                "I introduced containerised, reproducible deployments with Docker, replacing the manual process.",
            ],
            "stack": "Python, Django, PostgreSQL, Docker, Linux, Traefik, Nginx",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Delzam",
            "fechas": "06/2022 - 12/2023",
            "vinculo": "Freelance, alongside PCVARELAVENEZUELA",
            "puntos": [
                "REST APIs with Django and Django REST Framework for a business management system.",
                "Service integration on top of that API.",
                "PostgreSQL query optimisation on the most heavily used endpoints.",
            ],
            "stack": "Django, Django REST Framework, PostgreSQL, Docker, Vue.js",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Zippyttech Tecnología e Innovación",
            "fechas": "12/2019 - 12/2022",
            "vinculo": "Consulting, alongside PCVARELAVENEZUELA",
            "puntos": [
                "Microservice architecture in PHP with Laravel and Lumen.",
                "Third-party API integration and real-time communication over WebSockets.",
                "Deployment automation through CI/CD.",
                "JWT security and fine-grained access control.",
            ],
            "stack": "PHP, Laravel, Lumen, microservices, WebSockets, PostgreSQL, MySQL",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Guásimos Municipality (Local Government)",
            "fechas": "02/2020 - 05/2022",
            "vinculo": "Contract, alongside PCVARELAVENEZUELA",
            "puntos": [
                "Municipal platform for citizen administrative procedures.",
                "Geographic information systems with PostGIS.",
                "Administration of the servers running the platform.",
                "Integration with existing government systems.",
            ],
            "stack": "Python, Django, PostgreSQL, PostGIS",
        },
    ],
    "habilidades_titulo": "TECHNICAL SKILLS",
    "habilidades": [
        ("Languages", "Python, JavaScript (ES6+), PHP, SQL / PL-pgSQL"),
        ("Backend frameworks", "Django, Django REST Framework, FastAPI, Laravel, Lumen, Express.js"),
        ("Frontend", "Vue.js, HTML5, CSS3, dependency-free JavaScript"),
        ("Databases", "PostgreSQL, PostGIS, MySQL, Redis, SQL Server"),
        ("Infrastructure", "Docker, Docker Compose, Traefik, Nginx, Linux (Ubuntu, Debian, Fedora), Git, shell scripting"),
        ("APIs and architecture", "REST, JWT, WebSockets, microservices"),
    ],
    "proyectos_titulo": "PROJECTS",
    "proyectos": [
        {
            "nombre": "Professional portfolio and analytics backend",
            "url": "https://github.com/jhernan33/portfolio-devapis",
            "puntos": [
                "Dependency-free static site served by Nginx, with a self-hosted analytics service in FastAPI and PostgreSQL, behind Traefik and running on Docker Compose.",
                "Visitor IP addresses are never stored: only the truncated network and a salted hash.",
                "Authentication lives in the application rather than the proxy, so the protection ships with the code.",
            ],
            "stack": "FastAPI, PostgreSQL, Docker, Traefik, Nginx",
        },
        {
            "nombre": "Municipal management system",
            "url": "",
            "puntos": [
                "REST API handling citizen service requests.",
                "Geographic data for the municipality with PostGIS.",
                "Administrative dashboard built with Vue.js.",
            ],
            "stack": "Django, PostgreSQL, PostGIS, Docker",
        },
        {
            "nombre": "Legacy system migration to microservices",
            "url": "",
            "puntos": [
                "Migration from a monolith to a microservice architecture.",
                "Deployment automation through CI/CD.",
            ],
            "stack": "Laravel, Lumen, PostgreSQL",
        },
    ],
    "educacion_titulo": "EDUCATION",
    "educacion": [
        ("Associate Degree in Computer Science", "IUFRONT", "1998 - 2000"),
        ("e-Business Developer", "IUTAI", "2008 - 2009"),
    ],
    "certificaciones_titulo": "CERTIFICATIONS",
    "certificaciones_intro": "21 certifications and over 229 hours of continuous learning between 2023 and 2026, all from Platzi. Most relevant to a backend role:",
    "certificaciones": [
        "Python Fundamentals - Platzi - 10/2025",
        "FastAPI - Platzi - 08/2025",
        "Django - Platzi - 09/2024",
        "PostgreSQL - Platzi - 05/2025",
        "Docker: Fundamentals - Platzi - 10/2025",
        "Introduction to Linux Server Administration - Platzi - 07/2026",
        "Preventive Cybersecurity - Platzi - 03/2026",
        "Backend with ExpressJS - Platzi - 04/2025",
        "Claude Code - Platzi - 01/2026",
    ],
    "idiomas_titulo": "LANGUAGES",
    "idiomas": [
        "Spanish: native.",
        "English: fluent technical reading and writing (B2). Spoken English improving (A2-B1). "
        "Comfortable with English documentation, code reviews and asynchronous written communication.",
    ],
}

# ---------------------------------------------------------------- docx

# Arial 11 pt. Las medidas de OOXML van en medios puntos, de ahí el 22.
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>
</w:styles>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def parrafo(texto, negrita=False, tam=None, espacio_antes=0, sangria=0, mayus=False):
    """Un párrafo suelto. Sin tablas ni cuadros: es lo que un lector ATS entiende."""
    rpr = "<w:rPr>"
    if negrita:
        rpr += "<w:b/>"
    if tam:
        rpr += f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>'
    if mayus:
        rpr += "<w:caps/>"
    rpr += "</w:rPr>"
    ppr = f'<w:pPr><w:spacing w:before="{espacio_antes}" w:after="40"/>'
    if sangria:
        ppr += f'<w:ind w:left="{sangria}"/>'
    ppr += "</w:pPr>"
    return f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space=\"preserve\">{escape(texto)}</w:t></w:r></w:p>"


def encabezado(texto):
    """Encabezado de sección. En mayúsculas y con los nombres estándar que los
    lectores automáticos buscan para trocear el documento."""
    return parrafo(texto, negrita=True, tam=24, espacio_antes=180)


def vineta(texto):
    """Viñeta como guion literal. Las listas numeradas de OOXML dependen de
    numbering.xml y algunos lectores las pierden; un guion siempre sobrevive."""
    return parrafo(f"- {texto}", sangria=284)


def construir_documento(d):
    p = []
    p.append(parrafo(d["nombre"], negrita=True, tam=32))
    p.append(parrafo(d["titular"], tam=24))
    for linea in d["contacto"]:
        p.append(parrafo(linea))

    p.append(encabezado(d["resumen_titulo"]))
    p.append(parrafo(d["resumen"]))

    p.append(encabezado(d["experiencia_titulo"]))
    for e in d["experiencia"]:
        p.append(parrafo(f'{e["puesto"]} - {e["empresa"]}', negrita=True, espacio_antes=120))
        p.append(parrafo(f'{e["fechas"]} | {e["vinculo"]}'))
        for punto in e["puntos"]:
            p.append(vineta(punto))
        p.append(parrafo(f'Tecnologías: {e["stack"]}'))

    p.append(encabezado(d["habilidades_titulo"]))
    for categoria, valores in d["habilidades"]:
        p.append(parrafo(f"{categoria}: {valores}"))

    p.append(encabezado(d["proyectos_titulo"]))
    for pr in d["proyectos"]:
        p.append(parrafo(pr["nombre"], negrita=True, espacio_antes=120))
        if pr["url"]:
            p.append(parrafo(pr["url"]))
        for punto in pr["puntos"]:
            p.append(vineta(punto))
        p.append(parrafo(f'Tecnologías: {pr["stack"]}'))

    p.append(encabezado(d["educacion_titulo"]))
    for titulo, centro, fechas in d["educacion"]:
        p.append(parrafo(f"{titulo} - {centro} - {fechas}"))

    p.append(encabezado(d["certificaciones_titulo"]))
    p.append(parrafo(d["certificaciones_intro"]))
    for c in d["certificaciones"]:
        p.append(vineta(c))

    p.append(encabezado(d["idiomas_titulo"]))
    for i in d["idiomas"]:
        p.append(parrafo(i))

    cuerpo = "".join(p)
    # Una sola columna, A4, márgenes de 2 cm (1134 twips).
    seccion = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
               '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
               'w:header="0" w:footer="0" w:gutter="0"/><w:cols w:space="708"/></w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{cuerpo}{seccion}</w:body></w:document>")


def escribir_docx(destino: pathlib.Path, d: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/document.xml", construir_documento(d))


def convertir_a_pdf(docx: pathlib.Path) -> pathlib.Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("  LibreOffice no está disponible; el PDF hay que generarlo aparte.",
              file=sys.stderr)
        return None
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)],
        check=True, capture_output=True, timeout=180)
    return docx.with_suffix(".pdf")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--en", action="store_true", help="generar la versión en inglés")
    ap.add_argument("--check", action="store_true",
                    help="comprobar que los documentos versionados están al día")
    args = ap.parse_args()

    datos = EN if args.en else ES
    sufijo = "-EN" if args.en else ""
    docx = SALIDA / f"Jose-Hernan-Varela-Backend-Developer{sufijo}.docx"

    if args.check:
        # Se compara word/document.xml y no el fichero entero: un ZIP guarda
        # marcas de tiempo, así que dos .docx con el mismo contenido nunca son
        # idénticos byte a byte.
        if not docx.exists():
            sys.exit(f"Falta {docx.relative_to(RAIZ)}. Ejecuta: python3 tools/generar-cv-ats.py"
                     f"{' --en' if args.en else ''}")
        with zipfile.ZipFile(docx) as z:
            actual = z.read("word/document.xml").decode("utf-8")
        if actual != construir_documento(datos):
            sys.exit(f"{docx.relative_to(RAIZ)} está desactualizado. "
                     f"Ejecuta: python3 tools/generar-cv-ats.py{' --en' if args.en else ''}")
        print(f"  {docx.relative_to(RAIZ)} está al día")
        return

    escribir_docx(docx, datos)
    print(f"  {docx.relative_to(RAIZ)}  ({docx.stat().st_size:,} bytes)")

    pdf = convertir_a_pdf(docx)
    if pdf and pdf.exists():
        print(f"  {pdf.relative_to(RAIZ)}  ({pdf.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
