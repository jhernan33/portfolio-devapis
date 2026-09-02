# CV Portfolio - José Hernán Varela

[![CI](https://github.com/jhernan33/portfolio-devapis/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jhernan33/portfolio-devapis/actions/workflows/ci.yml)
[![Production](https://img.shields.io/badge/Live-devapis.cloud%2Fcv-0ea5e9)](https://devapis.cloud/cv)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Nginx](https://img.shields.io/badge/Nginx-1.27-009639?logo=nginx&logoColor=white)](https://nginx.org/)
[![License](https://img.shields.io/badge/License-All%20rights%20reserved-red)](LICENSE)

Landing page profesional de CV/Portfolio para Senior Backend Developer. Sitio estático de una sola página con zero-dependencies, optimizado para rendimiento y accesibilidad.

## 🌐 Demo en Vivo

**URL:** [https://devapis.cloud/cv](https://devapis.cloud/cv)

## ✨ Características

### Frontend
- **Zero Dependencies**: Vanilla JavaScript puro (ES6+), sin npm ni build tools
- **Responsive Design**: Mobile-first con 4 breakpoints (380px, 640px, 768px, 1024px)
- **Dark Mode**: Tema claro/oscuro con detección de preferencias del sistema
- **Accesibilidad**: WCAG 2.1 AA compliant con ARIA labels y navegación por teclado
- **PDF Export**: Funcionalidad de impresión optimizada con forzado de tema claro
- **Smooth Scroll**: Navegación fluida con Intersection Observer
- **Certificate Gallery**: Modal lightbox para visualización de certificados

### Performance
- **Tamaño Total**: ~76 KB (HTML + CSS + JS)
- **Cache Strategy**: Assets inmutables (1 año), HTML sin cache
- **Gzip Compression**: Habilitada en Nginx
- **Lazy Loading**: Imágenes de certificados cargadas bajo demanda
- **No Build Required**: Deploy directo de archivos fuente

### Infraestructura
- **Containerizado**: Docker + Docker Compose
- **Reverse Proxy**: Traefik con TLS automático
- **Web Server**: Nginx 1.27 Alpine (minimal)
- **Security Headers**: CSP, HSTS, X-Frame-Options, etc.
- **Health Checks**: Monitoreo integrado de contenedor

### 📊 Analytics
- **Backend Propio**: FastAPI para tracking de visitas
- **Base de Datos**: PostgreSQL para almacenamiento
- **Dashboard en Tiempo Real**: Visualización de estadísticas
- **Datos Capturados**: IP, navegador, OS, dispositivo, referer, idioma
- **Sin Bloqueos**: No bloqueado por ad-blockers
- **100% Privado**: Control total de tus datos

## 🛠 Stack Tecnológico

| Categoría | Tecnologías |
|-----------|-------------|
| **Frontend** | HTML5, CSS3 (BEM), Vanilla JavaScript ES6+ |
| **Styling** | CSS Custom Properties, CSS Grid, Flexbox |
| **Server** | Nginx 1.27 Alpine |
| **Analytics Backend** | FastAPI + asyncpg + uvicorn |
| **Database** | PostgreSQL 17 |
| **Container** | Docker, Docker Compose |
| **Proxy** | Traefik (TLS, routing, strip prefix) |
| **Deployment** | devapis.cloud con path-based routing |

## 📁 Estructura del Proyecto

```
landPage/
├── src/                          # Source files (served directly)
│   ├── index.html               # Main HTML page (ES)
│   ├── styles.css               # Complete styling (~1450 lines)
│   ├── main.js                  # Vanilla JS modules (~300 lines)
│   └── assets/
│       └── images/              # Certificate images (17 files)
│   ├── theme-init.js            # Aplica el tema antes del primer pintado
│   └── 404.html                 # Página de error propia
├── backend/                      # API de analytics (FastAPI + asyncpg)
│   ├── main.py                  # Punto de entrada: app = create_app()
│   ├── app/                     # config, security, privacy, db, migrations,
│   │                            # models, repositories, routes, static
│   ├── migrations/              # Esquema versionado, aplicado al arrancar
│   ├── mantenimiento.py         # Andamiaje común de los scripts de datos
│   └── tests/                   # pytest, sin necesidad de PostgreSQL
├── tools/                        # Generadores y utilidades
│   ├── generar-version-en.py    # src/en/index.html desde src/index.html
│   ├── generar-cv-ats.py        # Los CV descargables (.docx y .pdf)
│   ├── generar-og.py            # Las imágenes de previsualización
│   ├── verificar-produccion.sh  # Las comprobaciones del despliegue y el monitor
│   ├── respaldar-db.sh          # Respaldo con verificación y rotación
│   └── e2e/                     # Tests de navegador (Playwright)
├── Dockerfile                    # Imagen del CV (nginx-unprivileged)
├── docker-compose.yaml           # Producción, tras Traefik
├── docker-compose.dev.yaml       # Stack local completo, con su PostgreSQL
├── nginx.conf                    # Configuración de Nginx
├── nginx-security-headers.conf   # Cabeceras, incluidas en cada location
├── CLAUDE.md                     # Guía para el asistente
└── README.md                     # Este fichero
```

## 🚀 Instalación y Uso

### Prerrequisitos
- Docker 20.10+
- Docker Compose 2.0+
- Red Docker externa `server` (para Traefik)

### Desarrollo Local

#### Opción 1: Servidor estático simple
```bash
# Python
cd src/
python -m http.server 8000

# Node.js
npx serve src/

# Acceder en http://localhost:8000
```

#### Opción 2: Docker local
```bash
# Build y ejecutar
docker build -t landpage .
docker run -p 8080:8080 landpage

# Acceder en http://localhost:8080
```

### Despliegue a Producción

#### 1. Crear red externa (solo primera vez)
```bash
docker network create server
```

#### 2. Desplegar con Docker Compose
```bash
# Iniciar contenedor
docker compose up -d

# Ver logs
docker compose logs -f

# Reiniciar
docker compose restart

# Detener y eliminar
docker compose down
```

#### 3. Verificar Health Check
```bash
docker ps
# Debe mostrar "healthy" en STATUS
```

## 🏗 Arquitectura

### Flujo de Deployment

```
┌──────────────┐
│  Browser     │
│  (HTTPS)     │
└──────┬───────┘
       │
┌──────▼───────────────────────┐
│  Traefik Reverse Proxy       │
│  - TLS Termination           │
│  - Host: devapis.cloud       │
│  - PathPrefix: /cv           │
│  - Strip Prefix Middleware   │
└──────┬───────────────────────┘
       │ (HTTP interno)
┌──────▼───────────────────────┐
│  Nginx Container (port 8080) │
│  - SPA Routing               │
│  - Security Headers          │
│  - Gzip Compression          │
│  - Cache Control             │
└──────┬───────────────────────┘
       │
┌──────▼───────────────────────┐
│  Static Files                │
│  /usr/share/nginx/html       │
│  (volume read-only)          │
└──────────────────────────────┘
```

### Módulos JavaScript

```javascript
ThemeManager      // Dark/Light mode toggle + localStorage
SmoothScroll      // Smooth anchor navigation
NavHighlight      // Active nav link via Intersection Observer
Accessibility     // Skip links, ARIA live regions
CertModal         // Certificate lightbox modal
PDFExport         // Print/PDF generation (forced light theme)
PrintHandler      // Keyboard shortcuts (Ctrl+P)
```

### CSS Architecture

- **Metodología**: BEM (Block Element Modifier)
- **Theming**: CSS Custom Properties con `[data-theme="dark"]`
- **Layout**: CSS Grid (hero, certifications) + Flexbox (nav, timeline)
- **Mobile-First**: Base styles para móvil, media queries para desktop

## 📊 Performance Metrics

Lo que descarga un visitante al abrir el CV: HTML, CSS y JavaScript. Las
imágenes de los diplomas no cuentan, porque solo se piden al abrir el modal.

| Métrica | Valor |
|---------|-------|
| HTML + CSS + JS de una versión | ~97 KB sin minificar |
| Presupuesto vigilado por la CI | < 200 KB |
| Imágenes (14 diplomas en WebP) | 522 KB, bajo demanda |
| Dependencias del frontend | ninguna |

El presupuesto lo comprueba la CI en cada push, así que la cifra no envejece.

## 🔒 Seguridad

### Headers Implementados

Del CV (`nginx-security-headers.conf`, incluido en el `server` **y en cada
`location`**: Nginx no acumula `add_header` entre niveles, y por eso durante
meses ninguna respuesta llevó ninguna de estas cabeceras):

- `Content-Security-Policy: default-src 'self'; script-src 'self'…`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

`X-XSS-Protection` se retiró a propósito: los navegadores actuales la ignoran y
en los que la implementaron el filtro llegó a introducir vulnerabilidades
propias.

Del backend (`backend/app/middleware.py`), que contesta directo por Traefik:
`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, una CSP de
`default-src 'none'` para las respuestas JSON y `Cache-Control: no-store` en
todo lo que devuelve datos de visitas.

### Medidas Adicionales
- Volúmenes read-only en Docker
- Directorio `.git` bloqueado por Nginx
- Archivos ocultos (`.env`, `.htaccess`) bloqueados
- Server tokens deshabilitados

### Backend de analytics
- Autenticación HTTP Basic a nivel de aplicación en los endpoints de estadísticas,
  con comparación en tiempo constante
- IPs de visitantes anonimizadas: red truncada (/24 IPv4, /48 IPv6) + hash SHA-256
  con sal. Ninguna IP se almacena en claro
- Secretos obligatorios sin valor por defecto: el servicio no arranca si falta alguno
- Rate limiting en el endpoint público de tracking
- Consultas parametrizadas; documentación interactiva deshabilitada

📄 **[Decisiones técnicas](docs/DECISIONES-TECNICAS.md)** — el razonamiento detrás
de estas decisiones, la auditoría de seguridad que las motivó y cómo se verificaron.

## 🧪 Testing

### Tests del backend

```bash
cd backend
make test     # crea .venv, instala las dependencias y ejecuta pytest
make lint     # ruff check + ruff format --check, lo mismo que la CI
```

**No hace falta PostgreSQL.** El pool se sustituye por un doble en memoria y
`ASGITransport` entra al enrutado sin ejecutar el arranque, así que cada test
inyecta la configuración que necesita. Es deliberado: una suite que exige
levantar un contenedor termina por no ejecutarse, y una suite que no se ejecuta
no protege nada.

Qué cubren, por orden de importancia:

| Área | Qué se comprueba |
|---|---|
| Anonimización | La IP completa no aparece en ningún valor que llegue a la base; una `X-Forwarded-For` falseada con basura o SQL no se propaga; cambiar la sal rompe la continuidad (por eso no se rota) |
| Tráfico propio | Rangos privados, la IP pública del propio servidor vía `ANALYTICS_IGNORE_NETWORKS`, y "ante la duda, interno" |
| Autenticación | Toda ruta de estadísticas responde 401 sin credenciales y 503 si no hay credenciales configuradas; el `realm` distingue si contestó la aplicación o el panel de Traefik |
| Arranque | Falta un secreto obligatorio → el servicio se niega a arrancar, nombrando cuál |
| User-Agent | El orden de las comprobaciones (ver abajo) y qué es un rastreador |
| Migraciones | Se aplican en orden, no se repiten, y una que falla no queda anotada como hecha |
| Calidad de los datos | Una recarga no cuenta como visita nueva; dos navegadores en la misma IP son dos personas; la página que manda el navegador nunca se guarda en crudo |
| Cabeceras | Toda respuesta del backend las lleva, incluido un 401; el panel conserva su propia CSP |

**Estos tests encontraron tres fallos reales el día que se escribieron.** Cada
cadena de User-Agent contiene varias pistas a la vez y gana la primera que se
mira: Opera y Edge se anuncian además como `Chrome/`, Android declara `Linux` e
iPhone/iPad declaran `like Mac OS X`. Con el orden anterior, **ninguna visita
desde Android o iOS se registró jamás como tal** — se contaban como Linux y
macOS— mientras el tipo de dispositivo, que se deduce aparte, sí decía `Mobile`.
Un panel que se contradice a sí mismo sin que salte ningún error es justo lo que
un test unitario detecta y una revisión a ojo no.

### Comprobaciones automáticas

Cada push a `main` ejecuta [el workflow de CI](.github/workflows/ci.yml).
Sus guardas no son buenas prácticas de catálogo: **cada una corresponde a un
fallo que este repositorio ya tuvo.**

| Guarda | El fallo que evita |
|---|---|
| Ningún `-old.*` en `src/` | Tres copias antiguas estuvieron descargables en `/cv/index-old.html` |
| `.env` no versionado | Lleva la contraseña de la base y la sal de las IPs |
| Sin datos de contacto directo | El teléfono se retiró del repositorio a propósito |
| Sin `<script>` inline | La CSP los bloquea; el fallo solo se ve en producción. La guarda combinaba `grep -E` y `-P`, que es un error de grep: llevaba desde el principio sin comprobar nada |
| Rutas de analytics con `Depends(require_analytics_auth)` | El dashboard estuvo protegido solo por el proxy |
| `ip_address` ni se crea ni se escribe | Las IPs no vuelven a almacenarse en claro |
| El directorio de migraciones entra en la imagen | Sin él, el contenedor arranca contra una base sin tabla y solo falla en la primera visita |
| Las migraciones aplicadas no se reescriben | Editar una deja las bases que ya la aplicaron con un esquema distinto del que dicen tener |
| Todo router bajo `/api` declara rate limit | HTTP Basic sin límite de intentos es fuerza bruta gratis |
| Ningún `print` en el backend | Sin nivel ni marca de tiempo, el motivo del bucle de reinicio de meses estaba en uno de ellos |
| Ninguna acción con etiqueta móvil | `@v4` ejecuta lo que haya ese día en un runner con acceso al repositorio |
| Contenedores sin root y con `read_only` | `/api/track` acepta escrituras públicas |
| Nginx envía sus cabeceras en todas las respuestas | `add_header` no se hereda en un `location`: no llegaba ninguna |
| Una ruta inexistente devuelve 404 | Devolvía 200 con el CV entero: un *soft 404* para los buscadores |
| Sin texto sin traducir en la versión inglesa | Encontró cuatro cadenas en español que llevaban publicadas meses |
| Prioridades de Traefik por encima de 73 | Por debajo, el tracking cae en el panel de Traefik y devuelve 401 |
| El compose falla si falta un secreto | Un `DB_HOST` por defecto dejó el servicio meses reiniciándose |
| Versión en inglés y documentos ATS al día | Se generan desde `src/index.html`; si no, divergen en silencio |
| Certificaciones con código y URL `https` | Un enlace de verificación roto es peor que ninguno |
| Presupuesto de peso de la página | Estaba documentado pero nada lo medía |
| `pytest` del backend y Playwright en el frontend | Los invariantes de arriba, ejecutándose de verdad y en un navegador de verdad |
| `ruff` | El estilo deja de discutirse en cada revisión |

### Despliegue

[`deploy.yml`](.github/workflows/deploy.yml) se dispara **solo si la CI terminó
en verde sobre `main`**, actualiza el servidor por SSH y después verifica desde
fuera, con `tools/verificar-produccion.sh`, las cosas que este proyecto ya vio
romperse. `update-production.sh` etiqueta las imágenes anteriores antes de
reconstruir, espera a que los contenedores estén sanos de verdad en lugar de
dormir diez segundos, y **vuelve a la versión anterior si la verificación
falla**: un despliegue fallido deja el sitio en pie.

[`monitor.yml`](.github/workflows/monitor.yml) repite esas comprobaciones cada
media hora y abre un issue si algo falla, porque entre despliegues no había nada
que avisara: el frontend se traga los errores de tracking por diseño, así que un
backend caído no se nota desde fuera.

Lo que verifica: que `/health` responda,
que `POST /api/track` siga siendo público (un 401 ahí significa que el router ha
vuelto a caer en el panel de Traefik) y que `/api/analytics` siga pidiendo
credenciales *de la aplicación* y no del proxy.

Mientras no existan los secretos del servidor, el job se salta y explica cuáles
faltan, en lugar de fallar: un pipeline en rojo permanente se acaba ignorando.

### Tests de extremo a extremo del frontend

```bash
cd tools/e2e
npm ci && npx playwright install chromium
npx playwright test
```

Playwright vive en `tools/e2e/` para que `src/` siga sin dependencias. Corren en
escritorio y en móvil, y sirven `src/` bajo `/cv/` porque el HTML lleva
`<base href="/cv/">`: servido en la raíz, todos los recursos darían 404 y los
tests medirían una página sin estilos ni JavaScript.

Cubren el checklist que antes se hacía a ojo: el tema persiste entre recargas,
el modal de certificados atrapa el foco y lo devuelve a la tarjeta, las
certificaciones colapsadas se despliegan, la navegación marca la sección activa
(abriendo antes el menú en móvil), el tracking manda la ruta correcta, y los
textos que genera el JavaScript salen en inglés en la versión inglesa.

### Verificación de producción

```bash
./tools/verificar-produccion.sh
```

Las mismas cinco comprobaciones que ejecuta el despliegue y que repite el
monitor cada media hora: que el CV responda con sus cabeceras, que una ruta
inexistente dé 404, que el backend alcance la base, que el tracking siga siendo
público y que las estadísticas sigan pidiendo credenciales.

### Navegadores Soportados
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

## 📊 Sistema de Analytics

El CV incluye un sistema completo de analytics propio con backend FastAPI y PostgreSQL.

### Características del Analytics

- **Privacidad por diseño**: las IPs **nunca** se almacenan en claro. Se guardan
  la red truncada (/24 en IPv4, /48 en IPv6) y dos hashes con sal: uno de la IP
  y otro de IP + User-Agent, que permite contar visitantes únicos sin poder
  reidentificarlos.
- **Qué se guarda**: red de origen truncada, navegador, sistema operativo, tipo
  de dispositivo, referente, idioma, versión del CV visitada y la fecha en UTC.
- **Qué NO cuenta como visita**, aunque se guarde y se pueda ver marcado:
  - **tráfico propio** — rangos privados y la IP pública del servidor;
  - **rastreadores** — buscadores, redes sociales, auditorías, `curl`;
  - **recargas** — el mismo visitante otra vez en menos de media hora.

  En la primera medición con tráfico real, el 70% de las "visitas" era tráfico
  propio. Sin esto, la única métrica con la que el CV se mide es ruido.
- **Retención**: `backend/depurar_visitas.py` retira el User-Agent y el
  referente de las visitas de más de 24 meses. Se conservan navegador, sistema
  y hashes, que es lo que alimenta las estadísticas.

### Endpoints Disponibles

| Endpoint | Método | Autenticación |
|---|---|---|
| `/health` | GET | Pública — 200 si atiende, 503 si no. No dice qué componente falla |
| `/api/track` | POST | Pública (rate limit en Traefik: 10/min) |
| `/api/analytics` | GET | 🔒 HTTP Basic (rate limit: 15/min) |
| `/api/analytics/recent?limit=20` | GET | 🔒 HTTP Basic |
| `/api/analytics/health` | GET | 🔒 HTTP Basic — diagnóstico detallado |
| `/analytics` | GET | 🔒 HTTP Basic — panel |

```bash
# Públicos
curl https://devapis.cloud/health
curl -X POST https://devapis.cloud/api/track

# Autenticados (credenciales en ANALYTICS_USER / ANALYTICS_PASSWORD)
curl -u "$ANALYTICS_USER:$ANALYTICS_PASSWORD" https://devapis.cloud/api/analytics
```

La autenticación se implementa en la aplicación (`backend/app/security.py`), no en el
reverse proxy: así la protección viaja con el repositorio y no se pierde al
recrear los contenedores.

### Dashboard de Analytics

El dashboard muestra en tiempo real:
- **Visitas totales**, **visitantes únicos**, **últimos 7 días** y **hoy**
  (dónde empieza "hoy" lo decide `ANALYTICS_DISPLAY_TZ`, no el reloj del
  contenedor de PostgreSQL)
- **Top navegadores**, **dispositivos** y **redes de origen** truncadas
- **Versión del CV** leída: español o inglés
- **Últimas 10 visitas**, incluyendo las que no cuentan y por qué: interna,
  rastreador o recarga. Sin esa tabla no habría forma de distinguir "no llega
  nada" de "llega y se está descartando"

**Acceso**: [https://devapis.cloud/analytics](https://devapis.cloud/analytics) — requiere usuario y contraseña.

### Despliegue del Analytics

Ver documentación completa en [DEPLOY-ANALYTICS.md](DEPLOY-ANALYTICS.md)

**Quick Start**:

```bash
# 1. Configurar variables de entorno
cp .env.example .env
nano .env  # Editar con credenciales reales

# 2. Ejecutar script de despliegue automatizado
./deploy-analytics.sh   # el esquema lo crean las migraciones al arrancar

# 3. Verificar que funciona
./tools/verificar-produccion.sh
```

Para probarlo entero sin tocar producción, `docker-compose.dev.yaml` levanta
PostgreSQL, el CV y la API en local (ver más arriba).

### Queries Útiles

```bash
# $DB_HOST es el nombre del contenedor de PostgreSQL, y no es adivinable:
#   docker ps --format '{{.Names}}' | grep -i postgres

# Últimas visitas, con el motivo por el que alguna no cuenta
docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT visited_at, ip_prefix, browser, os, page, is_internal, is_bot, is_repeat
   FROM cv_visits ORDER BY visited_at DESC LIMIT 10;"

# Resumen (ya excluye tráfico propio, rastreadores y recargas)
docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT * FROM cv_analytics_summary;"

# Redes de origen. NO hay columna de IP: se guarda el prefijo truncado
docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT ip_prefix, COUNT(*) AS visitas FROM cv_visits
   WHERE NOT is_internal AND NOT is_bot
   GROUP BY ip_prefix ORDER BY visitas DESC LIMIT 10;"

# Qué migraciones se han aplicado
docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "SELECT * FROM schema_migrations ORDER BY version;"
```

### Arquitectura del Analytics

```
Frontend (JavaScript) ──POST /api/track──> FastAPI Backend
                                               │
                                               ├──> PostgreSQL
                                               │    (cv_visits table)
                                               │
Dashboard (HTML) ────GET /api/analytics───────┘
```

### Privacidad

**El sistema no registra IPs.** Guarda la red truncada y hashes con sal, así que
no hay dato personal que borrar ni con el que reidentificar a nadie: el derecho
al olvido está resuelto por construcción y no por procedimiento.

- El aviso está en el pie del sitio, en las dos versiones de idioma.
- `ANALYTICS_IP_SALT` se genera una vez y no se rota: cambiarla rompe la
  continuidad del conteo de visitantes únicos.
- La retención (`backend/depurar_visitas.py`) retira a los 24 meses el
  User-Agent y el referente, que son los campos con más entropía.
- El respaldo (`tools/respaldar-db.sh`) se guarda cifrado en reposo solo si el
  disco del servidor lo está; tenlo en cuenta al elegir dónde se copia.

## 📄 Licencia

Este proyecto es privado y de uso personal.

## 👤 Autor

**José Hernán Varela**
- Portafolio: [devapis.cloud/cv](https://devapis.cloud/cv)
- GitHub: [@jhernan33](https://github.com/jhernan33)
- LinkedIn: [jhernanvarela](https://www.linkedin.com/in/jhernanvarela)
- Email: jhernan33@gmail.com
- Ubicación: Táchira, Venezuela

---

**Última actualización**: 2026-08-31
