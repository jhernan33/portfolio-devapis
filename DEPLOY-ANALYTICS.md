# 🚀 Despliegue del Sistema de Analytics

Este documento te guía paso a paso para desplegar el sistema de analytics en tu servidor.

## 📋 Pre-requisitos

- ✅ Docker y Docker Compose instalados
- ✅ Traefik configurado en la red `server`
- ✅ Un contenedor PostgreSQL en marcha

Sobre ese último punto, tres comprobaciones que parecen obvias y no lo son.
Las tres fallaron en el primer despliegue real y cada una cuesta una tarde:

**1. El nombre exacto del contenedor.** `DB_HOST` no es un hostname de red: es
el nombre del contenedor. Míralo, no lo recuerdes:

```bash
docker ps --format '{{.Names}}' | grep -i postgres
```

Un despliegue anterior dio por hecho `postgres17` cuando el contenedor se
llamaba `postgres17_qa-db-1`, y el servicio pasó meses reiniciándose con
`gaierror: Temporary failure in name resolution`.

**2. Red compartida con `analytics-api`.** Que el nombre sea correcto no basta:
si no comparten red, tampoco resuelve.

```bash
docker inspect <contenedor-postgres> \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
```

Si la red no es `server` ni `db-internal`, añádela a la clave `networks` del
servicio `analytics-api` en `docker-compose.yaml` **y** ajusta
`traefik.docker.network` (ver el paso 3).

**3. `pg_hba.conf` tiene que admitir al rol.** Un PostgreSQL endurecido puede
exigir TLS y llevar lista blanca de roles. Comprueba qué acepta de verdad:

```bash
docker exec <contenedor-postgres> psql -U postgres -tAc \
  "SELECT line_number, type, database, user_name, address, auth_method
     FROM pg_hba_file_rules ORDER BY line_number;"
```

Ojo con dos trampas aquí. `psql` por `docker exec` entra por el socket Unix
local, que suele ser `trust`, así que **funcionar por ahí no demuestra nada**
sobre el acceso por red. Y si tienes que editar `pg_hba.conf` montado por bind
sobre un fichero suelto, Docker lo ata por inodo: `sed -i` y
`awk > tmp && mv` crean un inodo nuevo y el contenedor sigue leyendo el viejo
sin decir nada. Hay que reiniciar el contenedor para que rehaga el montaje.

## 🔧 Paso 1: Configurar Variables de Entorno

```bash
# Crear archivo .env en la raíz del proyecto
nano .env
```

Agregar el siguiente contenido (ajustar según tu configuración):

```env
DB_HOST=                # obligatoria - NOMBRE DEL CONTENEDOR, verifícalo con docker ps
DB_NAME=                # obligatoria
DB_USER=                # obligatoria - rol dedicado, no el superusuario
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
cat database/init-analytics.sql | docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME"

# Opción 2: Manualmente
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME"
```

Si usas la opción 2, copia y pega el contenido de `database/init-analytics.sql`

### Verificar que la tabla se creó correctamente:

```bash
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "\dt cv_visits"
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
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT * FROM cv_visits ORDER BY visited_at DESC LIMIT 10;"
```

### Ver resumen de analytics:

```sql
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT * FROM cv_analytics_summary;"
```

### Ver top 10 redes (las IPs no se almacenan):

```sql
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "
  SELECT ip_prefix, COUNT(*) as visits, MAX(visited_at) as last_visit
  FROM cv_visits
  GROUP BY ip_prefix
  ORDER BY visits DESC
  LIMIT 10;
"
```

### Ver estadísticas de navegadores:

