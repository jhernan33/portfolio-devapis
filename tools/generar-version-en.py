#!/usr/bin/env python3
"""
Genera src/en/index.html a partir de src/index.html.

Por qué un generador y no un fichero escrito a mano: dos copias del CV se
desincronizan a la primera edición, y la que se queda vieja es siempre la que
no lees a diario. Aquí la estructura es idéntica por construcción y lo único
que se mantiene es el diccionario de abajo.

No es un paso de compilación: el sitio se sigue sirviendo estático y sin
dependencias. Esto se ejecuta a mano cuando cambia el CV, y la salida se
versiona.

    python3 tools/generar-version-en.py

El CI comprueba que la salida esté al día (job `frontend`).

Las traducciones NO son literales. Los cargos y titulaciones van a su
equivalente anglosajón: "Jefe de Informática" es "IT Manager", no "Chief of
Informatics"; "TSU" es un "Associate Degree".
"""
import pathlib
import re
import sys
from html.parser import HTMLParser

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "src" / "index.html"
DESTINO = RAIZ / "src" / "en" / "index.html"

# Ordenado de más largo a más corto: "Experiencia Profesional" tiene que
# traducirse antes que "Experiencia", o quedaría "Experience Profesional".
TRADUCCIONES = [
    # --- cabecera y metadatos ---
    ("Senior Backend Developer. 15 años en TI, 5 construyendo APIs con Python (Django y FastAPI), PostgreSQL y Docker. Remoto para LATAM y Europa.",
     "Senior Backend Developer. 15 years in IT, 5 building APIs with Python (Django and FastAPI), PostgreSQL and Docker. Available for remote work across LATAM and Europe."),
    ("15 años en TI, 5 construyendo APIs con Python (Django y FastAPI), PostgreSQL y Docker. Remoto para LATAM y Europa.",
     "15 years in IT, 5 building APIs with Python (Django and FastAPI), PostgreSQL and Docker. Available for remote work across LATAM and Europe."),
    # --- navegación ---
    ("Saltar al contenido", "Skip to content"),
    # El único periodo abierto del CV. Estaba sin traducir y no se ve a simple
    # vista: la fecha parece una fecha en cualquier idioma hasta que uno lee
    # "Presente" en una página en inglés. Lo destapó la comprobación de abajo.
    (">2011 - Presente<", ">2011 - Present<"),
    (">08/2025 - Presente<", ">08/2025 - Present<"),
    ('aria-label="Cerrar"', 'aria-label="Close"'),
    (">Experiencia<", ">Experience<"),
    (">Proyectos<", ">Projects<"),
    (">Educación<", ">Education<"),
    ('aria-label="Navegación principal"', 'aria-label="Main navigation"'),
    # Botón de descarga del CV en formato ATS: cada idioma tiene su documento,
    # así que se sustituye el elemento entero y no solo el aria-label. La ruta
    # va absoluta porque la página inglesa no lleva <base> y "documentos/..."
    # se resolvería contra /cv/en/.
    ('''<a class="nav__btn nav__btn--pdf" id="descargar-cv"
				   href="documentos/Jose-Hernan-Varela-Backend-Developer.pdf" download
				   title="Descargar CV en PDF (formato ATS)"
				   aria-label="Descargar el CV en PDF, en formato legible por sistemas de selección">''',
     '''<a class="nav__btn nav__btn--pdf" id="descargar-cv"
				   href="/cv/documentos/Jose-Hernan-Varela-Backend-Developer-EN.pdf" download
				   title="Download CV as PDF (ATS-friendly)"
				   aria-label="Download the CV as a PDF, in a format applicant tracking systems can read">'''),
    ('aria-label="Cambiar tema"', 'aria-label="Toggle theme"'),
    ('aria-label="Abrir menú de navegación"', 'aria-label="Open navigation menu"'),
    # conmutador de idioma: en la versión inglesa apunta de vuelta al español
    ('<a href="/cv/en/" class="nav__btn nav__btn--lang" hreflang="en" lang="en" aria-label="Read this CV in English">EN</a>',
     '<a href="/cv" class="nav__btn nav__btn--lang" hreflang="es" lang="es" aria-label="Leer este CV en español">ES</a>'),
    # --- hero ---
    ("Disponible para trabajo remoto", "Open to remote work"),
    ("<strong>15 años en TI, 5 construyendo APIs.</strong>",
     "<strong>15 years in IT, 5 building APIs.</strong>"),
    ("Especializado en <strong>Python (Django y FastAPI)</strong>, PostgreSQL\n\t\t\t\t\ty arquitecturas containerizadas. Remoto para LATAM y Europa.",
     "Specialised in <strong>Python (Django and FastAPI)</strong>, PostgreSQL\n\t\t\t\t\tand containerised architectures. Available for remote work across LATAM and Europe."),
    ("Información de contacto", "Contact details"),
    # --- experiencia ---
    ("Experiencia Profesional", "Professional Experience"),
    ("15 años en TI. Desde 2019 compagino el puesto de tiempo completo con trabajo freelance, consultoría, contrato y, desde 2025, un producto propio en producción.",
     "15 years in IT. Since 2019 I have combined my full-time role with freelance, consulting and contract work and, since 2025, a product of my own in production."),
    ("Jefe de Informática", "IT Manager"),
    ("Lidero el departamento de TI y la infraestructura tecnológica completa",
     "I lead the IT department and the full technology infrastructure"),
    ("Desarrollo de sistemas internos con Python y Django que automatizan procesos antes manuales",
     "Internal systems in Python and Django that automate previously manual processes"),
    ("Administro la infraestructura Linux que sostiene la operación en producción",
     "I administer the Linux infrastructure that keeps production running"),
    ("Despliegues contenerizados y reproducibles con Docker, en sustitución del despliegue manual",
     "Containerised, reproducible deployments with Docker, replacing the manual process"),
    ("Desarrollador Backend", "Backend Developer"),
    ("Freelance · en paralelo a PCVARELAVENEZUELA", "Freelance · alongside PCVARELAVENEZUELA"),
    ("Consultoría · en paralelo a PCVARELAVENEZUELA", "Consulting · alongside PCVARELAVENEZUELA"),
    ("Contrato · en paralelo a PCVARELAVENEZUELA", "Contract · alongside PCVARELAVENEZUELA"),
    ("Plataforma MLS inmobiliaria", "Real estate MLS platform"),
    ("Producto propio en producción · en paralelo a PCVARELAVENEZUELA",
     "Own product in production · alongside PCVARELAVENEZUELA"),
    ("API REST multi-inquilino en Node.js 22, Express 5 y PostgreSQL con Prisma: 353 endpoints en 57 routers sobre 53 modelos de datos",
     "Multi-tenant REST API on Node.js 22, Express 5 and PostgreSQL with Prisma: 353 endpoints across 57 routers over 53 data models"),
    ("Autorización con RBAC y alcance por empresa y agente derivado del JWT; las fugas entre inquilinos se cerraron como clase y las fijan 18 tests de seguridad",
     "RBAC authorisation with company- and agent-level scope derived from the JWT; cross-tenant leaks were closed as a class and are pinned by 18 security tests"),
    ("Dos pasarelas de pago en paralelo (Stripe y PayU) con webhooks, suscripciones recurrentes e idempotencia por cabecera",
     "Two payment gateways in parallel (Stripe and PayU) with webhooks, recurring subscriptions and header-based idempotency"),
    ("Caché Redis con ETag e invalidación dirigida desde cada escritura, y rate limiting en tres capas: Traefik, techo global y por ruta",
     "Redis cache with ETag and targeted invalidation on every write, plus three-layer rate limiting: Traefik, a global ceiling and per route"),
    ("Suite de 2.154 tests con Jest y Supertest, incluidos tests guardrail que fallan si reaparece un patrón ya eliminado; imagen Docker distroless sin root",
     "Suite of 2,154 tests with Jest and Supertest, including guardrail tests that fail if an eliminated pattern reappears; distroless, non-root Docker image"),
    ("Prototipo de la API REST de un sistema de trazabilidad de muestras geológicas mineras",
     "Prototype of the REST API for a mining geological sample traceability system"),
    ("Modelado del ciclo de vida del testigo de sondaje, desde que sale del terreno hasta su almacenamiento y análisis en laboratorio",
     "Modelled the life cycle of a drill core sample, from the field to storage and laboratory analysis"),
    ("Despliegue en un VPS de Contabo con Docker y Traefik",
     "Deployment on a Contabo VPS with Docker and Traefik"),
    ("APIs REST con Django y Django REST Framework para un sistema de gestión empresarial",
     "REST APIs with Django and Django REST Framework for a business management system"),
    ("Integración de servicios sobre esa API", "Service integration on top of that API"),
    ("Optimización de consultas PostgreSQL en las rutas de mayor uso",
     "PostgreSQL query optimisation on the most heavily used endpoints"),
    ("Arquitectura de microservicios en PHP con Laravel y Lumen",
     "Microservice architecture in PHP with Laravel and Lumen"),
    ("Integración con APIs de terceros y comunicación en tiempo real con WebSockets",
     "Third-party API integration and real-time communication over WebSockets"),
    ("Automatización de despliegues mediante CI/CD", "Deployment automation through CI/CD"),
    ("Seguridad con JWT y control de acceso granular", "JWT security and fine-grained access control"),
    ("Alcaldía del Municipio Guásimos", "Guásimos Municipality · Local Government"),
    ("Plataforma de gestión municipal para trámites ciudadanos",
     "Municipal platform for citizen administrative procedures"),
    ("Sistemas de información geográfica con PostGIS", "Geographic information systems with PostGIS"),
    ("Administración de los servidores que dan servicio a la plataforma",
     "Administration of the servers running the platform"),
    ("Integración con sistemas gubernamentales existentes",
     "Integration with existing government systems"),
    # --- stack ---
    ("Stack Tecnológico", "Tech Stack"),
    ("Herramientas y tecnologías de dominio", "Tools and technologies I work with"),
    ('<h3 class="stack-card__title">Lenguajes</h3>', '<h3 class="stack-card__title">Languages</h3>'),
    ("Bases de Datos", "Databases"),
    ("<li>Microservicios</li>", "<li>Microservices</li>"),
    (">Microservicios<", ">Microservices<"),
    ('"Microservicios"', '"Microservices"'),

    # --- proyectos ---
    ("Proyectos Destacados", "Selected Projects"),
    ("Soluciones de impacto real", "Work with real-world impact"),
    ("Sistema de Gestión Municipal", "Municipal Management System"),
    ("API REST para la tramitación de solicitudes ciudadanas",
     "REST API handling citizen service requests"),
    ("Información geográfica con PostGIS sobre los datos del municipio",
     "Geographic data for the municipality with PostGIS"),
    ("Dashboard administrativo con Vue.js", "Administrative dashboard built with Vue.js"),
    ("Migración de sistema legacy", "Legacy System Migration"),
    ("Migración de un monolito a una arquitectura de microservicios",
     "Migration from a monolith to a microservice architecture"),
    ("Automatización de los despliegues mediante CI/CD", "Deployment automation through CI/CD"),
    ("Este portafolio y su backend de analytics", "This Portfolio and Its Analytics Backend"),
    ("Sitio estático sin dependencias servido por Nginx, con analítica propia en FastAPI",
     "Zero-dependency static site served by Nginx, with self-hosted analytics in FastAPI"),
    ("Las IPs no se almacenan: se guardan la red truncada y un hash con sal",
     "IP addresses are never stored: only the truncated network and a salted hash"),
    ("Autenticación en la aplicación, no en el proxy, para que viaje con el código",
     "Authentication lives in the application, not the proxy, so it ships with the code"),
    ("Tests con pytest y despliegue automático: cada push verifica que ninguna IP se guarde en claro y que las estadísticas sigan protegidas",
     "pytest suite and automated deployment: every push verifies that no IP is stored in clear text and that the stats endpoints stay protected"),
    ("Código y decisiones técnicas en GitHub", "Source code and technical decisions on GitHub"),
    # --- educación y certificaciones ---
    ("TSU en Informática", "Associate Degree in Computer Science"),
    ("Desarrollador e-Business", "e-Business Developer"),
    ("Certificaciones", "Certifications"),
    # --- certificaciones ---
    ("21 certificaciones · más de 229 h de formación continua (2023–2026), todas de Platzi",
     "21 certifications · over 229 hours of continuous learning (2023–2026), all from Platzi"),
    # aria-label de las tarjetas que enlazan a la verificación: se traducen las
    # dos partes fijas y el nombre del curso lo cubren las reglas de abajo.
    ('aria-label="Certificado de ', 'aria-label="Certificate: '),
    (": verificar en Platzi, se abre en una pestaña nueva\"",
     " — verify on Platzi, opens in a new tab\""),
    # Nombres largos primero: "Ciberseguridad Preventiva" antes que
    # "Ciberseguridad", o quedaría "Cybersecurity Preventiva".
    ("Administración de Servidores Linux", "Linux Server Administration"),
    ("Ciberseguridad Preventiva", "Preventive Cybersecurity"),
    ("Taller de Ciberseguridad", "Cybersecurity Workshop"),
    ("Fundamentos de Python", "Python Fundamentals"),
    ("Fundamentos de Web3", "Web3 Fundamentals"),
    ("Servidores Linux", "Linux Servers"),
    ("Taller Ciberseguridad", "Cybersecurity Workshop"),
    ("Ciberseguridad", "Cybersecurity"),
    ("JavaScript Fundamentos", "JavaScript Fundamentals"),
    ("Intro IA", "Intro to AI"),
    ('<span class="cert-card__category">Seguridad</span>',
     '<span class="cert-card__category">Security</span>'),
    ('<span class="cert-card__category">Base de Datos</span>',
     '<span class="cert-card__category">Database</span>'),
    ('<span class="cert-card__category">Lenguaje</span>',
     '<span class="cert-card__category">Language</span>'),
    ('<span class="cert-card__category">IA</span>', '<span class="cert-card__category">AI</span>'),
    ("Platzi · ene ", "Platzi · Jan "),
    # jul faltaba: los otros once meses estaban y este no, así que la
    # certificación de julio de 2026 se publicaba con el mes en español. Lo
    # destapó la comprobación de texto sin traducir; a ojo no se ve.
    ("Platzi · jul ", "Platzi · Jul "),
    ("Platzi · mar ", "Platzi · Mar "),
    ("Platzi · abr ", "Platzi · Apr "),
    ("Platzi · may ", "Platzi · May "),
    ("Platzi · ago ", "Platzi · Aug "),
    ("Platzi · sep ", "Platzi · Sep "),
    ("Platzi · oct ", "Platzi · Oct "),
    ("Platzi · nov ", "Platzi · Nov "),
    ("Platzi · dic ", "Platzi · Dec "),
    # --- idiomas: redacción canónica en inglés (PERFIL-CANONICO §3) ---
    ('<h3 class="section__title section__title--sub">Idiomas</h3>',
     '<h3 class="section__title section__title--sub">Languages</h3>'),
    ('<span class="lang-item__name">Español</span>', '<span class="lang-item__name">Spanish</span>'),
    ('<span class="lang-item__level">Nativo</span>', '<span class="lang-item__level">Native</span>'),
    ('<span class="lang-item__name" lang="en">Inglés</span>', '<span class="lang-item__name">English</span>'),
    ('<span class="lang-item__level">Lectura y escritura técnica fluidas (B2)</span>',
     '<span class="lang-item__level">Fluent technical reading and writing (B2)</span>'),
    ('Conversacional en desarrollo (A2–B1). Cómodo trabajando con documentación,\n\t\t\t\t<span lang="en">code reviews</span> y comunicación asíncrona en inglés.',
     "Spoken English improving (A2–B1). Comfortable with English documentation,\n\t\t\t\tcode reviews and asynchronous written communication."),
    # --- disponibilidad y pie ---
    ('<h2 id="avail-title" class="sr-only">Disponibilidad</h2>',
     '<h2 id="avail-title" class="sr-only">Availability</h2>'),
    ("Disponible para nuevos proyectos", "Available for new projects"),
    # Descargas: rutas absolutas porque la página inglesa no lleva <base>, así
    # que "documentos/..." se resolvería contra /cv/en/ y daría un 404.
    ('''<p class="cta-box__downloads">
						Descargar CV:
						<a href="documentos/Jose-Hernan-Varela-Backend-Developer.pdf" download>PDF</a>
						<a href="documentos/Jose-Hernan-Varela-Backend-Developer.docx" download>DOCX</a>
					</p>''',
     '''<p class="cta-box__downloads">
						Download CV:
						<a href="/cv/documentos/Jose-Hernan-Varela-Backend-Developer-EN.pdf" download>PDF</a>
						<a href="/cv/documentos/Jose-Hernan-Varela-Backend-Developer-EN.docx" download>DOCX</a>
					</p>'''),
    ("Full-time · Part-time · Freelance · Consultoría", "Full-time · Part-time · Freelance · Consulting"),
    ("Zona horaria: UTC-4 (flexible) · Inicio inmediato", "Time zone: UTC−4 (flexible) · Immediate start"),
    (">Contactar<", ">Get in touch<"),
    ("Transformando ideas en soluciones backend robustas y escalables",
     "Turning ideas into robust, scalable backend systems"),
    ("Este sitio registra las visitas de forma anónima y sin cookies: no se\n\t\t\talmacenan direcciones IP, solo la red truncada y un hash con sal.",
     "This site records visits anonymously and without cookies: no IP addresses\n\t\t\tare stored, only the truncated network and a salted hash."),
]


