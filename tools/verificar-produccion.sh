#!/bin/bash
#
# Comprueba desde fuera que producción está sana.
#
# Vive aquí y no dentro del workflow de despliegue porque lo usan dos: el
# despliegue, justo después de recrear los contenedores, y el monitor, cada
# media hora. Tenerlo dos veces habría garantizado que se separaran.
#
# Cada comprobación corresponde a un fallo que este proyecto ya tuvo:
#   * /cv sin cabeceras: la CSP y HSTS no llegaban a ninguna respuesta.
#   * /cv devolviendo 200 en rutas inexistentes: soft 404 para los buscadores.
#   * /health caído: el backend sin poder resolver DB_HOST, meses en bucle.
#   * /api/track con 401: el router cayendo en el panel de Traefik.
#   * /api/analytics sin credenciales: las estadísticas quedándose abiertas.
#
# Reintenta antes de dar nada por roto. Traefik descubre los contenedores por
# eventos de Docker y tarda unos segundos en rehacer su tabla de rutas: justo
# después de recrear los servicios, las peticiones caen en su panel y devuelven
# 401 o 404 aunque el backend esté perfectamente. Eso hizo fallar un despliegue
# que en realidad había ido bien, y disparó una vuelta atrás innecesaria. Media
# docena de intentos separados por unos segundos cubre esa ventana sin tapar
# una caída de verdad, que dura mucho más.
#
# Uso:
#   ./tools/verificar-produccion.sh                       # https://devapis.cloud
#   ./tools/verificar-produccion.sh http://localhost:8080
#   INTENTOS=1 ./tools/verificar-produccion.sh            # sin reintentos
#
# Sale con 0 si todo está bien y con 1 si algo falla, describiendo qué.

set -uo pipefail

BASE="${1:-https://devapis.cloud}"
TIEMPO=15
INTENTOS="${INTENTOS:-6}"
ESPERA="${ESPERA:-5}"

fallo() { echo "  ✗ $1"; fallos=$((fallos + 1)); }
bien()  { echo "  ✓ $1"; }

comprobar() {
fallos=0

# --------------------------------------------------------------- el CV
cabeceras=$(curl -s -D - -o /dev/null --max-time "$TIEMPO" "$BASE/cv/" || true)
if ! printf '%s\n' "$cabeceras" | grep -q '^HTTP/[0-9.]* 200'; then
    fallo "/cv no responde 200. Si el frontend cambió de imagen, ¿se reconstruyó (puerto 8080)?"
elif ! printf '%s\n' "$cabeceras" | grep -qi '^content-security-policy:'; then
    fallo "/cv responde sin Content-Security-Policy: las cabeceras de Nginx no llegan"
else
    bien "/cv responde con sus cabeceras de seguridad"
fi

codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIEMPO" "$BASE/cv/ruta-que-no-existe")
if [ "$codigo" = "404" ]; then
    bien "una ruta inexistente devuelve 404"
else
    fallo "una ruta inexistente devolvió $codigo; un 200 con el CV es un soft 404"
fi

# --------------------------------------------------------------- el backend
if curl -fsS --max-time "$TIEMPO" "$BASE/health" | grep -q '"ok"'; then
    bien "/health responde ok"
else
    fallo "/health no responde ok: ¿alcanza el backend a PostgreSQL? Devuelve 503 si no"
fi

codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIEMPO" -X POST "$BASE/api/track")
if [ "$codigo" = "200" ]; then
    bien "POST /api/track es público"
else
    fallo "/api/track devolvió $codigo. Si es 401, el router volvió a caer en el panel de Traefik"
fi

# GET y no HEAD (`curl -I`): estas rutas están declaradas solo para GET, así que
# a HEAD responden 405 sin cabecera de autenticación, y eso se lee exactamente
# igual que "las estadísticas están abiertas". El propio despliegue tuvo ese
# falso positivo: una alarma de seguridad donde no la había.
cabeceras=$(curl -s -o /dev/null -D - --max-time "$TIEMPO" "$BASE/api/analytics" || true)
codigo=$(printf '%s\n' "$cabeceras" | awk 'NR==1 {print $2}')
realm=$(printf '%s\n' "$cabeceras" | grep -i 'www-authenticate' || true)

if [ "$codigo" != "401" ]; then
    fallo "/api/analytics devolvió $codigo en lugar de 401: ¿se están sirviendo sin credenciales?"
else
    case "$realm" in
        *cv-analytics*) bien "/api/analytics pide credenciales y contesta la aplicación" ;;
        *traefik*)      fallo "/api/analytics lo contesta el panel de Traefik, no el backend" ;;
        *)              fallo "/api/analytics da 401 sin realm reconocible: $realm" ;;
    esac
fi

return $fallos
}

for intento in $(seq 1 "$INTENTOS"); do
    salida=$(comprobar)
    resultado=$?

    if [ "$resultado" -eq 0 ]; then
        echo "Verificando $BASE"
        printf '%s\n' "$salida"
        [ "$intento" -gt 1 ] && echo "  (correcto al intento $intento de $INTENTOS)"
        echo "Todo correcto."
        exit 0
    fi

    if [ "$intento" -lt "$INTENTOS" ]; then
        echo "Intento $intento de $INTENTOS: $resultado comprobaciones fallidas, reintentando en ${ESPERA}s..."
        sleep "$ESPERA"
    fi
done

echo "Verificando $BASE"
printf '%s\n' "$salida"
echo "$resultado comprobaciones fallidas tras $INTENTOS intentos."
exit 1