```sql
docker exec -it "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c "
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

1. Verificar que el contenedor de `DB_HOST` está corriendo:
   ```bash
   docker ps --format '{{.Names}}' | grep -i postgres
   ```

2. Verificar variables de entorno:
   ```bash
   docker exec cv-analytics env | grep DB_
   ```

3. Probar la conexión **desde dentro del contenedor de analytics**, que es el
   único camino que importa. Hacerlo con `docker exec` contra PostgreSQL usa
   el socket local y no prueba lo mismo:
   ```bash
   docker exec cv-analytics python -c "
   import asyncpg, asyncio, os
   async def test():
       conn = await asyncpg.connect(
           user=os.environ['DB_USER'],
           password=os.environ['DB_PASSWORD'],
           database=os.environ['DB_NAME'],
           host=os.environ['DB_HOST'],
       )
       print('✅ Conectado')
       await conn.close()
   asyncio.run(test())
   "
   ```

### Problema: `gaierror: Temporary failure in name resolution`

`DB_HOST` nombra un contenedor que no existe, o que no comparte red con
`analytics-api`. Las tres comprobaciones de los pre-requisitos cubren ambos casos.

### Problema: `pg_hba.conf rejects connection ... no encryption`

El servidor exige TLS o no tiene al rol en su lista blanca. asyncpg intenta
primero con TLS y, si lo rechazan, reintenta sin cifrar; el mensaje que ves es
el del **segundo** intento, así que "no encryption" despista: puede que el
problema real fuese la falta de una regla `hostssl` para ese rol. Mira
`pg_hba_file_rules` antes de tocar nada.

### Problema: las peticiones expiran, sin 502 ni entrada en el log de Traefik

`curl` devuelve `000` y `/cv` sí funciona. Casi siempre significa que
`analytics-api` está en más de una red y Traefik eligió una IP que no alcanza.
Se arregla con la etiqueta `traefik.docker.network=server`. Para confirmarlo,
prueba cada IP desde el propio Traefik:

```bash
for ip in $(docker inspect cv-analytics \
    --format '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}} {{end}}'); do
  echo -n "$ip -> "
  docker exec traefik wget -q -O- --timeout=3 "http://$ip:8000/health" || echo INALCANZABLE
done
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
watch -n 5 'docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT * FROM cv_analytics_summary;"'
```

## 🎯 Próximos Pasos

Una vez que todo esté funcionando:

1. Publicar el aviso de privacidad en el sitio — es lo único de la sección de
   privacidad que sigue abierto.
2. Gráficos en el dashboard con una librería servida desde el propio dominio
   (la CSP restringe los scripts a `'self'`).
3. Geolocalización a nivel de país. Tendría que salir de `ip_prefix`, la red
   ya truncada: reintroducir la IP completa para geolocalizar anularía la
   decisión de no almacenarla.

Descartado a propósito: heatmaps de terceros tipo Hotjar y cualquier servicio
externo de analítica. Contradicen el motivo por el que existe este backend,
explicado en `docs/DECISIONES-TECNICAS.md`.
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

Las instalaciones anteriores a esta versión guardaban la IP completa en una
columna `ip_address`. Hay que eliminarla. El procedimiento depende de si
seguiste en la misma base o migraste a una dedicada.

Haz **siempre** la copia de seguridad primero: los dos caminos son irreversibles.

```bash
set -a; . ./.env; set +a   # DB_HOST, DB_NAME, DB_USER
```

#### Caso A — Base nueva y dedicada (empezar de cero)

Si migraste a `cv_analytics`, esa base arranca vacía y el histórico se queda
en la tabla `cv_visits` de la base antigua. Como no se conserva nada, basta
con eliminar la tabla vieja entera:

```bash
# 1. Copia de seguridad de la tabla antigua
docker exec "$DB_HOST" pg_dump -U postgres -d postgres -t cv_visits \
  > cv_visits_legacy_$(date +%F).sql

# 2. Eliminar la tabla con las IPs en claro (y su vista dependiente)
docker exec -i "$DB_HOST" psql -U postgres -d postgres \
  -c "DROP TABLE cv_visits CASCADE;"
```

`CASCADE` elimina también la vista `cv_analytics_summary` de la base antigua.
No hace falta ejecutar `migrate-anonymize-ips.sql`: la base nueva ya nace sin
la columna `ip_address`.

Se pierden los contadores históricos. Si quieres conservarlos como referencia,
el dump del paso 1 los mantiene.

#### Caso B — Misma base de siempre

El backend rellena `ip_prefix`/`ip_hash` de las filas antiguas al arrancar
(paso **no** destructivo). Después, para eliminar la columna:

```bash
# 1. Copia de seguridad
docker exec "$DB_HOST" pg_dump -U "$DB_USER" -d "$DB_NAME" -t cv_visits \
  > cv_visits_backup_$(date +%F).sql

