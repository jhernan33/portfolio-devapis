# CV Portfolio - José Hernán Varela

[![Production](https://img.shields.io/badge/Live-devapis.cloud%2Fcv-0ea5e9)](https://devapis.cloud/cv)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Nginx](https://img.shields.io/badge/Nginx-1.27-009639?logo=nginx&logoColor=white)](https://nginx.org/)
[![License](https://img.shields.io/badge/License-Private-red)](LICENSE)

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

## 🧪 Testing

### Checklist Manual
- [ ] Theme toggle (light/dark)
- [ ] Smooth scroll navigation
- [ ] Certificate modal (click any cert card)
- [ ] PDF export button (Ctrl+P)
- [ ] Responsive layouts (mobile, tablet, desktop)
- [ ] Keyboard navigation
- [ ] Screen reader compatibility

### Navegadores Soportados
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

## 📝 Mejoras y Recomendaciones

### 🔥 Mejoras Críticas (Alta Prioridad)

1. **Analytics y Monitoreo**
   - [ ] Agregar Google Analytics 4 o similar
   - [ ] Implementar monitoring con Sentry para errores JS
   - [ ] Agregar métricas de performance (Web Vitals)

2. **SEO Optimization**
   - [ ] Agregar `sitemap.xml`
   - [ ] Agregar `robots.txt`
   - [ ] Mejorar meta tags Open Graph
   - [ ] Agregar schema.org markup (Person, ProfilePage)
   - [ ] Implementar breadcrumbs estructurados

3. **Performance**
   - [ ] Convertir imágenes PNG a WebP (reducción ~70%)
   - [ ] Implementar lazy loading en imágenes
   - [ ] Agregar preload hints para CSS crítico
   - [ ] Considerar minificación de CSS/JS (opcional)

4. **Accesibilidad**
   - [ ] Agregar skip navigation links más robustos
   - [ ] Mejorar contraste de colores en dark mode
   - [ ] Agregar lang attributes en textos en inglés

### 💡 Mejoras Recomendadas (Media Prioridad)

5. **Funcionalidad**
   - [ ] Agregar botón "Scroll to top"
   - [ ] Implementar navegación móvil hamburger menu
   - [ ] Agregar animaciones de entrada (Intersection Observer)
   - [ ] Crear versión en inglés (i18n)

6. **Contenido**
   - [ ] Agregar sección de testimonios/referencias
   - [ ] Expandir proyectos con enlaces a demos/GitHub
   - [ ] Agregar blog o artículos técnicos
   - [ ] Incluir enlaces a StackOverflow/GitHub profile

7. **DevOps**
   - [ ] Implementar CI/CD con GitHub Actions
   - [ ] Agregar tests automatizados (Playwright/Cypress)
   - [ ] Configurar renovación automática de certificados
   - [ ] Implementar staging environment

8. **Backup y Versionado**
   - [ ] Configurar backups automáticos de imágenes
   - [ ] Implementar git tags para releases
   - [ ] Documentar proceso de rollback

### 🚀 Mejoras Futuras (Baja Prioridad)

9. **Progressive Enhancement**
   - [ ] Convertir a PWA (Service Worker, manifest.json)
   - [ ] Agregar soporte offline
   - [ ] Implementar notificaciones push (nuevo artículo/proyecto)

10. **Interactividad**
    - [ ] Agregar formulario de contacto (con backend)
    - [ ] Implementar sistema de comentarios
    - [ ] Agregar contador de visitas

11. **Integrations**
    - [ ] Conectar con LinkedIn API para sincronizar experiencia
    - [ ] Integrar con GitHub API para mostrar repos
    - [ ] Agregar feed RSS para actualizaciones

### 🔧 Mejoras Técnicas Específicas

#### Código Sugerido para WebP Conversion
```bash
# Convertir todas las imágenes PNG a WebP
cd src/assets/images/
for img in *.png; do
  cwebp -q 85 "$img" -o "${img%.png}.webp"
done
```

#### Código para Analytics (Google Analytics 4)
```html
<!-- Agregar antes de </head> en index.html -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

#### Schema.org Markup Sugerido
```html
<!-- Agregar en <head> -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "José Hernán Varela",
  "jobTitle": "Senior Backend Developer",
  "url": "https://devapis.cloud/cv",
  "email": "jhernan33@gmail.com",
  "address": {
    "@type": "PostalAddress",
    "addressRegion": "Táchira",
    "addressCountry": "VE"
  },
  "knowsAbout": ["Python", "Django", "FastAPI", "PostgreSQL", "Docker"],
  "alumniOf": "IUFRONT"
}
</script>
```

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
- Email: jhernan33@gmail.com
- LinkedIn: [jhernan-13465028](https://www.linkedin.com/in/jhernan-13465028)
- Ubicación: Táchira, Venezuela

---

**Última actualización**: 2026-01-13
