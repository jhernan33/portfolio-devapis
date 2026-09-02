# Plan de mejoras

Fecha: 2026-09-02. Origen: revisión de arquitectura del proyecto completo
(frontend, backend, Nginx, Compose, CI, despliegue y herramientas).

Cada tarea indica **por qué**, **qué tocar**, **cómo saber que está hecha** y el
**principio** que aplica. El tamaño es orientativo: S (menos de 2 h), M (media
jornada), L (una jornada o más).

Restricciones que el plan respeta a propósito:

- El frontend sigue sin build ni dependencias.
- El backend no añade dependencias en tiempo de ejecución (fastapi, uvicorn,
  asyncpg). Sin Alembic, sin SQLAlchemy, sin librerías de User-Agent.
- Nada de lo que se haga aquí cambia la sal de las IPs ni borra datos.
- Toda guarda de CI que se toque se ajusta en el mismo commit que el cambio.

Orden de fases: cada una deja el proyecto desplegable. No se empieza la
refactorización (fase 3) sin la red de tests local de la fase 0.

---

## Fase 0. Preparación (S, medio día en total)

Objetivo: poder ejecutar todo en local antes de tocar nada.

### 0.1 Entorno de tests reproducible
- **Por qué:** hoy la suite solo corre en CI. Refactorizar sin poder correrla
  en local es refactorizar a ciegas.
- **Qué:** `backend/Makefile` (o `tools/test-backend.sh`) que crea
  `backend/.venv`, instala `requirements-dev.txt` y ejecuta `pytest`. Documentar
  en README y CLAUDE.md.
- **Hecho cuando:** `make test` pasa desde un clon limpio.

### 0.2 Dependabot
- **Por qué:** fastapi 0.115 y uvicorn 0.32 son de 2024. Nadie revisa CVEs a mano.
- **Qué:** `.github/dependabot.yml` para `pip` (backend), `docker` (ambos
  Dockerfiles) y `github-actions`. Frecuencia semanal, agrupando parches.
- **Hecho cuando:** aparece el primer PR automático y la CI lo valida.

### 0.3 Linter y formato del backend
- **Por qué:** clean code sin herramienta que lo vigile se erosiona.
- **Qué:** `ruff` en `requirements-dev.txt` (solo dev), `ruff.toml` con reglas
  básicas (E, F, I, B, UP) y un paso en el job `backend` de la CI.
- **Hecho cuando:** `ruff check backend` y `ruff format --check backend` pasan
  en CI.

---

## Fase 1. Seguridad y riesgos de arreglo rápido (S cada una, un día en total)

### 1.1 Rate limit en el router privado
- **Por qué:** HTTP Basic sin límite de intentos es fuerza bruta gratis.
  `compare_digest` evita ataques de temporización, no de volumen.
- **Qué:** en `docker-compose.yaml`, nuevo middleware
  `analytics-auth-ratelimit` (average 5, burst 10, period 1m) y asignarlo a
  `analytics-private`. Más estricto que el público porque un humano legítimo
  no falla la contraseña diez veces por minuto.
- **Hecho cuando:** un bucle de 15 peticiones sin credenciales devuelve 429 a
  partir de la undécima. Guarda de CI: todo router bajo `/api` declara un
  middleware de rate limit (extender la guarda de prioridades existente).

### 1.2 Contenedores sin root — HECHA 2026-09-02
Aplicada, y además de lo previsto: `no-new-privileges`, `cap_drop: ALL` y
sistema de ficheros de solo lectura con `tmpfs` en ambos servicios, con guarda
de CI en el job `compose`.
- **Por qué:** `/api/track` acepta escrituras públicas. Si algo escapa del
  proceso, hoy es root dentro del contenedor.
- **Qué:** `backend/Dockerfile`: `RUN adduser --system --no-create-home app` y
  `USER app` antes del `CMD`. `Dockerfile` del frontend: usar
  `nginxinc/nginx-unprivileged:1.27-alpine` y cambiar el puerto interno a 8080
  (etiqueta `loadbalancer.server.port` y healthcheck).
