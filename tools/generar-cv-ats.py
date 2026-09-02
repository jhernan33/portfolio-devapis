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
    python3 tools/generar-cv-ats.py --en           # versión en inglés
    python3 tools/generar-cv-ats.py --marcadores   # borrador con [CONFIRMAR: ___]

La experiencia se presenta en dos bloques: el puesto principal, y debajo los
cuatro compromisos que fueron SIMULTÁNEOS a él. Leídos en una lista corrida,
cinco empleos que se solapan entre 2019 y 2024 parecen un error de fechas, y
es de las primeras cosas que un reclutador descarta sin preguntar.

Todo dato factual sale de PERFIL-CANONICO.md. No inventar nada aquí, y las
cifras menos que nada: van en METRICAS, vacías hasta que el titular las
confirme con evidencia.
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

# Los borradores con marcadores NO van a src/: todo lo que hay en esa carpeta
# lo publica Nginx, y un reclutador podría descargarse un CV con "[CONFIRMAR:
# ___]" dentro. Ese directorio está en .gitignore.
BORRADORES = RAIZ / ".borradores"

# ---------------------------------------------------------------- métricas
#
# Un CV sin una sola cifra se lee por encima; un CV con cifras que no puedes
# defender en entrevista es peor. Por eso las métricas no están escritas dentro
# de las viñetas, sino aquí, y cada viñeta trae dos redacciones: la cualitativa,
# que es la que se publica mientras el dato no exista, y la cuantificada, que
# solo aparece cuando el valor está confirmado.
#
# **Ninguna IA rellena esta tabla.** Los valores los aporta el titular con
# evidencia (PERFIL-CANONICO.md, sección 5: "si no puedes explicar cómo lo
# mediste en 20 segundos frente a un entrevistador, se elimina").
#
# `python3 tools/generar-cv-ats.py --marcadores` genera en .borradores/ una
# copia con "[CONFIRMAR: ___]" en el sitio exacto de cada hueco, para saber qué
# hay que medir sin publicar nada a medias.
# Hay un diccionario por idioma porque los separadores decimales y de millar no
# son los mismos: "0,29 s" en español es "0.29 s" en inglés, y publicar el
# formato equivocado delata que el documento está traducido a medias.
METRICAS = {
    # PCVARELAVENEZUELA no aparece aquí a propósito. Se valoró cuantificar los
    # sistemas internos, el tamaño de la base y los tiempos de despliegue de ese
    # puesto, y la decisión fue dejar esas tres viñetas en cualitativo: no hay
    # medición que defender. Es la regla del perfil canónico —"si no puedes
    # explicar cómo lo mediste en 20 segundos frente a un entrevistador, se
    # reescribe en cualitativo"— y una cifra que no se sostiene en entrevista
    # hace más daño que su ausencia.
    "es": {
        # --- Delzam · medido sobre el sistema, endpoint por endpoint ---
        # De la tabla de medición: la ruta más pesada pasó de más de 9.000
        # consultas y 62 s a una sola consulta y 0,29 s. Se publica esa, no el
        # factor ×214: el "antes y después" se defiende en entrevista, un
        # multiplicador suelto invita a preguntar de dónde sale.
        "consultas_antes": "más de 9.000 consultas y 62 s",
        "consultas_despues": "1 consulta y 0,29 s",

        # --- Zippyttech ---
        "microservicios": "3",

        # --- Portafolio propio ---
        "anio_infra": "2024",
        "despliegue_propio": "18 s",
    },
    "en": {
        "consultas_antes": "over 9,000 queries and 62 s",
        "consultas_despues": "a single query and 0.29 s",
        "microservicios": "3",
        "anio_infra": "2024",
        "despliegue_propio": "18 s",
    },
}

SIN_CONFIRMAR = "[CONFIRMAR: ___]"


