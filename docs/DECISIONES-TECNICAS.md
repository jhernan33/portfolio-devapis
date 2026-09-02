# Decisiones técnicas

Este portafolio no es solo una página estática. Incluye un backend de analytics
propio —FastAPI, PostgreSQL, Traefik— que registra las visitas al CV sin
depender de terceros.

Este documento explica **por qué** está construido así, incluidas las decisiones
que resultaron equivocadas y hubo que corregir. Cada afirmación es verificable
contra el código de este repositorio.

---

## 1. Por qué un backend propio y no Google Analytics

| | Analytics de terceros | Este sistema |
|---|---|---|
| Datos del visitante | Salen hacia un tercero | No salen de mi infraestructura |
| Cookies | Sí | Ninguna |
| Banner de consentimiento | Obligatorio | Innecesario: no hay dato personal que consentir |
| Peso en el cliente | Decenas de KB de JS | Un `fetch` sin cuerpo |
| Responsabilidad de seguridad | Del proveedor | **Mía** |

La última fila es el precio real. Montar tu propio sistema de tracking significa
heredar los problemas de seguridad y privacidad que el proveedor te resolvía.
La sección 3 es la consecuencia directa de haber asumido ese coste.

El frontend se mantiene en **cero dependencias**: sin build, sin npm, sin
framework. El módulo de tracking son unas 30 líneas de JavaScript que fallan en
silencio, porque una métrica caída nunca debe degradar la experiencia de quien
está leyendo mi CV.

---

## 2. Privacidad por diseño

**Las direcciones IP no se almacenan.** De cada visita se guardan dos valores
derivados:

```python
# backend/app/privacy.py
ip = ipaddress.ip_address(raw_ip)            # valida que sea una IP real
network = 24 if ip.version == 4 else 48
prefix  = ip_network(f"{ip}/{network}").network_address   # 203.0.113.45 → 203.0.113.0
digest  = sha256(f"{SALT}:{ip}").hexdigest()              # hash con sal secreta
```

- **`ip_prefix`** — la red truncada a /24 en IPv4 y /48 en IPv6. Sirve para
  estadísticas agregadas de origen; no identifica a una persona.
- **`ip_hash`** — SHA-256 con una sal secreta. Permite contar visitantes únicos
  sin poder revertir el valor ni cruzarlo con otra base de datos.

**Qué se pierde:** geolocalización por visitante y cualquier análisis individual.

**Qué se conserva:** totales, únicos, series temporales, navegador, sistema
operativo y dispositivo. Es decir, todo lo que una métrica de portafolio
necesita de verdad.

La validación con `ipaddress` no es solo higiene de tipos. La IP llega en la
cabecera `X-Forwarded-For`, que **la controla el cliente**: Traefik añade la IP
real al final de la cadena, no impone la primera. Cualquiera puede enviar lo que
quiera ahí. Al exigir que el valor sea una IP parseable, un payload arbitrario
nunca llega a la base de datos.

---

## 3. Auditoría de seguridad (agosto 2026)

Antes de hacer público el repositorio audité el árbol completo, el historial
completo de commits y el comportamiento en producción. El historial estaba limpio de
credenciales. El código, no tanto.

### 3.1 La protección existía, pero fuera del control de versiones

El hallazgo más interesante no era una vulnerabilidad abierta: era una
**divergencia entre el repositorio y producción**.

Los endpoints de estadísticas no tenían ninguna autenticación en el código.
Estaban protegidos por un middleware `basicAuth` de Traefik configurado
directamente en el servidor y **ausente del repositorio**. En producción
respondían 401 correctamente, así que nunca hubo una fuga real. Pero:

- `docker compose up -d --force-recreate` reaplica las etiquetas del repo. Si esa
  configuración se perdía, la base de visitantes quedaba abierta sin que nada
  avisara.
- Cualquiera que leyera el repositorio veía un backend sin autenticación,
  porque en el código efectivamente no la había.

**Corrección:** la autenticación se movió a la aplicación.

```python
def require_analytics_auth(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok     = secrets.compare_digest(credentials.username.encode(), expected_user.encode())
    password_ok = secrets.compare_digest(credentials.password.encode(), expected_password.encode())
    if not (user_ok and password_ok):
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="cv-analytics"'})
```