- **Hecho cuando:** `docker compose exec analytics-api id` no devuelve uid 0 y
  el despliegue verifica los tres endpoints.

### 1.2 bis. Cabeceras de seguridad de Nginx — HECHA 2026-09-02
Hallazgo durante la verificación de 1.2: ninguna respuesta de Nginx llevaba
CSP ni HSTS, en producción incluida, porque `add_header` en un `location`
anula los heredados. Cabeceras movidas a `nginx-security-headers.conf` e
incluidas en cada nivel; guarda de CI que arranca la imagen y lo comprueba.

### 1.3 Cabeceras de seguridad en las respuestas de FastAPI
- **Por qué:** Nginx las pone en el CV, pero el dashboard y la API salen sin
  ninguna. El dashboard además ejecuta JavaScript inline sin CSP.
- **Qué:** middleware `SecurityHeadersMiddleware` (una clase, una
  responsabilidad) que añade `X-Content-Type-Options`, `Referrer-Policy`,
  `Cache-Control: no-store` en rutas autenticadas y una CSP para `/analytics`.
  Requiere sacar el script del dashboard a un fichero (ver 3.5).
- **Hecho cuando:** test que comprueba las cabeceras en `/analytics`,
  `/api/analytics` y `/health`.

### 1.4 Logging en lugar de print
- **Por qué:** `print` no tiene nivel, ni marca de tiempo, ni se puede
  silenciar. El servicio estuvo meses en bucle de reinicio y nadie lo leyó.
- **Qué:** `logging` de la biblioteca estándar con formato
  `%(asctime)s %(levelname)s %(name)s %(message)s`, nivel por variable
  `LOG_LEVEL` (por defecto INFO). Sustituir todos los `print`. Los errores de
  tracking van a `logger.exception` para conservar la traza.
- **Hecho cuando:** `grep -n 'print(' backend/main.py` devuelve vacío y hay una
  guarda de CI que lo mantiene así.

### 1.5 Health check sin detalle público
- **Por qué:** `/health` es público y dice si la base de datos está caída.
  Es información útil para quien busque un momento de debilidad.
- **Qué:** `/health` público responde solo `{"status": "ok"}` o 503. El
  detalle de base de datos se mueve a `/api/analytics/health` bajo
  autenticación. El deploy y el monitor usan el público.
- **Hecho cuando:** test de la matriz de autenticación incluye la ruta nueva.

---

## Fase 2. Datos y tiempo (M, un día)

### 2.1 Migraciones versionadas
- **Por qué:** el DDL está duplicado en `main.py` y en
  `database/init-analytics.sql`, con una guarda de CI que solo comprueba que
  sigan iguales. Es la violación de DRY más cara del proyecto: cada cambio de
  esquema pasado necesitó un script a mano.
- **Qué:** directorio `backend/migrations/` con ficheros `0001_inicial.sql`,
  `0002_timestamptz.sql`, etc. Un módulo `migrations.py` de unas 40 líneas
  que crea `schema_migrations(version, applied_at)`, lee los ficheros en orden
  y aplica los pendientes dentro de una transacción. Sin dependencias nuevas.
  `database/init-analytics.sql` desaparece; el runbook apunta a las
  migraciones. `backfill_anonymized_ips` y `backfill_internal_flag` pasan a ser
  migraciones de datos, no código de arranque.
- **Hecho cuando:** un arranque contra base vacía aplica todo; un segundo
  arranque no aplica nada; test con el doble en memoria verifica el orden y la
  idempotencia. Eliminar la guarda de CI de "DDL sincronizado" y sustituirla
  por "todo fichero en migrations/ está numerado sin huecos".
- **Principio:** una única fuente de verdad del esquema.

### 2.2 TIMESTAMPTZ y zona horaria determinista
- **Por qué:** las columnas son `TIMESTAMP` sin zona. La aplicación inserta
  UTC, pero `visits_today` y `visits_last_24h` usan `NOW()` y `CURRENT_DATE`
  con la zona del servidor de Postgres. Si ese contenedor no está en UTC, los
  cortes diarios están desplazados y nadie lo nota.
