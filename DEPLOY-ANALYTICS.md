# 🚀 Despliegue del Sistema de Analytics

Este documento te guía paso a paso para desplegar el sistema de analytics en tu servidor.

## 📋 Pre-requisitos

- ✅ Contenedor PostgreSQL corriendo (`postgres17`)
- ✅ Traefik configurado en red `server`
- ✅ Docker y Docker Compose instalados
- ✅ Acceso a la base de datos PostgreSQL

## 🔧 Paso 1: Configurar Variables de Entorno

```bash
# Crear archivo .env en la raíz del proyecto
nano .env
```

Agregar el siguiente contenido (ajustar según tu configuración):

```env
DB_HOST=postgres17
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=            # obligatoria
DB_PORT=5432

ANALYTICS_USER=         # obligatoria - acceso al dashboard
ANALYTICS_PASSWORD=     # obligatoria - openssl rand -base64 32
ANALYTICS_IP_SALT=      # obligatoria - openssl rand -hex 32
```

**IMPORTANTE**:
- Las cinco variables sin valor por defecto son **obligatorias**. Si falta
  alguna, el contenedor no arranca (a propósito: es preferible fallar a
  arrancar con credenciales por defecto).
- `ANALYTICS_IP_SALT` se genera **una sola vez**. Si la cambias más adelante,
  se pierde la continuidad del conteo de visitantes únicos.
- Copia la plantilla con `cp .env.example .env` y rellénala.

## 📊 Paso 2: Crear la Tabla en PostgreSQL

Conecta a tu base de datos PostgreSQL y ejecuta el script SQL:

```bash
# Opción 1: Desde el host
cat database/init-analytics.sql | docker exec -i postgres17 psql -U postgres -d postgres

# Opción 2: Manualmente
docker exec -it postgres17 psql -U postgres -d postgres
```

Si usas la opción 2, copia y pega el contenido de `database/init-analytics.sql`

### Verificar que la tabla se creó correctamente:

```bash
docker exec -it postgres17 psql -U postgres -d postgres -c "\dt cv_visits"
```

Deberías ver:

```
          List of relations
 Schema |   Name    | Type  |  Owner
--------+-----------+-------+----------
 public | cv_visits | table | postgres
```

## 🐳 Paso 3: Construir y Levantar el Backend

```bash
# Construir la imagen del backend
docker compose build analytics-api

# Levantar ambos servicios (CV + Analytics)
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f analytics-api
```

## ✅ Paso 4: Verificar que Todo Funciona

### 4.1. Verificar que los contenedores están corriendo:

```bash
docker compose ps
```

Deberías ver:

```
NAME           STATUS
landpage       Up (healthy)
cv-analytics   Up (healthy)
```

### 4.2. Probar el health check del backend:

```bash
curl https://devapis.cloud/health
```

Respuesta esperada:

```json
{"status":"healthy","database":"connected"}
```

### 4.3. Probar el tracking:

```bash
curl -X POST https://devapis.cloud/api/track \
  -H "Content-Type: application/json"
```

Respuesta esperada:

```json
{"status":"tracked","timestamp":"2026-01-13T..."}
```

### 4.4. Ver analytics (requiere autenticación):

```bash
curl -u "$ANALYTICS_USER:$ANALYTICS_PASSWORD" https://devapis.cloud/api/analytics
```

Sin credenciales debe responder `401`:

```bash
curl -o /dev/null -w '%{http_code}\n' https://devapis.cloud/api/analytics   # -> 401
```

### 4.5. Acceder al Dashboard:

Abre en tu navegador (el navegador pedirá usuario y contraseña):

```
https://devapis.cloud/analytics
```

## 🔍 Paso 5: Verificar en el Frontend

1. Abre tu CV: `https://devapis.cloud/cv`
2. Abre la consola del navegador (F12)
3. Deberías ver: `✅ Visit tracked: 2026-01-13T...`
4. Refresca el dashboard: `https://devapis.cloud/analytics`
5. Deberías ver tu visita registrada

## 📊 Queries Útiles

### Ver todas las visitas:

```sql
docker exec -it postgres17 psql -U postgres -d postgres -c "SELECT * FROM cv_visits ORDER BY visited_at DESC LIMIT 10;"
```

### Ver resumen de analytics:

```sql
docker exec -it postgres17 psql -U postgres -d postgres -c "SELECT * FROM cv_analytics_summary;"
```

### Ver top 10 IPs:

```sql
docker exec -it postgres17 psql -U postgres -d postgres -c "
  SELECT ip_address, COUNT(*) as visits, MAX(visited_at) as last_visit
  FROM cv_visits
  GROUP BY ip_address
  ORDER BY visits DESC
  LIMIT 10;
"
```

### Ver estadísticas de navegadores:

```sql
docker exec -it postgres17 psql -U postgres -d postgres -c "
  SELECT browser, COUNT(*) as count
  FROM cv_visits
  GROUP BY browser
  ORDER BY count DESC;
"
```

## 🔧 Troubleshooting

### Problema: Analytics no está conectando a PostgreSQL

**Síntoma**: Error "Database error" en `/health`

**Solución**:

1. Verificar que postgres17 está corriendo:
   ```bash
   docker ps | grep postgres17
   ```

2. Verificar variables de entorno:
   ```bash
   docker exec cv-analytics env | grep DB_
   ```