Se comparan ambos campos siempre, sin cortocircuito, en tiempo constante. La
protección ahora viaja con el código y sobrevive a cualquier recreación de
contenedores.

**Principio:** si una medida de seguridad no está en el repositorio, no existe.
Solo estás confiando en que nadie toque el servidor.

### 3.2 El mismo middleware había roto el tracking

El `basicAuth` cubría todo el prefijo `/api`, incluido `POST /api/track`. El
frontend llevaba tiempo recibiendo 401 y tragándose el error en silencio —
exactamente el comportamiento que yo mismo había programado para que las
métricas nunca afectaran a la experiencia.

Una decisión defensiva razonable había ocultado un fallo total del sistema.

**Corrección:** dos routers con prioridad explícita.

```
Path(/api/track) o Path(/health)              → público, con rate limit   [prioridad 100]
PathPrefix(/api/analytics) o /analytics       → autenticado               [prioridad  90]
```

Los dos números tienen que estar **por encima de 73**, que es lo que puntúa el
router del panel de Traefik: v2 deriva la prioridad de la longitud de la regla,
así que el panel reclama todo `/api/*` que no lo supere. Y el público por encima
del privado, para que `/api/track` no caiga nunca en el autenticado. Una guarda
de la CI comprueba que ninguna ruta futura bajo `/api` se despliegue sin
prioridad explícita.

**Principio:** fallar en silencio es correcto de cara al usuario y peligroso de
cara al operador. Un fallo silencioso necesita, en alguna parte, un contador
ruidoso.

### 3.3 Credenciales por defecto

```python
password=os.getenv("DB_PASSWORD", "postgres")   # antes
```

Si la variable faltaba, el servicio arrancaba contra la base de producción
probando `postgres/postgres`, sin un solo mensaje de aviso.

**Corrección:** `DB_PASSWORD`, `ANALYTICS_USER`, `ANALYTICS_PASSWORD` y
`ANALYTICS_IP_SALT` no tienen valor por defecto. Faltar una es un error fatal,
tanto en `docker-compose.yaml` (`${VAR:?mensaje}`) como en el arranque de la
aplicación.

**Principio:** un valor por defecto inseguro es peor que un fallo, porque no
deja rastro.

### 3.4 XSS almacenado vía cabecera HTTP

El dashboard construía las tablas con `innerHTML` interpolando la IP guardada. Y
esa IP venía, sin validar, de una cabecera que controla el cliente.

Una petición con `X-Forwarded-For: <svg onload=…>` quedaba persistida y se
ejecutaba en cada carga del panel, que además se refresca cada 30 segundos.

**Corrección doble:**
- En la entrada, la validación con `ipaddress` descarta cualquier valor que no
  sea una IP (sección 2).
- En la salida, el dashboard se reescribió con `createElement` y `textContent`.
  Cero `innerHTML` con datos procedentes de una petición.

**Principio:** validar en la entrada y escapar en la salida. Cualquiera de las
dos por separado es una capa; las dos juntas son una defensa.

### 3.5 Copias de seguridad servidas al público

Tres archivos `*-old.html/js/css` estaban en `.gitignore`... y también en el
repositorio. `.gitignore` no desrastrea lo que git ya conocía.

Peor: vivían dentro de `src/`, el directorio que Nginx sirve. Eran accesibles en
`/cv/index-old.html`, con una copia antigua de mis datos de contacto.

**Corrección:** desrastreados con `git rm --cached` y movidos fuera de `src/`.

**Principio:** `.gitignore` previene, no cura. Y todo lo que esté en el
directorio servido, se sirve.

### 3.6 Resto de correcciones

| Hallazgo | Corrección |
|---|---|
| `/health` y `/api/track` devolvían `str(e)` al cliente | Se registra internamente, se responde genérico |
| `?limit=-1` generaba `LIMIT -1` → 500 sin manejar | `Query(20, ge=1, le=100)` |
| `/docs`, `/redoc`, `/openapi.json` expuestos | Deshabilitados |
| `POST /api/track` sin límite de tasa | Rate limit en Traefik: 10/min, ráfaga 20 |
| Servicio conectado como superusuario `postgres` | Base y rol dedicados con permisos mínimos |

---

## 4. Cómo se verificó

Ninguna corrección se dio por buena por leer el diff. Se levantó un PostgreSQL
desechable en una red aislada y se comprobó el ciclo completo:

| Comprobación | Resultado esperado |
|---|---|
| Arranque sin secretos | `RuntimeError` y salida distinta de cero |
| Migración de IPs históricas | `203.0.113.45` → `203.0.113.0`; IPv6 → `/48` |
| Los tres endpoints privados sin credenciales | 401 |
| Los mismos con credenciales | 200 |
| Usuario correcto y contraseña incorrecta | 401 |
| `X-Forwarded-For: <svg onload=alert(1)>` | Almacenado como `NULL`, cero marcado en la tabla |
| `?limit` = -1, 0, 101, 9999, `abc` | 422 |
| Migración de purga con filas sin anonimizar | Aborta y hace rollback |
| Migración tras anonimizar | Completa; el servicio sigue operativo |
| Backend contra el rol de permisos mínimos | Arranca y opera sin privilegios extra |

La migración que elimina las IPs históricas es **deliberadamente manual**. El
arranque rellena los campos anonimizados —operación reversible— pero borrar la
columna original exige ejecutar un script aparte que además aborta si detecta
filas sin migrar. Una operación irreversible sobre datos de producción no debe
ocurrir como efecto secundario de un despliegue.

---

## 5. Tests: tres fallos que nadie había visto (septiembre 2026)

La verificación de la sección 4 era reproducible pero manual, así que lo primero
que quedaba pendiente era automatizarla. La suite vive en `backend/tests` y no
necesita PostgreSQL: el pool se sustituye por un doble en memoria y
`ASGITransport` entra al enrutado sin ejecutar el arranque. Es deliberado — una
suite que exige levantar un contenedor termina por no ejecutarse.

Lo interesante es que **siete pruebas fallaron a la primera, y no por culpa de
las pruebas.**

El parseo de User-Agent se hace a mano, sin librería externa, para no añadir una
dependencia por una estadística. El riesgo de hacerlo a mano no está en las
palabras que se buscan, sino en el **orden** en que se buscan: cada cadena
contiene varias pistas a la vez y gana la primera que se mira.

| Lo que dice la cadena | Lo que se registraba | Lo que era |
|---|---|---|
| Opera lleva `Chrome/…` además de `OPR/` | Chrome | Opera |
| Android declara `Linux;` | Linux | Android |
| iPhone y iPad declaran `like Mac OS X` | macOS | iOS |

Es decir: **ninguna visita desde un móvil Android o iOS se había registrado nunca
como tal**, desde el primer día del sistema.

Lo que lo hacía invisible es que el tipo de dispositivo se deduce por separado,
con otra lista de palabras, y ese sí acertaba. El panel llevaba meses mostrando
`Mobile` y `macOS` en la misma fila sin que la contradicción saltara a la vista.

**Principio, y es el mismo de la sección 3.2:** no fue un fallo de lógica
compleja, fue un orden de `elif`. Ningún error, ninguna excepción, ningún log.
Los fallos que no producen error son los que sobreviven años, y la única
herramienta que los encuentra barato es la que ejerce el código con casos
concretos.

## 6. Refactorización del backend (septiembre 2026)

`backend/main.py` era un solo fichero de 943 líneas con cinco responsabilidades
y el panel embebido como una cadena. Se convirtió en el paquete `backend/app/`
con un módulo por responsabilidad (ver la tabla de abajo) sin cambiar el
comportamiento observable: los tests de contrato se conservaron y solo
cambiaron sus imports.

Lo que cambió por dentro y por qué:

- **Sin estado global.** `SETTINGS` y `DB_POOL` eran variables de módulo que
  obligaban a los tests a parchear y hacían que `anonymize_ip` dependiera de
  algo invisible en su firma. Ahora viven en `app.state`, las rutas los reciben
  por `Depends`, y las funciones puras reciben la sal y las redes como
  parámetros.
- **Un repositorio para todo el SQL.** `get_analytics` hacía ocho consultas en
  línea. El filtro `NOT is_internal` se define una vez y los cuatro contadores
  del resumen salen de una sola pasada por la tabla.
- **Modelos de respuesta.** La forma de la API no estaba escrita en ningún
  sitio. Con `/docs` deshabilitado, `app/models.py` es el contrato.