- **Qué:** migración `ALTER COLUMN visited_at TYPE TIMESTAMPTZ USING visited_at
  AT TIME ZONE 'UTC'` (igual para `created_at`). En la creación del pool,
  `server_settings={"timezone": "UTC"}`. Recrear la vista.
- **Hecho cuando:** test que inserta a las 23:30 y 00:30 UTC y comprueba en qué
  día cae cada una.

### 2.3 Zona horaria de presentación configurable
- **Por qué:** `to_venezuela_time` fija UTC-4 en el código. Si el titular
  cambia de país, cambia el código.
- **Qué:** variable `ANALYTICS_DISPLAY_TZ` (por defecto `America/Caracas`)
  leída con `zoneinfo` de la biblioteca estándar. Renombrar la función a
  `to_display_time`.
- **Hecho cuando:** el dashboard muestra la hora local correcta y el nombre
  `venezuela` no aparece en el código.

### 2.4 Retención y respaldo
- **Por qué:** la tabla crece sin límite y no hay respaldo documentado en este
  repositorio.
- **Qué:** `tools/respaldar-db.sh` con `pg_dump` del contenedor, rotación de
  30 días y documentación de dónde se guarda. Política de retención: las
  filas mayores de 24 meses pierden `user_agent` y `referer` (los campos con
  más entropía), mediante una migración de datos periódica ejecutada por
  `tools/depurar-visitas.py --aplicar` con dry-run por defecto, como ya hace
  `migrar_user_agents.py`.
- **Hecho cuando:** el runbook de despliegue incluye el cron del respaldo y
  una restauración se ha probado una vez.

---

## Fase 3. Refactorización del backend (L, dos o tres días) — HECHA 2026-09-02

Aplicada en su totalidad. Diferencias respecto a lo previsto: el resumen
agrupa los cuatro contadores en una consulta y deja los cinco desgloses como
consultas separadas (ocho viajes pasan a seis), en lugar de una única CTE que
habría hecho ilegible el SQL. La tarea 2.1 (migraciones) sigue pendiente, así
que `migrations.py` no existe todavía y el DDL vive en `app/db.py`.

Objetivo: pasar de un fichero de 943 líneas con cinco responsabilidades a un
paquete pequeño donde cada módulo tiene una. Sin cambiar el comportamiento
observable: la matriz de tests de la fase 0 es la red.

### 3.1 Estructura de paquete
```
backend/
  app/
    __init__.py        create_app()  (factoría; sin estado global)
    config.py          Settings (dataclass frozen) + load_settings()
    logging.py         configuración del logger
    security.py        require_analytics_auth, SecurityHeadersMiddleware
    privacy.py         anonymize_ip, is_internal_ip, client_ip_from_request
    useragent.py       parse_user_agent (tabla de reglas)
    db.py              create_pool, get_conn (dependencia)
    migrations.py      runner de la fase 2
    repositories/
      visits.py        VisitRepository: insert, summary, top_*, recent
    routes/
      public.py        /api/track, /health
      analytics.py     /api/analytics, /recent, /analytics
    static/
      dashboard.html
      dashboard.js
      dashboard.css
  migrations/
  main.py              app = create_app()   (dos líneas, para uvicorn)
```
- **Principios:** SRP por módulo; DIP porque las rutas reciben el repositorio y
  la configuración por `Depends`, no por variable global; OCP en el parser de
  User-Agent, que pasa a ser una tabla ordenada de `(patrón, valor)` a la que
  se añade una fila sin tocar la lógica.
- **Hecho cuando:** `main.py` tiene menos de 10 líneas, ningún módulo supera
  200, y `pytest` pasa sin cambios en los tests de comportamiento (solo
  cambian los imports en `conftest.py`).

### 3.2 Eliminar el estado global
- **Por qué:** `SETTINGS` y `DB_POOL` globales obligan a los tests a
  parchear módulos, y hacen que `anonymize_ip` dependa de una variable
  invisible en su firma.
