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
# backend/main.py
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
PathPrefix(/api/analytics) o /analytics       → autenticado               [prioridad  50]
```

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

## 5. Próximos pasos

- **Tests automatizados** con pytest sobre la anonimización, la autenticación y
  la validación de entrada. Hoy la verificación de la sección 4 es reproducible
  pero manual.
- **CI/CD** con GitHub Actions: lint, build de la imagen y despliegue.
- **Aviso de privacidad** visible en el sitio, describiendo lo de la sección 2.

---

## Referencias en el código

| Tema | Dónde |
|---|---|
| Autenticación y anonimización | `backend/main.py` |
| Routers, rate limit y secretos obligatorios | `docker-compose.yaml` |
| Esquema y vista | `database/init-analytics.sql` |
| Migración de purga | `database/migrate-anonymize-ips.sql` |
| Rol de permisos mínimos | `database/create-analytics-role.sql` |
| Runbook de despliegue | `DEPLOY-ANALYTICS.md` |
