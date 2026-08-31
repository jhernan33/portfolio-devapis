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
docker run -p 8080:80 landpage

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
│  Nginx Container (port 80)   │
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
| DDL sincronizado entre `main.py` y el SQL | El esquema vive en dos sitios |
| Prioridades de Traefik por encima de 73 | Por debajo, el tracking cae en el panel de Traefik y devuelve 401 |
| El compose falla si falta un secreto | Un `DB_HOST` por defecto dejó el servicio meses reiniciándose |
| Versión en inglés y documentos ATS al día | Se generan desde `src/index.html`; si no, divergen en silencio |
| Certificaciones con código y URL `https` | Un enlace de verificación roto es peor que ninguno |
| Presupuesto de peso de la página | Estaba documentado pero nada lo medía |

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

La autenticación se implementa en la aplicación (`backend/main.py`), no en el
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
- LinkedIn: [jhernan-13465028](https://www.linkedin.com/in/jhernan-13465028)
- Email: jhernan33@gmail.com
- Ubicación: Táchira, Venezuela

---

**Última actualización**: 2026-08-31