# Identificadores de sección, que acaban visibles en la barra de direcciones
# al navegar (/cv/en/#experience). "stack" es igual en los dos idiomas.
# main.js no los conoce: recorre section[id] y los href de .nav__link, así que
# traducirlos no rompe la navegación ni el resaltado de sección activa.
IDS_SECCION = [
    ("experiencia", "experience"),
    ("proyectos", "projects"),
    ("educacion", "education"),
]


def generar(html: str) -> str:
    faltantes = []
    for es, en in TRADUCCIONES:
        if es not in html and es != en:
            faltantes.append(es)
        html = html.replace(es, en)

    html = html.replace('<html lang="es">', '<html lang="en">', 1)

    for es, en in IDS_SECCION:
        html = html.replace(f'id="{es}"', f'id="{en}"')
        html = html.replace(f'href="#{es}"', f'href="#{en}"')

    # Sin <base>. En /cv/en/ un <base href="/cv/"> heredado haría que los
    # enlaces de ancla (#experience) se resolvieran contra /cv/ y sacaran al
    # visitante de la página. Con rutas absolutas /cv/... no hace falta.
    html = html.replace('\t<base href="/cv/">\n', "")
    html = html.replace('href="styles.css"', 'href="/cv/styles.css"')
    html = html.replace('src="main.js"', 'src="/cv/main.js"')
    html = html.replace('src="theme-init.js"', 'src="/cv/theme-init.js"')
    html = html.replace('data-cert="assets/images/', 'data-cert="/cv/assets/images/')

    # Los hreflang ya están en el original y son recíprocos, así que se copian
    # tal cual. Aquí solo cambia la canónica, que sí es propia de cada idioma.
    html = html.replace('<link rel="canonical" href="https://devapis.cloud/cv">',
                        '<link rel="canonical" href="https://devapis.cloud/cv/en/">')
    html = html.replace('<meta property="og:url" content="https://devapis.cloud/cv">',
                        '<meta property="og:url" content="https://devapis.cloud/cv/en/">')
    html = html.replace('<meta property="og:locale" content="es_VE">',
                        '<meta property="og:locale" content="en">\n'
                        '\t<meta property="og:locale:alternate" content="es_VE">')

    # La tarjeta de previsualización lleva texto dentro de la imagen, así que
    # cada idioma tiene la suya. Se sustituyen aquí y no en TRADUCCIONES
    # porque son URL y atributos, no texto visible de la página.
    html = html.replace("assets/images/og-cover.png", "assets/images/og-cover-en.png")
    # Con `replace` a secas, cambiar una cifra en index.html dejaba este texto
    # sin traducir y la página inglesa se publicaba con el alt en español, sin
    # que nada lo dijera. Pasó al corregir los años de experiencia. Ahora se
    # comprueba que la frase de origen exista antes de sustituirla.
    alt_es = ('content="José Hernán Varela, Senior Backend Developer. 15 años en TI, '
              '5 construyendo APIs. Python, Django, FastAPI, PostgreSQL y Docker."')
    alt_en = ('content="José Hernán Varela, Senior Backend Developer. 15 years in IT, '
              '5 building APIs. Python, Django, FastAPI, PostgreSQL and Docker."')
    if alt_es not in html:
        sys.exit("El texto alternativo de la portada Open Graph cambió en "
                 "src/index.html y ya no coincide con el de este script.\n"
                 f"  Se esperaba: {alt_es}\n"
                 "  Actualiza `alt_es` y `alt_en` en tools/generar-version-en.py.")
    html = html.replace(alt_es, alt_en)
    html = html.replace('"url": "https://devapis.cloud/cv"', '"url": "https://devapis.cloud/cv/en/"')
    html = html.replace('"name": "Español", "alternateName": "es"',
                        '"name": "Spanish", "alternateName": "es"')
    html = html.replace('"name": "Inglés", "alternateName": "en"',
                        '"name": "English", "alternateName": "en"')

    html = ("<!-- GENERADO por tools/generar-version-en.py a partir de src/index.html.\n"
            "     No editar a mano: los cambios se pierden en la siguiente ejecución.\n"
            "     Edita src/index.html y vuelve a ejecutar el script. -->\n") + html

    if faltantes:
        print("Cadenas del diccionario que ya no existen en src/index.html:", file=sys.stderr)
        for f in faltantes:
            print("  ·", f[:70], file=sys.stderr)
        print("Actualiza TRADUCCIONES o revisa el original.", file=sys.stderr)
        sys.exit(1)
    return html