3. Probar conexión manual:
   ```bash
   docker exec cv-analytics python -c "
   import asyncpg, asyncio
   async def test():
       conn = await asyncpg.connect(
           user='postgres',
           password='tu_password',
           database='postgres',
           host='postgres17'
       )
       print('✅ Connected!')
       await conn.close()
   asyncio.run(test())
   "
   ```

### Problema: Tracker no funciona en el frontend

**Síntoma**: No hay mensaje en consola del navegador

**Solución**:

1. Verificar que el archivo `main.js` tiene el módulo Analytics
2. Limpiar caché del navegador (Ctrl+Shift+R)
3. Verificar CORS en las herramientas de desarrollador
4. Verificar que el endpoint responde:
   ```bash
   curl -X POST https://devapis.cloud/api/track
   ```

### Problema: Dashboard no carga

**Síntoma**: Error 404 o página en blanco

**Solución**:

1. Verificar que el servicio analytics-api está corriendo
2. Verificar logs:
   ```bash
   docker compose logs analytics-api
   ```

3. Verificar routing de Traefik:
   ```bash
   docker logs traefik | grep analytics
   ```

## 📈 Monitoreo Continuo

### Ver logs en tiempo real:

```bash
# Logs del backend
docker compose logs -f analytics-api

# Últimas 50 líneas
docker compose logs --tail 50 analytics-api
```

### Reiniciar servicios:

```bash
# Solo analytics
docker compose restart analytics-api

# Todo el stack
docker compose restart
```

### Ver estadísticas de visitas en tiempo real:

```bash
# Comando que se actualiza cada 5 segundos
watch -n 5 'docker exec -i postgres17 psql -U postgres -d postgres -t -c "SELECT * FROM cv_analytics_summary;"'
```

## 🎯 Próximos Pasos

Una vez que todo esté funcionando, puedes:

1. ✅ Agregar geolocalización de IPs con MaxMind GeoIP2
2. ✅ Crear gráficos con Chart.js en el dashboard
3. ✅ Configurar alertas por email cuando alguien visite
4. ✅ Agregar heatmap de clicks con Hotjar o similar
5. ✅ Implementar política de privacidad (GDPR)
6. ✅ Agregar autenticación al dashboard (opcional)

## 🔐 Seguridad

Estado actual de la protección:

| Endpoint | Acceso |
|---|---|
| `POST /api/track` | Público, con rate limit (10 req/min, ráfaga 20) en Traefik |
| `GET /health` | Público, no revela detalles internos |
| `GET /api/analytics` | 🔒 HTTP Basic (`ANALYTICS_USER` / `ANALYTICS_PASSWORD`) |
| `GET /api/analytics/recent` | 🔒 HTTP Basic |
| `GET /analytics` | 🔒 HTTP Basic |

La autenticación está implementada en `backend/main.py` con `secrets.compare_digest`
(comparación en tiempo constante), **no** en el reverse proxy. Esto es
deliberado: la protección forma parte del código versionado y no se pierde al
recrear los contenedores ni al reconstruir Traefik.

`/docs`, `/redoc` y `/openapi.json` están deshabilitados.

### Endurecimiento adicional (opcional)

1. Restringir el dashboard por IP en Traefik:
   ```yaml
   - "traefik.http.middlewares.analytics-ip.ipallowlist.sourcerange=TU.IP.AQUI/32"
   - "traefik.http.routers.analytics-private.middlewares=analytics-ip@docker"
   ```

2. Usar una base de datos y un rol dedicados en lugar del superusuario
   `postgres`: ver `database/create-analytics-role.sql`.

## 🕵️ Privacidad de los visitantes

Las direcciones IP **no se almacenan**. Por cada visita se guardan:

- `ip_prefix`: la red truncada (`/24` en IPv4, `/48` en IPv6).
- `ip_hash`: SHA-256 de la IP con la sal secreta `ANALYTICS_IP_SALT`.

El valor de `x-forwarded-for` se valida como IP real antes de procesarse, de
modo que una cabecera manipulada no puede inyectar contenido en la base ni en
el dashboard.

### Purgar las IPs históricas

Las instalaciones anteriores a esta versión tienen una columna `ip_address` con
IPs en claro. Al arrancar, el backend rellena `ip_prefix`/`ip_hash` de esas
filas automáticamente (paso **no** destructivo). Para eliminar definitivamente
la columna con los datos personales:

```bash
# Usa los mismos valores que tengas en .env
set -a; . ./.env; set +a

# 1. Copia de seguridad (irreversible a partir de aquí)
docker exec "$DB_HOST" pg_dump -U "$DB_USER" -d "$DB_NAME" -t cv_visits \
  > cv_visits_backup_$(date +%F).sql

# 2. Purga
cat database/migrate-anonymize-ips.sql | \
  docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME"
```

⚠️ Ejecútalo contra la **misma** base que usa el servicio. Si migraste a una
base dedicada, `-d postgres` apuntaría a la base equivocada.

El script aborta si detecta filas todavía sin anonimizar.

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs: `docker compose logs analytics-api`
2. Verifica la conectividad de red: `docker network inspect server`
3. Prueba las queries SQL directamente en PostgreSQL

---

**¡Listo!** Ahora tienes un sistema completo de analytics funcionando 🎉