- **Qué:** `Settings` se guarda en `app.state.settings`; el pool en
  `app.state.pool`. `anonymize_ip(raw_ip, salt)` e
  `is_internal_ip(raw_ip, ignore_networks)` reciben lo que necesitan como
  parámetros. Dependencias `get_settings(request)` y `get_repo(request)`.
- **Hecho cuando:** `grep -rn 'global ' backend/app` devuelve vacío.

### 3.3 Repositorio de visitas
- **Por qué:** `get_analytics` hace ocho consultas en línea. La lógica SQL
  mezclada con la de HTTP no se puede probar por separado.
- **Qué:** clase `VisitRepository(conn)` con un método por consulta. Las ocho
  consultas del resumen se agrupan en una sola llamada `summary()` que ejecuta
  una CTE, reduciendo ocho viajes a la base a uno. `WHERE NOT is_internal` se
  define una vez como constante `EXTERNAS`.
- **Hecho cuando:** los tests de endpoints usan un `FakeVisitRepository` en
  lugar de simular `fetchval` por orden de llamada.

### 3.4 Modelos de respuesta
- **Por qué:** las rutas devuelven diccionarios construidos a mano; la forma
  de la API no está en ningún sitio.
- **Qué:** modelos Pydantic (ya viene con FastAPI, no es dependencia nueva)
  `Summary`, `AnalyticsResponse`, `RecentVisit`, `TrackResponse` como
  `response_model`. Generan validación y documentan el contrato sin exponer
  `/docs`.
- **Hecho cuando:** un campo mal escrito en una ruta falla en el test, no en
  producción.

### 3.5 Dashboard como ficheros estáticos
- **Por qué:** 250 líneas de HTML, CSS y JavaScript dentro de una cadena
  Python no pasan por ningún linter, ni por la CSP, ni por el resaltado del
  editor.
- **Qué:** `static/dashboard.html`, `dashboard.css` y `dashboard.js` leídos
  una vez en el arranque y servidos por rutas bajo `/analytics/` con la misma
  dependencia de autenticación (el router privado ya cubre el prefijo).
  Reutilizar la disciplina de `createElement`/`textContent`.
- **Hecho cuando:** `/analytics` responde con CSP `script-src 'self'` y el
  dashboard funciona. La guarda de CI de "sin JavaScript inline" se extiende a
  `backend/app/static`.

### 3.6 Parser de User-Agent como tabla
- **Por qué:** la cadena de `if/elif` es correcta hoy porque alguien la
  ordenó a mano y escribió un test. Una tabla hace que el orden sea un dato
  visible, no una propiedad emergente del código.
- **Qué:**
  ```python
  NAVEGADORES = (("edg", "Edge"), ("opr", "Opera"), ("opera", "Opera"),
                 ("chrome", "Chrome"), ("firefox", "Firefox"), ("safari", "Safari"))
  ```
  y una función genérica `primera_coincidencia(ua, tabla, defecto)`. Añadir
  `BOTS` (ver 4.1) en la misma forma. Los tests existentes de orden se
  conservan tal cual.
- **Hecho cuando:** `parse_user_agent` tiene menos de 15 líneas.

### 3.7 Actualizar CLAUDE.md y las guardas de CI
- **Qué:** CLAUDE.md deja de decir "single-file"; describe el paquete. La
  guarda "toda ruta de datos exige autenticación" pasa a recorrer
  `backend/app/routes`. La guarda "ninguna IP en claro" pasa a recorrer
  `repositories`.
- **Hecho cuando:** la CI está en verde con las guardas apuntando a las rutas
  nuevas y `git grep 'main.py' CLAUDE.md README.md` no encuentra referencias
  obsoletas.

---

## Fase 4. Calidad de los datos de analytics (M, un día)

### 4.1 Filtro de bots
- **Por qué:** cualquier rastreador que ejecute JavaScript cuenta como
  visita, y un `curl -X POST` externo también.
- **Qué:** columna `is_bot BOOLEAN NOT NULL DEFAULT FALSE` (migración). Tabla
  `BOTS` en `useragent.py` con `bot`, `crawler`, `spider`, `headless`,
  `lighthouse`, `curl`, `wget`, `python-requests`. Los agregados filtran
  `NOT is_bot` igual que `NOT is_internal`; `/recent` los muestra marcados.
  Migración de datos con el mismo script que `migrar_user_agents.py`
  (reutilizar su estructura dry-run/aplicar; extraer esa estructura a
  `tools/migracion_base.py` para no copiarla una tercera vez).