# 2. Purga
cat database/migrate-anonymize-ips.sql | \
  docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME"
```

El script aborta si detecta filas todavía sin anonimizar. Ejecútalo contra la
**misma** base que usa el servicio.

## ⏮️ Volver atrás (rollback)

Hasta ahora, volver a una versión anterior significaba buscar un SHA a mano
mientras algo estaba roto. Cada versión desplegada lleva ahora una etiqueta:

```bash
git tag -n9              # qué es cada versión
git tag --contains HEAD  # ¿está publicado lo que tengo delante?
```

**Numeración.** El primer número sube cuando cambia algo que no se puede
deshacer solo con `git checkout` —el esquema de la base, un secreto
obligatorio nuevo, el formato de un dato almacenado—; el segundo, cuando se
añade funcionalidad; el tercero, para correcciones. Dicho de otro modo: **si
para volver atrás hace falta leer esta sección, es un cambio de versión
mayor.**

### Etiquetar una versión nueva

Esto solo sirve si se hace **cada vez**. Una etiqueta suelta no da a dónde
volver; lo que sirve es la anterior:

```bash
git tag -a v2.1.0 -m "qué cambia y qué hay que saber para volver atrás"
git push origin v2.1.0
```

Escribe el mensaje pensando en quien lo lea con algo caído. Si el cambio toca
la base de datos o `.env`, dilo ahí: es lo primero que se mira.

### Antes de nada: ¿qué está roto?

El rollback del frontend y el del backend son operaciones distintas y con
riesgos muy distintos. No los mezcles.

| Síntoma | Qué revertir | Riesgo |
|---|---|---|
| La página se ve mal, un enlace roto, un texto equivocado | solo `cv` | ninguno |
| Cabeceras, caché, redirecciones, CSP | `cv` **con reconstrucción** | ninguno |
| `/api/track` o `/analytics` fallan | solo `analytics-api` | lee lo de abajo |
| El contenedor no arranca | mira primero `docker compose logs`; casi siempre es `.env`, no el código | — |

### Frontend (`cv`) — segundos, sin riesgo

`src/` está montado como volumen de solo lectura, así que el contenido se
cambia con un `git checkout` y no hace falta tocar el contenedor:

```bash
cd ~/cv
git checkout v2.0.0 -- src/      # solo el sitio
curl -sI https://devapis.cloud/cv | head -1
```

Si lo que falla viene de `nginx.conf` —caché, cabeceras, redirecciones— eso
sí está dentro de la imagen y hay que reconstruir:

```bash
git checkout v2.0.0 -- nginx.conf
docker compose build cv
docker compose up -d --force-recreate cv
```

**`--force-recreate` no es opcional.** Compose 2.3.3 decide si recrear un
contenedor comparando su configuración, y el identificador de la imagen no
entra en esa comparación. Sin la bandera, `up -d` responde `Container landpage
Running` y deja corriendo la imagen vieja: parece que has desplegado y no has
desplegado nada.

Para deshacer el rollback, **el orden importa y no es el evidente**:

```bash
cd ~/cv
git reset -- src/ nginx.conf          # 1. sacarlos del índice
git checkout main -- src/ nginx.conf  # 2. contenido de main
git clean -fd src/                    # 3. borrar lo que main ya no tiene
git status --short                    # debe salir vacío
```

`git checkout main -- src/` **no basta**. Devuelve a su estado los ficheros que
existen en `main`, pero no borra los que trajo la versión antigua y `main` ya no
tiene. Volviendo a antes de la conversión a WebP, por ejemplo, deja los 14 PNG
en `src/` — y `src/` es lo que Nginx publica entero, que es exactamente cómo tres
copias `-old.*` acabaron descargables en su día.

Y `git clean` tampoco basta por su cuenta: un `checkout` desde otro commit deja
esos ficheros **en el índice**, y `clean` solo borra lo que no está seguido. De
ahí que el `reset` vaya primero.

Si en el servidor no hay nada local que conservar —lo normal—, esto hace lo
mismo de un tirón y sin margen de error:

```bash
git reset --hard origin/main
```

### Backend (`analytics-api`) — comprueba el esquema primero

```bash
cd ~/cv
git checkout v2.0.0        # completo, no por rutas: aquí git sí borra lo que sobra
docker compose build analytics-api
docker compose up -d --force-recreate analytics-api
curl -s https://devapis.cloud/health