# ---------------------------------------------------------------------------
# Comprobación de texto sin traducir
# ---------------------------------------------------------------------------
#
# Comparar que la salida coincida con el generador solo detecta que alguien
# editó src/en/index.html a mano. No detecta lo que de verdad pasa: que se
# añada un párrafo en español, no esté en el diccionario y viaje intacto a la
# versión inglesa. Eso no falla, no se ve, y la única persona que abre esa
# página a diario es la que menos lo va a notar.
#
# Aquí se extrae el texto visible de las dos versiones y se marca todo lo que
# aparezca idéntico en ambas. La mayoría de esas coincidencias son legítimas
# —nombres propios, tecnologías, fechas— así que hace falta decir cuáles.

# Palabras que se escriben igual en los dos idiomas: nombres propios,
# tecnologías, siglas y valores técnicos. Una cadena se considera invariante si
# TODAS sus palabras están aquí. Así "Django / Django REST Framework" pasa sin
# tener que enumerar cada combinación, y "Microservicios" no.
VOCABULARIO_INVARIANTE = {
    # persona, lugares y organizaciones
    "josé", "hernán", "varela", "táchira", "venezuela", "delzam", "iufront",
    "iutai", "platzi", "zippyttech", "tecnología", "innovación", "github",
    "linkedin", "pcvarelavenezuela", "jv", "gsamples", "global", "chile",
    "prisma", "stripe", "mls", "node",
    # cargo y secciones que ya están en inglés en el original
    "senior", "backend", "developer", "stack", "frameworks", "devops",
    "terminal", "prompt", "engineering", "ai", "tools", "code", "claude",
    "windsurf", "blockchain",
    # tecnologías
    "python", "django", "rest", "framework", "fastapi", "postgresql",
    "postgis", "mysql", "sql", "server", "pl", "pgsql", "redis", "docker",
    "compose", "traefik", "nginx", "linux", "ubuntu", "debian", "fedora",
    "php", "laravel", "lumen", "javascript", "es6", "express", "js", "vue",
    "web3", "websockets", "jwt", "auth", "apis", "api", "git", "shell",
    "scripting", "cv", "pdf", "docx", "json", "es", "web", "jhernan",
    # meses ya traducidos y valores de metadatos
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
    "nov", "dec", "es_ve", "en_us", "image", "png", "profile",
    "summary_large_image", "width", "device", "initial", "scale",
    "jhernan33", "gmail", "com", "http", "https",
}