- **El panel como ficheros.** 250 líneas de HTML, CSS y JavaScript dentro de una
  cadena Python no pasaban por ningún linter ni por la CSP. Ahora son tres
  ficheros en `app/static/`, servidos bajo `/analytics/` con las mismas
  credenciales y con `script-src 'self'`.
- **User-Agent como tabla.** El orden de las comprobaciones, que ya había
  falseado la estadística una vez, pasa a ser un dato visible en lugar de una
  propiedad emergente de una cadena de `if`.

Las guardas de CI que leían `main.py` ahora recorren el paquete completo, y la
de autenticación falla si encuentra menos rutas privadas de las esperadas, para
que un cambio de prefijo no la deje comprobando nada.

---

## 7. Contenedores sin root (septiembre 2026)

Ningún Dockerfile declaraba `USER`: Nginx y el backend corrían como root
dentro del contenedor, y el backend acepta escrituras públicas en
`/api/track`. Si algo escapa del proceso, no debería tener privilegios.

- El frontend usa `nginxinc/nginx-unprivileged`, que corre como uid 101. Eso
  obliga a escuchar en **8080**: un proceso sin root no puede abrir el 80.
  Cambian `nginx.conf`, la etiqueta `loadbalancer.server.port` y los health
  checks; el visitante no ve ninguna diferencia porque Traefik sigue
  publicando el 443.
- El backend crea un usuario de sistema `app` y cambia a él antes del `CMD`.
- Ambos servicios llevan `no-new-privileges`, `cap_drop: ALL` y `read_only`
  con `tmpfs` en `/tmp`. Se comprobó en local que ninguno de los dos necesita
  escribir en disco: Nginx dirige sus temporales a `/tmp` y el backend no
  genera ni `.pyc`.

Una guarda de CI en el job `compose` vigila las cuatro piezas, porque dependen
unas de otras: volver a `listen 80` con la imagen sin privilegios mata el
contenedor al arrancar.

---

## 8. Las cabeceras de seguridad no se enviaban (septiembre 2026)

Al verificar los contenedores sin root se interrogó a Nginx respuesta por
respuesta y **ninguna llevaba CSP, HSTS, `X-Frame-Options` ni `nosniff`**.
Se comprobó contra la configuración original: en producción tampoco.

La causa es una regla de Nginx poco intuitiva: `add_header` no se acumula
entre niveles. En cuanto un `location` declara una cabecera propia, deja de
heredar todas las del bloque `server`. Los tres `location` que sirven el
sitio declaran `Cache-Control`, así que las cabeceras de seguridad, escritas
solo en `server`, no llegaban a nada. La CSP de la que dependía la guarda
"sin JavaScript inline" no estaba activa.

Arreglo: las cabeceras pasan a `nginx-security-headers.conf`, que se incluye
en `server` y en cada `location` con `add_header`. De paso desaparece el
`Cache-Control` duplicado que generaba `expires` junto al `add_header`.

No hay forma de detectar esto leyendo la configuración, así que la guarda de
CI construye la imagen, la arranca y comprueba en seis rutas que lleguen las
cuatro cabeceras y un único `Cache-Control`.

---

## 9. Migraciones, husos horarios y respaldo (septiembre 2026)

### El esquema tenía dos copias y ninguna sabía migrar

El DDL vivía en el código y en `database/init-analytics.sql`, con una guarda
de CI que solo comprobaba que las dos copias se parecieran. `CREATE TABLE IF
NOT EXISTS` no cubre cambiar una columna existente, así que cada cambio real
acababa en un script SQL suelto lanzado a mano contra producción y recordado
por quien estuviera delante.

Ahora hay un directorio `backend/migrations/` numerado y una tabla
`schema_migrations` que anota lo aplicado. El runner son cuarenta líneas y no
añade dependencias: traerse Alembic para una tabla habría sido peor. Una
migración que necesita Python —derivar un hash con sal, por ejemplo— comparte
la numeración con las de SQL.

Lo que **no** es una migración: `reconciliar_trafico_interno` sigue corriendo
en cada arranque, porque `ANALYTICS_IGNORE_NETWORKS` cambia. El caso que la
justifica es descubrir meses después que la IP del propio servidor llevaba
contándose como visitante; una migración anotada como aplicada no volvería a
mirar.

### "Hoy" dependía del reloj del contenedor de PostgreSQL