- **Hecho cuando:** test con diez User-Agent de bots conocidos y diez de
  navegadores reales.

### 4.2 Deduplicación de recargas
- **Por qué:** cada recarga y cada pestaña abierta es una visita. Con siete
  visitas externas reales, una persona curiosa que recarga tres veces
  distorsiona el 40%.
- **Qué:** columna `is_repeat`: verdadero si existe una fila con el mismo
  `ip_hash` y `user_agent` en los últimos 30 minutos. Se calcula en el
  `INSERT` con una subconsulta; no requiere estado en la aplicación. Los
  agregados de "visitas" excluyen repetidas; "visitantes únicos" no cambia.
- **Hecho cuando:** dos POST seguidos desde el mismo cliente dejan la segunda
  fila marcada.

### 4.3 Registrar la página visitada
- **Por qué:** hoy no se sabe si la visita fue al CV en español o en inglés.
- **Qué:** el frontend envía `{"page": location.pathname}` en el cuerpo (ya
  manda `Content-Type: application/json`). El backend valida contra una lista
  cerrada (`/cv`, `/cv/`, `/cv/en/`) y guarda `page VARCHAR(20)`. Cualquier
  otro valor se guarda como `otro`, nunca el valor crudo.
- **Hecho cuando:** el resumen incluye visitas por idioma y un test rechaza un
  `page` arbitrario.

### 4.4 Visitante único más robusto
- **Por qué:** el hash es de la IP exacta: una oficina detrás de NAT es un
  visitante, una IP dinámica son varios.
- **Qué:** columna adicional `visitor_hash = sha256(sal:ip:user_agent)`.
  `ip_hash` se conserva para no romper la continuidad histórica. Los
  agregados usan `visitor_hash` cuando existe y caen a `ip_hash` en filas
  antiguas (`COALESCE`).
- **Hecho cuando:** dos User-Agent distintos desde la misma IP cuentan como
  dos visitantes en el test.

---

## Fase 5. Frontend (M, un día)

### 5.1 Un solo helper de activación
- **Por qué:** `click` + `touchend` con `preventDefault` está copiado en
  cuatro módulos. Es el mismo patrón, cuatro oportunidades de divergir.
- **Qué:** función `onActivate(el, handler)` al principio del IIFE que
  registra ambos eventos y evita el doble disparo con una marca de tiempo.
  Los cuatro módulos la usan.
- **Principio:** DRY.
- **Hecho cuando:** `grep -c "touchend" src/main.js` devuelve 1.

### 5.2 Un solo punto de idioma
- **Por qué:** `document.documentElement.lang === 'en'` aparece en cinco
  módulos, cada uno con su propio par de cadenas.
- **Qué:** objeto `I18N` con todas las cadenas generadas por JavaScript en
  ambos idiomas y una función `t(clave)`. Los módulos consumen `t()`.
- **Hecho cuando:** la comparación con `'en'` aparece una sola vez.

### 5.3 Quitar el ruido de consola
- **Por qué:** once `console.log` activos en producción. No aportan nada al
  visitante y ensucian la consola de quien inspeccione el sitio.
- **Qué:** eliminarlos. Conservar solo `console.debug` en el fallo del
  tracking, que es silencioso por defecto.
- **Hecho cuando:** guarda de CI: `grep -c 'console.log' src/main.js` es 0.

### 5.4 Generador de inglés que falla ante texto sin traducir
- **Por qué:** una frase nueva en español pasa a la versión inglesa intacta y
  la CI no lo ve, porque solo comprueba que la salida coincida con el
  generador.
- **Qué:** tras generar, extraer los nodos de texto de ambas versiones con
  `html.parser`. Todo texto idéntico en las dos que no esté en una lista
  `INVARIANTES` (nombres propios, tecnologías, fechas, números, correos)
  hace fallar `--check` listando las frases. Es una lista de excepciones
  explícita, no una heurística.
