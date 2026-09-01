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
import sys

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
    (">Experiencia<", ">Experience<"),
    (">Proyectos<", ">Projects<"),
    (">Educación<", ">Education<"),
    ('aria-label="Navegación principal"', 'aria-label="Main navigation"'),
    ('aria-label="Exportar a PDF"', 'aria-label="Export to PDF"'),
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
    ("15 años en TI. Entre 2019 y 2023 compaginé el puesto de tiempo completo con trabajo freelance, consultoría y contrato.",
     "15 years in IT. Between 2019 and 2023 I combined my full-time role with freelance, consulting and contract work."),
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


def main() -> None:
    salida = generar(ORIGEN.read_text(encoding="utf-8"))
    if "--check" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != salida:
            sys.exit("src/en/index.html está desactualizado. "
                     "Ejecuta: python3 tools/generar-version-en.py")
        print("src/en/index.html está al día")
        return
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(salida, encoding="utf-8")
    print(f"Generado {DESTINO.relative_to(RAIZ)} · {len(salida.splitlines())} líneas")


if __name__ == "__main__":
    main()