Las columnas eran `TIMESTAMP` sin zona. La aplicación insertaba UTC, pero
`NOW()` y `CURRENT_DATE` los resolvía PostgreSQL con la zona de su servidor,
que nadie fijaba. Los cortes de "hoy" y "últimas 24 horas" podían salir
desplazados sin que nada fallara: los números seguían apareciendo.

Las columnas pasan a `TIMESTAMPTZ`, la sesión se fija en UTC, y dónde empieza
el día pasa a ser una decisión explícita: `ANALYTICS_DISPLAY_TZ`, por defecto
`America/Caracas`. Con UTC-4 no es un detalle: una visita de las ocho de la
tarde en Caracas contaba como del día siguiente. Se verificó insertando una
visita a las 23:00 de Caracas —03:00 UTC del día siguiente— y comprobando que
cuenta como de hoy con `America/Caracas` y no con `UTC`.

La vista `cv_analytics_summary` pierde `visits_today`, que era su única
columna dependiente de una zona. Una vista que responde "hoy" en UTC mientras
el panel responde "hoy" en Caracas no es una comodidad: es una discrepancia
esperando a confundir a alguien. Las ventanas móviles que quedan son
intervalos y no dependen de la zona.

### El único dato irrecuperable no tenía respaldo

`tools/respaldar-db.sh` vuelca la base, **comprueba que el volcado contenga
la tabla** —un respaldo que no se verifica es un fichero— y rota los
antiguos. `backend/depurar_visitas.py` retira `user_agent` y `referer` de las
visitas de más de 24 meses: la cadena de User-Agent es el campo con más
entropía de cada fila y conservarla para siempre contradice la promesa del
pie del CV. Se conservan navegador, sistema y hash, que es lo que alimenta
las estadísticas.

Los dos scripts de mantenimiento comparten `backend/mantenimiento.py`: mismo
contrato de simulacro por defecto y `--aplicar` explícito, escrito una vez.

---

## 10. Qué es una visita (septiembre 2026)

Hasta aquí, "visita" era cualquier POST a `/api/track`. Eso incluía a los
rastreadores que ejecutan JavaScript, cada recarga y cada pestaña de la misma
persona, y no distinguía el CV en español del inglés. Con siete visitas
externas reales, alguien que recarga tres veces movía la métrica un 40%.

Cuatro columnas nuevas, ninguna de las cuales borra nada: las filas se siguen
guardando enteras y se siguen viendo en `/api/analytics/recent`, marcadas.

- **`is_bot`** sale de una lista de subcadenas en `useragent.py`, evaluada al
  registrar. La migración que reclasifica lo ya guardado importa esa misma
  función en lugar de reescribirla en SQL: mantener dos veces la lista es
  garantizar que se separen.
- **`is_repeat`** lo calcula la propia base dentro del `INSERT`. Preguntar
  antes y escribir después son dos viajes y una ventana en la que dos
  peticiones simultáneas se declaran la primera cada una.
- **`page`** llega del navegador y por eso no se guarda en crudo: se compara
  contra un conjunto cerrado y lo que no se reconoce se registra como `otro`.
  El cuerpo se limita a 512 bytes; `/api/track` es público y aceptar cuerpos
  arbitrarios por cortesía es regalar un vector de agotamiento de memoria.
- **`visitor_hash`** es `sha256(sal:ip:user-agent)`. `ip_hash` seguía contando
  como un visitante a toda una oficina detrás de un NAT. Se conserva `ip_hash`
  y los únicos usan `COALESCE` de los dos, porque romper esa continuidad
  significaría perder el histórico.

**Un fallo que los tests con doble en memoria no podían ver.** El `EXISTS`
del INSERT usaba `$13 - INTERVAL '30 minutes'` y PostgreSQL no puede inferir
el tipo de un parámetro en esa posición: dedujo `interval`, la comparación no
existía y **todas las visitas fallaban**. La suite pasaba porque el doble no
valida SQL; lo destapó la prueba de integración contra PostgreSQL real. El
arreglo es un `::timestamptz` explícito, y la lección es que el doble en
memoria protege la lógica, no el SQL.

---

## 11. Frontend: repetición, idioma y una guarda que no comprobaba nada (septiembre 2026)

- **`onActivate`.** El par `click` + `touchend` estaba copiado en cuatro
  módulos. En móvil llegan los dos y la acción se ejecutaba dos veces: el tema
  cambiaba y volvía en el mismo gesto. Ahora está escrito una vez, con la
  guarda de medio segundo, y hay un test móvil que lo fija.