- **Hecho cuando:** añadir un párrafo en español sin traducción rompe la CI
  con el texto exacto en el mensaje.

### 5.5 404 real en Nginx
- **Por qué:** `try_files ... /index.html` y `error_page 404 =200` convierten
  cualquier URL en un 200 con el CV. Los buscadores lo tratan como soft-404.
  El sitio no es una SPA con rutas de cliente; no necesita ese fallback.
- **Qué:** `try_files $uri $uri/ =404;`, página `src/404.html` mínima con el
  mismo diseño y enlace al inicio, `error_page 404 /404.html;`. Eliminar la
  regla de `50x.html` que apunta a un fichero inexistente, o crear el fichero.
  Quitar `X-XSS-Protection`, cabecera obsoleta que los navegadores modernos
  ignoran y que en versiones antiguas introducía vulnerabilidades.
- **Hecho cuando:** `curl -o /dev/null -w '%{http_code}' https://devapis.cloud/cv/noexiste`
  devuelve 404 y `/cv/en/` sigue devolviendo 200.

### 5.6 Preload de la hoja de estilos crítica y fuentes
- **Por qué:** con 97 KB no hay problema de peso, pero sí un salto visual al
  aplicar el tema guardado en `localStorage` después del primer pintado.
- **Qué:** script de 5 líneas al inicio del `<head>` que lee la clave y pone
  `data-theme` antes de que exista el `<body>`. Como la CSP bloquea inline,
  va en `src/theme-init.js` referenciado con `<script src>` sin `defer`.
  Mover `loadTheme()` de `ThemeManager` allí (DRY).
- **Hecho cuando:** recargar con tema oscuro no muestra fondo claro ni un
  fotograma.

### 5.7 Tests de extremo a extremo mínimos
- **Por qué:** el documento de decisiones los lista como pendientes. El
  checklist manual de CLAUDE.md tiene seis puntos que nadie ejecuta en cada
  cambio.
- **Qué:** Playwright en un job separado de la CI (`frontend-e2e`), sirviendo
  `src/` con `python -m http.server`. Seis pruebas: tema persiste, modal abre
  y devuelve el foco, menú móvil abre y cierra con Escape, botón de
  certificaciones cambia el texto, enlaces de navegación marcan activo,
  tracking hace un POST. Sin dependencias en `src/`: Playwright vive en
  `tools/e2e/`.
- **Hecho cuando:** el job pasa en CI en menos de dos minutos.

---

## Fase 6. Infraestructura y operación (M, un día y medio)

### 6.1 Compose de desarrollo
- **Por qué:** el stack no se levanta en una máquina limpia: las redes son
  externas y Postgres es de otro proyecto.
- **Qué:** `docker-compose.dev.yaml` con un servicio `postgres:17-alpine`,
  red interna propia, `.env.dev` de ejemplo con valores no secretos, y sin
  Traefik: puertos 8080 (cv) y 8000 (api) publicados. Se usa con
  `docker compose -f docker-compose.dev.yaml up`.
- **Hecho cuando:** un clon limpio levanta el stack, `/api/track` inserta y
  `/analytics` muestra la fila. Guarda de CI: `docker compose -f
  docker-compose.dev.yaml config` resuelve.

### 6.2 Verificación de producción como script reutilizable
- **Por qué:** las tres comprobaciones viven dentro de `deploy.yml`; el
  monitor de 6.3 las necesita también. Copiarlas sería la segunda copia.
- **Qué:** `tools/verificar-produccion.sh` con las tres comprobaciones
  actuales más el 404 real y el 429 del rate limit. `deploy.yml` lo invoca.
- **Principio:** DRY entre despliegue y monitorización.
- **Hecho cuando:** `deploy.yml` no contiene ningún `curl`.

### 6.3 Monitor continuo
- **Por qué:** el servicio estuvo meses caído sin que nadie lo viera. El
  deploy verifica una vez; entre despliegues no hay nada.
