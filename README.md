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

### 📊 Analytics (NUEVO)
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
├── backend/                      # Analytics API (FastAPI + asyncpg)
│   ├── main.py                  # Entrypoint: app = create_app()
│   ├── app/                     # Package: config, security, privacy, db, repositories, routes, static
│   └── tests/                   # pytest, no PostgreSQL needed
├── Dockerfile                    # Container definition
├── docker-compose.yaml           # Docker Compose orchestration
├── nginx.conf                    # Nginx configuration
├── CLAUDE.md                     # AI assistant guidance
└── README.md                     # This file
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

| Métrica | Valor |
|---------|-------|
| HTML Size | ~11 KB |
| CSS Size | ~55 KB |
| JS Size | ~10 KB |
| Total Load | ~76 KB |
| First Paint | < 500ms |
| Interactive | < 1s |
| Lighthouse Score | 95+ |

## 🔒 Seguridad

### Headers Implementados
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'...`
- `Referrer-Policy: strict-origin-when-cross-origin`

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
pip install -r requirements-dev.txt
python -m pytest
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
| User-Agent | El orden de las comprobaciones (ver abajo) |

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
| Sin `<script>` inline | La CSP los bloquea; el fallo solo se ve en producción |
| Rutas de analytics con `Depends(require_analytics_auth)` | El dashboard estuvo protegido solo por el proxy |
| `ip_address` ni se crea ni se escribe | Las IPs no vuelven a almacenarse en claro |
| DDL sincronizado entre `backend/app/db.py` y el SQL | El esquema vive en dos sitios |
| Prioridades de Traefik por encima de 73 | Por debajo, el tracking cae en el panel de Traefik y devuelve 401 |
| El compose falla si falta un secreto | Un `DB_HOST` por defecto dejó el servicio meses reiniciándose |
| Versión en inglés y documentos ATS al día | Se generan desde `src/index.html`; si no, divergen en silencio |
| Certificaciones con código y URL `https` | Un enlace de verificación roto es peor que ninguno |
| Presupuesto de peso de la página | Estaba documentado pero nada lo medía |
| `pytest` del backend | Los invariantes de arriba, ejecutándose de verdad |

### Despliegue

[`deploy.yml`](.github/workflows/deploy.yml) se dispara **solo si la CI terminó
en verde sobre `main`**, actualiza el servidor por SSH y después verifica desde
fuera las tres cosas que este proyecto ya vio romperse: que `/health` responda,
que `POST /api/track` siga siendo público (un 401 ahí significa que el router ha
vuelto a caer en el panel de Traefik) y que `/api/analytics` siga pidiendo
credenciales *de la aplicación* y no del proxy.

Mientras no existan los secretos del servidor, el job se salta y explica cuáles
faltan, en lugar de fallar: un pipeline en rojo permanente se acaba ignorando.

### Verificación manual

Sigue sin haber tests de extremo a extremo del frontend
([#11](https://github.com/jhernan33/portfolio-devapis/issues/11)). Antes de
cada despliegue se comprueba a mano:

- Conmutador de tema (claro/oscuro) y persistencia en `localStorage`
- Navegación con scroll suave y resaltado de sección activa
- Modal de certificados
- Exportación a PDF (Ctrl+P), que fuerza el tema claro
- Diseño responsive en móvil, tablet y escritorio
- Navegación completa por teclado
- Compatibilidad con lector de pantalla

El backend se verifica con los endpoints descritos en `DEPLOY-ANALYTICS.md`.

### Navegadores Soportados
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

## 📊 Sistema de Analytics

El CV incluye un sistema completo de analytics propio con backend FastAPI y PostgreSQL.

### Características del Analytics

- **Tracking Automático**: Registra visitas automáticamente sin intervención
- **Privacidad por diseño**: las IPs **nunca** se almacenan en claro. Se guardan
  la red truncada (/24 en IPv4, /48 en IPv6) y un hash SHA-256 con sal, que
  permite contar visitantes únicos sin poder reidentificarlos.
- **Datos Capturados**:
  - Red de origen truncada (derivada de x-forwarded-for de Traefik)
  - Navegador y versión
  - Sistema operativo
  - Tipo de dispositivo (Mobile/Desktop)
  - Referrer (de dónde viene)
  - Idioma preferido
  - Timestamp UTC

### Endpoints Disponibles

| Endpoint | Método | Autenticación |
|---|---|---|
| `/health` | GET | Pública |
| `/api/track` | POST | Pública (con rate limit en Traefik) |
| `/api/analytics` | GET | 🔒 HTTP Basic |
| `/api/analytics/recent?limit=20` | GET | 🔒 HTTP Basic |
| `/analytics` | GET | 🔒 HTTP Basic |

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
- **Visitas totales**
- **Visitantes únicos** (por hash de IP con sal)
- **Visitas últimos 7 días**
- **Visitas hoy**
- **Top navegadores**
- **Redes de origen** truncadas, con última visita
- **Estadísticas de dispositivos** (Mobile vs Desktop)
- **Sistemas operativos**
- **Últimas 10 visitas** con detalles completos

**Acceso**: [https://devapis.cloud/analytics](https://devapis.cloud/analytics) — requiere usuario y contraseña.

### Despliegue del Analytics

Ver documentación completa en [DEPLOY-ANALYTICS.md](DEPLOY-ANALYTICS.md)

**Quick Start**:

```bash
# 1. Configurar variables de entorno
cp .env.example .env
nano .env  # Editar con credenciales reales

# 2. Ejecutar script de despliegue automatizado
./deploy-analytics.sh

# 3. Verificar que funciona
curl https://devapis.cloud/health
curl https://devapis.cloud/api/analytics
```

### Queries Útiles

```bash
# Ver todas las visitas
docker exec -it postgres17 psql -U postgres -d postgres \
  -c "SELECT * FROM cv_visits ORDER BY visited_at DESC LIMIT 10;"

# Ver resumen
docker exec -it postgres17 psql -U postgres -d postgres \
  -c "SELECT * FROM cv_analytics_summary;"

# Top 10 IPs
docker exec -it postgres17 psql -U postgres -d postgres \
  -c "SELECT ip_address, COUNT(*) as visits FROM cv_visits GROUP BY ip_address ORDER BY visits DESC LIMIT 10;"
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

### Privacidad y GDPR

El sistema registra IPs para fines estadísticos. Se recomienda:
1. Agregar política de privacidad en el footer
2. Informar al usuario sobre el tracking
3. Ofrecer opción de opt-out
4. Implementar derecho al olvido (eliminar datos bajo petición)

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