def resolver_punto(punto, cifras: dict, marcadores: bool) -> str:
    """
    Devuelve el texto de una viñeta.

    Una viñeta es una cadena, o un diccionario con `base` (redacción
    cualitativa) y `cuantificada` (plantilla con huecos `{clave}`). La versión
    con cifras solo sale si TODAS sus métricas están confirmadas; si falta
    alguna se publica la cualitativa, que siempre es cierta.
    """
    if isinstance(punto, str):
        return punto

    if all(cifras.get(c) for c in punto["metricas"]):
        return punto["cuantificada"].format(**cifras)
    if marcadores:
        valores = {c: (cifras.get(c) or SIN_CONFIRMAR) for c in punto["metricas"]}
        return punto["cuantificada"].format(**valores)
    return punto["base"]

# ---------------------------------------------------------------- contenido

ES = {
    "idioma": "es",
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend Developer",
    "contacto": [
        "jhernan33@gmail.com | Táchira, Venezuela | UTC-4 | Disponible para trabajo totalmente remoto",
        "https://devapis.cloud/cv | https://github.com/jhernan33 | https://www.linkedin.com/in/jhernanvarela",
    ],
    "resumen_titulo": "PERFIL PROFESIONAL",
    "resumen": (
        "Senior Backend Developer con 15 años en tecnologías de la información, "
        "5 de ellos construyendo APIs con Python. Trabajo tanto el backend como la "
        "infraestructura donde corre: servidores Linux, contenedores, proxy inverso "
        "y bases de datos. Disponible para trabajo remoto con equipos de "
        "Latinoamérica, Estados Unidos y Europa."
    ),
    # La etiqueta va aquí y no escrita a fuego en construir_documento():
    # estaba en español también en el documento inglés, en las siete líneas
    # de stack. Un lector automático que busca "Technologies:" no la
    # reconocía, y quien lo abría veía un descuido de idioma.
    "stack_etiqueta": "Tecnologías",
    "experiencia_titulo": "EXPERIENCIA PROFESIONAL",
    # El puesto principal va solo y primero. Los otros cuatro fueron simultáneos a
    # él, no consecutivos: leídos en una lista corrida, cinco empleos que se
    # solapan entre 2019 y 2024 parecen un error de fechas o una exageración, y
    # es lo primero que un reclutador descarta sin preguntar.
    "experiencia": [
        {
            "puesto": "Jefe de Informática",
            "empresa": "PCVARELAVENEZUELA",
            "fechas": "05/2011 – Presente",
            "vinculo": "Tiempo completo",
            "puntos": [
                # "Coordinando un equipo de 1" se lee mal y vende menos que la
                # verdad: es el único responsable del área, así que la propiedad
                # del trabajo es completa. Para un puesto remoto eso es
                # exactamente lo que se busca.
                "Único responsable del departamento de TI y de la infraestructura tecnológica"
                " completa: desarrollo, servidores, bases de datos y despliegue.",
                "Desarrollo sistemas internos con Python y Django que automatizan procesos"
                " antes manuales.",
                "Administro la infraestructura Linux que sostiene la operación en producción.",
                "Implanté despliegues contenerizados y reproducibles con Docker, en sustitución"
                " del despliegue manual.",
            ],
            "stack": "Python, Django, PostgreSQL, Docker, Linux, Traefik, Nginx",
        },
    ],
    "experiencia_paralela_titulo": "Experiencia paralela / freelance",
    "experiencia_paralela_nota": (
        "Los cuatro compromisos siguientes se desarrollaron de forma simultánea al puesto de "
        "Jefe de Informática, no como empleos consecutivos."
    ),
    "experiencia_paralela": [
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Gsamples-Global (Chile)",
            "fechas": "08/2023 – 07/2024",
            "vinculo": "Freelance, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "Prototipo de la API REST de un sistema de trazabilidad de muestras geológicas"
                " mineras.",
                "Modelado del ciclo de vida del testigo de sondaje, desde que sale del terreno"
                " hasta su almacenamiento y análisis en laboratorio.",
                "Despliegue en un VPS de Contabo con Docker y Traefik.",
            ],
            "stack": "PHP, Laravel, MySQL, Docker, Traefik",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Delzam",
            "fechas": "06/2022 – 12/2023",
            "vinculo": "Freelance, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "APIs REST con Django y Django REST Framework para un sistema de gestión empresarial.",
                "Integración de servicios sobre esa API.",
                {
                    "base": "Optimización de consultas PostgreSQL en las rutas de mayor uso.",
                    "cuantificada": "Eliminación de consultas N+1 en las rutas de mayor uso: el"
                                    " endpoint más pesado pasó de {consultas_antes} a"
                                    " {consultas_despues}.",
                    "metricas": ["consultas_antes", "consultas_despues"],
                },
            ],
            "stack": "Django, Django REST Framework, PostgreSQL, Docker, Vue.js",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Zippyttech Tecnología e Innovación",
            "fechas": "12/2019 – 12/2022",
            "vinculo": "Consultoría, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                {
                    "base": "Arquitectura de microservicios en PHP con Laravel y Lumen.",
                    "cuantificada": "Arquitectura de {microservicios} microservicios en PHP con"
                                    " Laravel y Lumen.",
                    "metricas": ["microservicios"],
                },
                "Integración con APIs de terceros y comunicación en tiempo real con WebSockets.",
                "Automatización de despliegues mediante CI/CD.",
                "Seguridad con JWT y control de acceso granular.",
            ],
            "stack": "PHP, Laravel, Lumen, microservicios, WebSockets, PostgreSQL, MySQL",
        },
        {
            "puesto": "Desarrollador Backend",
            "empresa": "Alcaldía del Municipio Guásimos",
            "fechas": "02/2020 – 05/2022",
            "vinculo": "Contrato, en paralelo a PCVARELAVENEZUELA",
            "puntos": [
                "Actualización y optimización del sistema de partidas del registro civil.",
                "Portal web del municipio.",
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
                {
                    "base": "Infraestructura propia en producción, operada de forma"
                            " ininterrumpida.",
                    "cuantificada": "Infraestructura propia en producción, operada de forma"
                                    " ininterrumpida desde {anio_infra}.",
                    "metricas": ["anio_infra"],
                },
                {
                    "base": "Despliegue automatizado con verificación externa y vuelta atrás"
                            " automática si la comprobación falla.",
                    "cuantificada": "Despliegue automatizado en {despliegue_propio} —construcción,"
                                    " recreación, espera a estado sano y verificación externa— con"
                                    " vuelta atrás automática si la comprobación falla.",
                    "metricas": ["despliegue_propio"],
                },
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
    "certificaciones_intro": "21 certificaciones y más de 229 horas de formación continua entre 2023 y 2026, todas de Platzi (plataforma líder de educación tech en Latinoamérica, más de 1 millón de estudiantes). Las más relevantes para un puesto backend:",
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
    "idioma": "en",
    "nombre": "José Hernán Varela",
    "titular": "Senior Backend Developer",
    "contacto": [
        "jhernan33@gmail.com | Táchira, Venezuela | UTC-4 | Available for fully remote work",
        "https://devapis.cloud/cv/en/ | https://github.com/jhernan33 | https://www.linkedin.com/in/jhernanvarela",
    ],
    "resumen_titulo": "PROFESSIONAL SUMMARY",
    "resumen": (
        "Senior Backend Developer with 15 years in IT, 5 of them building APIs with "
        "Python. I work across both the backend and the infrastructure it runs on: "
        "Linux servers, containers, reverse proxy and databases. Available for remote "
        "work with teams in Latin America, the United States and Europe."
    ),
    "stack_etiqueta": "Technologies",
    "experiencia_titulo": "PROFESSIONAL EXPERIENCE",
    # Fechas en "Mon YYYY - Mon YYYY": fuera de Latinoamérica, "05/2011" se lee
    # con frecuencia como día/mes, y una fecha ambigua en la primera línea de un
    # puesto es exactamente donde un lector automático se equivoca.
    "experiencia": [
        {
            "puesto": "IT Manager",
            "empresa": "PCVARELAVENEZUELA",
            "fechas": "May 2011 – Present",
            "vinculo": "Full-time",
            "puntos": [
                "Sole owner of the IT department and the full technology infrastructure:"
                " development, servers, databases and deployment.",
                "I build internal systems in Python and Django that automate previously manual"
                " processes.",
                "I administer the Linux infrastructure that keeps production running.",
                "I introduced containerised, reproducible deployments with Docker, replacing the"
                " manual process.",
            ],
            "stack": "Python, Django, PostgreSQL, Docker, Linux, Traefik, Nginx",
        },
    ],
    "experiencia_paralela_titulo": "Concurrent / Freelance Engagements",
    "experiencia_paralela_nota": (
        "The four engagements below ran concurrently with the IT Manager role, not as "
        "consecutive positions."
    ),
    "experiencia_paralela": [
        {
            "puesto": "Backend Developer",
            "empresa": "Gsamples-Global (Chile)",
            "fechas": "Aug 2023 – Jul 2024",
            "vinculo": "Freelance, alongside PCVARELAVENEZUELA",
            "puntos": [
                "Prototype of the REST API for a mining geological sample traceability system.",
                "Modelled the life cycle of a drill core sample, from the field to storage and"
                " laboratory analysis.",
                "Deployment on a Contabo VPS with Docker and Traefik.",
            ],
            "stack": "PHP, Laravel, MySQL, Docker, Traefik",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Delzam",
            "fechas": "Jun 2022 – Dec 2023",
            "vinculo": "Freelance, alongside PCVARELAVENEZUELA",
            "puntos": [
                "REST APIs with Django and Django REST Framework for a business management system.",
                "Service integration on top of that API.",
                {
                    "base": "PostgreSQL query optimisation on the most heavily used endpoints.",
                    "cuantificada": "Eliminated N+1 queries on the most heavily used endpoints:"
                                    " the heaviest one went from {consultas_antes} to"
                                    " {consultas_despues}.",
                    "metricas": ["consultas_antes", "consultas_despues"],
                },
            ],
            "stack": "Django, Django REST Framework, PostgreSQL, Docker, Vue.js",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Zippyttech Tecnología e Innovación",
            "fechas": "Dec 2019 – Dec 2022",
            "vinculo": "Consulting, alongside PCVARELAVENEZUELA",
            "puntos": [
                {
                    "base": "Microservice architecture in PHP with Laravel and Lumen.",
                    "cuantificada": "Architecture of {microservicios} microservices in PHP with"
                                    " Laravel and Lumen.",
                    "metricas": ["microservicios"],
                },
                "Third-party API integration and real-time communication over WebSockets.",
                "Deployment automation through CI/CD.",
                "JWT security and fine-grained access control.",
            ],
            "stack": "PHP, Laravel, Lumen, microservices, WebSockets, PostgreSQL, MySQL",
        },
        {
            "puesto": "Backend Developer",
            "empresa": "Guásimos Municipality (Local Government)",
            "fechas": "Feb 2020 – May 2022",
            "vinculo": "Contract, alongside PCVARELAVENEZUELA",
            "puntos": [
                "Overhaul and optimisation of the civil registry records system.",
                "Municipal public website.",
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
                {
                    "base": "Self-managed infrastructure in production, running without"
                            " interruption.",
                    "cuantificada": "Self-managed infrastructure in production, running without"
                                    " interruption since {anio_infra}.",
                    "metricas": ["anio_infra"],
                },
                {
                    "base": "Automated deployment with external verification and automatic"
                            " rollback when the check fails.",
                    "cuantificada": "Automated deployment in {despliegue_propio} — image build,"
                                    " container recreation, health wait and external verification"
                                    " — with automatic rollback when the check fails.",
                    "metricas": ["despliegue_propio"],
                },
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
    "certificaciones_intro": "21 certifications and over 229 hours of continuous learning between 2023 and 2026, all from Platzi (leading tech education platform in Latin America, over 1 million students). Most relevant to a backend role:",
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


def bloque_experiencia(d, e, cifras, marcadores):
    """Un puesto: cabecera, fechas, viñetas y stack. Sin tablas ni columnas."""
    p = [
        parrafo(f'{e["puesto"]} - {e["empresa"]}', negrita=True, espacio_antes=120),
        parrafo(f'{e["fechas"]} | {e["vinculo"]}'),
    ]
    for punto in e["puntos"]:
        p.append(vineta(resolver_punto(punto, cifras, marcadores)))
    p.append(parrafo(f'{d["stack_etiqueta"]}: {e["stack"]}'))
    return p


def construir_documento(d, marcadores: bool = False):
    cifras = METRICAS[d["idioma"]]
    p = []
    p.append(parrafo(d["nombre"], negrita=True, tam=32))
    p.append(parrafo(d["titular"], tam=24))
    for linea in d["contacto"]:
        p.append(parrafo(linea))

    p.append(encabezado(d["resumen_titulo"]))
    p.append(parrafo(d["resumen"]))

    p.append(encabezado(d["experiencia_titulo"]))
    for e in d["experiencia"]:
        p.extend(bloque_experiencia(d, e, cifras, marcadores))

    # Subtítulo en negrita, no un encabezado de sección: un segundo título en
    # mayúsculas aquí haría que un lector automático diera por cerrada la
    # sección de experiencia y tratara lo de abajo como otra cosa.
    p.append(parrafo(d["experiencia_paralela_titulo"], negrita=True, espacio_antes=180))
    p.append(parrafo(d["experiencia_paralela_nota"]))
    for e in d["experiencia_paralela"]:
        p.extend(bloque_experiencia(d, e, cifras, marcadores))

    p.append(encabezado(d["habilidades_titulo"]))
    for categoria, valores in d["habilidades"]:
        p.append(parrafo(f"{categoria}: {valores}"))

    p.append(encabezado(d["proyectos_titulo"]))
    for pr in d["proyectos"]:
        p.append(parrafo(pr["nombre"], negrita=True, espacio_antes=120))
        if pr["url"]:
            p.append(parrafo(pr["url"]))
        for punto in pr["puntos"]:
            p.append(vineta(resolver_punto(punto, cifras, marcadores)))
        p.append(parrafo(f'{d["stack_etiqueta"]}: {pr["stack"]}'))

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


def escribir_docx(destino: pathlib.Path, d: dict, marcadores: bool = False) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/document.xml", construir_documento(d, marcadores))


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
    ap.add_argument("--marcadores", action="store_true",
                    help="generar en .borradores/ una copia con [CONFIRMAR: ___] "
                         "donde falta cada métrica; no toca los documentos publicados")
    args = ap.parse_args()

    datos = EN if args.en else ES
    sufijo = "-EN" if args.en else ""
    nombre = f"Jose-Hernan-Varela-Backend-Developer{sufijo}"

    if args.marcadores:
        # A .borradores/ y nunca a src/: Nginx publica todo lo que hay en src/,
        # así que un CV con "[CONFIRMAR: ___]" dentro sería descargable desde el
        # sitio. Un borrador que se filtra hace más daño que la métrica que
        # intenta añadir.
        docx = BORRADORES / f"{nombre}-BORRADOR.docx"
        pendientes = [c for c, v in METRICAS[datos["idioma"]].items() if not v]
        escribir_docx(docx, datos, marcadores=True)
        print(f"  {docx.relative_to(RAIZ)}  ({docx.stat().st_size:,} bytes)")
        pdf = convertir_a_pdf(docx)
        if pdf and pdf.exists():
            print(f"  {pdf.relative_to(RAIZ)}  ({pdf.stat().st_size:,} bytes)")
        if pendientes:
            print(f"\n  {len(pendientes)} métricas por confirmar en METRICAS "
                  "(tools/generar-cv-ats.py):")
            for clave in pendientes:
                print(f"    · {clave}")
            print("  Rellénalas ahí y vuelve a ejecutar sin --marcadores para publicar.")
        else:
            print("\n  No hay métricas pendientes: este borrador es idéntico al publicado.")
        return

    docx = SALIDA / f"{nombre}.docx"

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