- **Qué:** workflow `monitor.yml` con `schedule` cada 30 minutos que ejecuta
  `tools/verificar-produccion.sh`. Si falla, abre o actualiza un issue con
  etiqueta `produccion-caida` (acción `actions/github-script`). Complemento
  gratuito externo: un check de `/health` en healthchecks.io o similar, por
  si GitHub Actions es lo que está caído.
- **Hecho cuando:** parar el backend a mano produce un issue en menos de una
  hora.

### 6.4 Despliegue con espera real y vuelta atrás
- **Por qué:** `sleep 10` es una adivinanza y un fallo de verificación deja
  producción rota.
- **Qué:** `update-production.sh` etiqueta la imagen anterior como
  `cv-analytics:previa` antes de construir, espera con un bucle sobre
  `docker inspect --format '{{.State.Health.Status}}'` hasta `healthy` o 60 s,
  y si la verificación falla recrea con `previa`. Reescribir sus comentarios
  obsoletos ("cambió endpoint /dashboard").
- **Hecho cuando:** un despliegue con un backend que no arranca termina con la
  versión anterior sirviendo y el workflow en rojo con el motivo.

### 6.5 Acciones de GitHub fijadas por hash
- **Por qué:** `actions/checkout@v4` es una etiqueta móvil; la CI ejecuta lo
  que haya en ella hoy.
- **Qué:** fijar por SHA con comentario de versión. Dependabot (0.2) las
  actualiza.
- **Hecho cuando:** ningún `uses:` termina en `@vN`.

### 6.6 Postgres con la aplicación en su propio Compose (opcional)
- **Por qué:** la base pertenece a otro proyecto y `db-internal` es una red
  ajena. Cada migración de servidor exige recordar esa dependencia.
- **Qué:** evaluar traer un Postgres dedicado al analytics dentro de este
  Compose, con volumen propio y respaldo de 2.4. Solo si el otro proyecto no
  lo necesita compartido. Decisión documentada en DECISIONES-TECNICAS.md sea
  cual sea.
- **Hecho cuando:** existe la sección de decisión con los pros y contras
  medidos en producción.

---

## Fase 7. Documentación (S, medio día)

- CLAUDE.md: nueva estructura del backend, `make test`, Compose de desarrollo,
  guardas nuevas.
- README: sección de analytics actualizada (bots, repetidas, página), quitar
  "NUEVO" y las consultas SQL que hablan de "Top 10 IPs" (ya no hay IPs).
- DEPLOY-ANALYTICS.md: migraciones en lugar de `init-analytics.sql`, respaldo,
  monitor, vuelta atrás.
- DECISIONES-TECNICAS.md: sección 7 con las decisiones de este plan y sus
  fechas.
- Eliminar `analytics-backend-proposal.md` o marcarlo como histórico en su
  primera línea: describe un diseño que ya no coincide con el código.

---

## Guardas de CI que añade este plan

| Guarda | Fase |
|---|---|
| Todo router bajo `/api` declara rate limit | 1.1 |
| Sin `print(` en el backend | 1.4 |
| Migraciones numeradas sin huecos | 2.1 |
| Sin JavaScript inline en `backend/app/static` | 3.5 |
| Rutas autenticadas: recorrer `backend/app/routes` | 3.7 |
| Sin `console.log` en `src/main.js` | 5.3 |
| Texto sin traducir en la versión inglesa | 5.4 |
| `docker-compose.dev.yaml` resuelve | 6.1 |
| Ningún `uses:` con etiqueta móvil | 6.5 |

## Lo que este plan no hace, a propósito

- No introduce un framework de frontend ni un bundler. El sitio pesa 97 KB y
  no tiene lógica que lo justifique.
- No introduce un ORM ni Alembic. Una tabla y un runner de 40 líneas bastan,
  y cada dependencia es una superficie de ataque más en un servicio expuesto.
- No añade autenticación con sesiones o JWT al dashboard. HTTP Basic sobre
  TLS con rate limit es proporcional a un panel de una persona.
- No cambia la sal ni la política de anonimización. El coste sería perder la
  continuidad de visitantes únicos sin ganar privacidad.