# Cadenas completas que se escriben igual en los dos idiomas y que no se pueden
# descomponer en palabras del vocabulario. Van enteras y contadas.
CADENAS_INVARIANTES = {
    "Zippyttech Tecnología e Innovación",   # razón social
}

# Valores que no son prosa: colores, correos, dominios, locales, tipos MIME e
# identificadores. Ninguno se traduce nunca, y enumerarlos uno a uno en el
# vocabulario solo lo ensuciaría.
PATRONES_TECNICOS = (
    re.compile(r"^#[0-9a-fA-F]{3,8}$"),                     # color
    re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$"),              # correo
    re.compile(r"^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$"),  # dominio o URL
    re.compile(r"^[a-z]{2}_[A-Z]{2}$"),                     # locale
    re.compile(r"^[\w-]+/[\w.+-]+$"),                       # tipo MIME
    re.compile(r"^[a-z0-9]*_[a-z0-9_]+$"),                  # identificador
)

ATRIBUTOS_CON_TEXTO = ("alt", "aria-label", "title", "content", "placeholder")


class _TextoVisible(HTMLParser):
    """Saca el texto que lee una persona: nodos de texto y atributos con copy."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.textos: list[str] = []
        self._dentro_de_codigo = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._dentro_de_codigo += 1
        for nombre, valor in attrs:
            if nombre in ATRIBUTOS_CON_TEXTO and valor and valor.strip():
                self.textos.append(valor.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._dentro_de_codigo:
            self._dentro_de_codigo -= 1

    def handle_data(self, datos):
        if self._dentro_de_codigo:
            return
        limpio = " ".join(datos.split())
        if limpio:
            self.textos.append(limpio)


def _texto_visible(html: str) -> set:
    parser = _TextoVisible()
    parser.feed(html)
    return set(parser.textos)


def _es_invariante(texto: str) -> bool:
    """
    ¿Es normal que esta cadena sea idéntica en los dos idiomas?

    Lo es si no contiene ninguna palabra —solo cifras, fechas o símbolos— o si
    todas sus palabras están en el vocabulario. Es una lista de excepciones
    explícita y no una heurística: cuando falle, el mensaje dice exactamente
    qué palabra no reconoce, y la decisión de añadirla o traducir es de quien
    edita el CV.
    """
    if texto in CADENAS_INVARIANTES:
        return True
    if any(patron.match(texto) for patron in PATRONES_TECNICOS):
        return True
    palabras = re.findall(r"[^\W\d_]+", texto.lower(), re.UNICODE)
    return all(p in VOCABULARIO_INVARIANTE for p in palabras)


def comprobar_traduccion(html_en: str) -> list:
    """Devuelve las cadenas que siguen en español en la versión inglesa."""
    comunes = _texto_visible(ORIGEN.read_text(encoding="utf-8")) & _texto_visible(html_en)
    return sorted(t for t in comunes if not _es_invariante(t))


def main() -> None:
    salida = generar(ORIGEN.read_text(encoding="utf-8"))
    if "--check" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != salida:
            sys.exit("src/en/index.html está desactualizado. "
                     "Ejecuta: python3 tools/generar-version-en.py")

        sin_traducir = comprobar_traduccion(salida)
        if sin_traducir:
            print("Texto idéntico en las dos versiones y no reconocido como invariante:")
            for texto in sin_traducir:
                print(f"  · {texto[:120]}")
            sys.exit(
                "Añade la traducción a TRADUCCIONES, o la palabra a "
                "VOCABULARIO_INVARIANTE si de verdad se escribe igual."
            )

        print("src/en/index.html está al día y sin texto sin traducir")
        return
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(salida, encoding="utf-8")
    print(f"Generado {DESTINO.relative_to(RAIZ)} · {len(salida.splitlines())} líneas")


if __name__ == "__main__":
    main()