git checkout main          # para no quedarse en detached HEAD
```

**El `.env` no se toca nunca en un rollback.** No está versionado, así que
`git checkout` no lo pisa —bien—, pero tampoco te lo repone si lo has
editado. Y hay uno que no puede cambiar jamás: `ANALYTICS_IP_SALT`. Si se
altera, todos los hashes anteriores dejan de corresponder con los nuevos y el
contador de visitantes únicos empieza a contar doble a la misma persona. No es
un dato que se pueda recalcular.

### Si el esquema ya migró

El servicio ejecuta su DDL al arrancar. Es aditiva —`CREATE TABLE IF NOT
EXISTS`, `ADD COLUMN IF NOT EXISTS`—, así que **una versión antigua no revienta
contra un esquema nuevo**: las columnas que no conoce tienen valor por defecto
y sus `INSERT` siguen siendo válidos.

Lo que sí cambia en silencio es la **vista**. `cv_analytics_summary` se crea
con `CREATE OR REPLACE`, así que la versión a la que vuelvas la reescribe con
*su* definición. Concretamente, cualquier versión anterior al filtrado de
tráfico interno la deja **sin** `WHERE NOT is_internal`, y las estadísticas
vuelven a contar tus propias visitas y los health checks del servidor. La
columna `is_internal` sigue ahí y sigue rellenándose; lo único que se pierde
es el filtro. Volver adelante lo restaura solo, sin tocar datos.

Comprobarlo en un segundo:

```bash
docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_HOST" \
  psql -U "$DB_USER" -d "$DB_NAME" -tAc \
  "SELECT pg_get_viewdef('cv_analytics_summary', true);" | grep -c is_internal
# 1 = la vista filtra · 0 = está contando tráfico propio
```

### El punto sin retorno

**La anonimización de IPs no se puede deshacer, y ya está hecha.** La columna
`ip_address` ya no existe en producción; lo que queda es el prefijo truncado y
un hash con sal, y de un hash no se recupera la IP. Consecuencia práctica:

> **Ninguna versión anterior a la anonimización se puede desplegar.** Su código
> hace `INSERT` sobre `ip_address` y fallaría con *column does not exist*. El
> límite inferior real del rollback es la primera etiqueta con IPs anonimizadas,
> no el primer commit del repositorio.

Antes de cualquier operación que toque la base, la copia:

```bash
docker exec "$DB_HOST" pg_dump -U "$DB_USER" -d "$DB_NAME" -t cv_visits \
  > cv_visits_backup_$(date +%F).sql
```

### Copias de seguridad de `src/assets/images/`

Los diplomas **no se pueden regenerar**: los emite Platzi y las imágenes
descargadas son el único original que hay. No los trates como un artefacto de
construcción.

Dónde está cada cosa:

| Qué | Dónde | ¿Sobrevive a perder el portátil? |
|---|---|---|
| Diplomas en WebP (lo que sirve el sitio) | `src/assets/images/*.webp`, versionados | sí, están en GitHub |
| PNG originales | historial de git, hasta el commit anterior a la conversión | sí, están en GitHub |
| PNG originales, copia de trabajo | `.backups/certificados-png/` | **no**, está en `.gitignore` |

Recuperar un PNG original del historial:

```bash
git show 20f87cb^:src/assets/images/Django.png > Django.png
```

Y si algún día hay que reconstruirlo todo desde cero, el enlace público de
verificación de cada certificado está en su atributo `data-verify` dentro de
`src/index.html`: desde ahí se vuelven a descargar los diplomas de Platzi.

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs: `docker compose logs analytics-api`
2. Verifica la conectividad de red: `docker network inspect server`
3. Prueba las queries SQL directamente en PostgreSQL

---

**¡Listo!** Ahora tienes un sistema completo de analytics funcionando 🎉