- **`TEXTOS` y `t()`.** El idioma se miraba en cinco módulos con cinco
  ternarios. Bastaba con olvidar uno para que un lector de pantalla anunciara
  "Certificado Django" en la versión inglesa. Ahora se mira una vez.
- **`theme-init.js`.** `main.js` se carga con `defer`, así que el tema guardado
  se aplicaba después del primer pintado: quien tenía el oscuro veía un
  fogonazo blanco en cada carga. Este fichero, sin `defer` y en el `<head>`,
  lo aplica antes, y de paso es el único sitio donde vive la clave de
  `localStorage`.

### La comprobación de traducción encontró cuatro cosas

Comparar que la salida coincida con el generador solo detecta ediciones a
mano. No detecta lo que de verdad pasa: que se añada texto en español, no esté
en el diccionario y viaje intacto al inglés. La comprobación nueva extrae el
texto visible de las dos versiones y marca lo que aparezca idéntico y no esté
en una lista de excepciones explícita. Al estrenarla encontró:

- `Microservicios` en una etiqueta y en el JSON-LD (solo estaba traducido en
  la lista `<li>`),
- `aria-label="Cerrar"` del modal, que es justo lo que oye un lector de
  pantalla,
- `Platzi · jul 2026`: los once meses restantes estaban traducidos y julio no,
- `2011 - Presente`, el único periodo abierto del CV.

Ninguna de las cuatro se ve leyendo la página por encima.

### Un 404 que decía 200

`try_files ... /index.html` más `error_page 404 =200 /index.html` hacían que
cualquier ruta inexistente devolviera el CV entero con código 200. Para un
buscador eso es un *soft 404*: una página que afirma existir sin existir, en
un sitio que tiene sitemap y canonical. Ahora hay una página 404 propia y un
código de verdad. El reenvío de SPA no hacía falta: esto no es una SPA.

También se retira `X-XSS-Protection`: los navegadores actuales la ignoran y en
los que la implementaron el filtro llegó a introducir vulnerabilidades
propias.

### Una guarda que llevaba desde el principio sin comprobar nada

La de "sin JavaScript inline" ejecutaba `grep -nE '...' -P`. Combinar `-E` y
`-P` es un error de grep: el comando salía con código 2, el `if` lo leía como
"no hay coincidencias" y la guarda pasaba siempre. Se descubrió al ver el
aviso `conflicting matchers` ejecutándola en local. Corregida a `-P` solo y
verificada en negativo: con un `<script>` inline, falla.

---

## 12. Próximos pasos

- **Despliegue automático**: `deploy.yml` ya actualiza el VPS cuando la CI pasa
  en `main` y verifica el resultado desde fuera; queda configurar los secretos
  del servidor para activarlo.
- **Monitor externo continuo** y **vuelta atrás en el despliegue** (fase 6 del
  plan de mejoras).

El aviso de privacidad que figuraba aquí ya está en el pie del sitio, en las dos
versiones de idioma.

---

## Referencias en el código

| Tema | Dónde |
|---|---|
| Autenticación | `backend/app/security.py` |
| Anonimización y tráfico interno | `backend/app/privacy.py` |
| SQL y filtro `NOT is_internal` | `backend/app/repositories/visits.py` |
| Contrato de la API | `backend/app/models.py` |
| Qué cuenta como visita | `PERSONAS` y `VISITAS` en `backend/app/repositories/visits.py` |
| Rastreadores conocidos | `BOTS` en `backend/app/useragent.py` |
| Textos generados por JS | `TEXTOS` y `t()` en `src/main.js` |
| Tests de navegador | `tools/e2e/` |
| Routers, rate limit y secretos obligatorios | `docker-compose.yaml` |
| Esquema versionado | `backend/migrations/` y `backend/app/migrations.py` |
| Zona de presentación y corte del día | `backend/app/timeutils.py` |
| Respaldo y retención | `tools/respaldar-db.sh`, `backend/depurar_visitas.py` |
| Migración de purga | `database/migrate-anonymize-ips.sql` |
| Rol de permisos mínimos | `database/create-analytics-role.sql` |
| Runbook de despliegue | `DEPLOY-ANALYTICS.md` |
