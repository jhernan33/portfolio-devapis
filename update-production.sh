#!/bin/bash

# ============================================
# Actualizar producción
# ============================================
#
# Reconstruye las imágenes, recrea los servicios, ESPERA a que estén sanos de
# verdad y, si algo va mal, vuelve a la versión anterior.
#
# Lo que había antes: reconstruía solo el backend, dormía diez segundos fijos y
# daba el despliegue por bueno. Los diez segundos eran una adivinanza, y un
# fallo dejaba producción rota hasta que alguien lo mirara.

set -euo pipefail

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SERVICIOS=(cv analytics-api)
IMAGENES=(landpage:latest cv-analytics:latest)
ESPERA_MAXIMA=90        # segundos que se le dan a un contenedor para estar sano

# --------------------------------------------------------------------------
# Cronómetros por etapa.
#
# El total no dice nada accionable: cuarenta segundos pueden ser una imagen
# reconstruyéndose entera o un contenedor tardando en contestar, y son dos
# problemas distintos. Se mide cada etapa por separado y se imprime un resumen
# al final, también cuando el despliegue falla, que es cuando más importa saber
# dónde se fue el tiempo.
# --------------------------------------------------------------------------
INICIO=$(date +%s)
RESUMEN=()

ahora() { date +%s; }

marcar() {   # marcar <etiqueta> <instante en que empezó la etapa>
    local segundos=$(( $(ahora) - $2 ))
    RESUMEN+=("$1|$segundos")
    echo -e "   ${YELLOW}⏱  $1: ${segundos}s${NC}"
}

# `%-28s` de printf cuenta bytes, no caracteres: con "construcción" o
# "verificación" las tildes ocupan dos y la columna de segundos se descuadra.
# El relleno se calcula con ${#cadena}, que sí cuenta caracteres.
fila_resumen() {   # fila_resumen <etiqueta> <segundos>
    local relleno=$(( 28 - ${#1} ))
    [ "$relleno" -lt 1 ] && relleno=1
    printf '   %s%*s %4ss\n' "$1" "$relleno" "" "$2"
}

imprimir_resumen() {
    echo ""
    echo "⏱  Tiempos por etapa:"
    local fila
    for fila in ${RESUMEN[@]+"${RESUMEN[@]}"}; do
        fila_resumen "${fila%|*}" "${fila#*|}"
    done
    fila_resumen "TOTAL" "$(( $(ahora) - INICIO ))"
}

echo "🚀 Actualizando servicios en producción..."
echo ""

# --------------------------------------------------------------------------
# 1. Guardar a dónde volver.
#
# Se etiquetan las imágenes actuales antes de tocar nada. Sin esto, "volver
# atrás" significa reconstruir desde el commit anterior, que es justo lo que no
# se puede hacer con prisa y producción caída.
# --------------------------------------------------------------------------
echo "🔖 Etiquetando las imágenes actuales como :previa..."
hay_respaldo=1
for imagen in "${IMAGENES[@]}"; do
    if docker image inspect "$imagen" >/dev/null 2>&1; then
        docker tag "$imagen" "${imagen%:latest}:previa"
    else
        echo -e "   ${YELLOW}$imagen no existe todavía; no habrá vuelta atrás${NC}"
        hay_respaldo=0
    fi
done

# --------------------------------------------------------------------------
# 2. Reconstruir LAS DOS imágenes.
#
# `docker compose up` no reconstruye una imagen que ya existe, así que un
# cambio en un Dockerfile o en nginx.conf no llegaría a producción.
# --------------------------------------------------------------------------
echo "📦 Reconstruyendo las imágenes..."
etapa=$(ahora)
docker compose build
marcar "construcción de imágenes" "$etapa"

echo "🔄 Recreando los servicios..."
etapa=$(ahora)
docker compose up -d --force-recreate
marcar "recreación de contenedores" "$etapa"

# --------------------------------------------------------------------------
# 3. Esperar a que estén sanos, preguntando en lugar de adivinar.
# --------------------------------------------------------------------------
esperar_sano() {
    local servicio="$1" contenedor estado inicio
    inicio=$(ahora)
    contenedor=$(docker compose ps -q "$servicio")
    if [ -z "$contenedor" ]; then
        echo -e "   ${RED}$servicio no ha llegado a arrancar${NC}"
        return 1
    fi

    for _ in $(seq 1 "$ESPERA_MAXIMA"); do
        estado=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$contenedor")
        case "$estado" in
            healthy|running) echo "   $servicio: $estado en $(( $(ahora) - inicio ))s"; return 0 ;;
            unhealthy)       echo -e "   ${RED}$servicio: unhealthy tras $(( $(ahora) - inicio ))s${NC}"; return 1 ;;
        esac
        sleep 1
    done

    echo -e "   ${RED}$servicio sigue en '$estado' tras ${ESPERA_MAXIMA}s${NC}"
    return 1
}

echo "⏳ Esperando a que los servicios estén sanos..."
etapa=$(ahora)
sano=1
for servicio in "${SERVICIOS[@]}"; do
    esperar_sano "$servicio" || sano=0
done
marcar "espera a estar sanos" "$etapa"

# --------------------------------------------------------------------------
# 4. Comprobar desde fuera, con las mismas comprobaciones que el monitor.
# --------------------------------------------------------------------------
if [ "$sano" -eq 1 ]; then
    echo ""
    echo "🔍 Verificando producción..."
    # El script reintenta por su cuenta: Traefik tarda unos segundos en rehacer
    # su tabla de rutas tras recrear los contenedores, y durante esa ventana las
    # peticiones caen en su panel aunque el backend esté perfecto.
    etapa=$(ahora)
    ./tools/verificar-produccion.sh || sano=0
    marcar "verificación externa" "$etapa"
fi

# --------------------------------------------------------------------------
# 5. Si algo falló, volver atrás.
# --------------------------------------------------------------------------
if [ "$sano" -eq 0 ]; then
    echo ""
    if [ "$hay_respaldo" -eq 0 ]; then
        echo -e "${RED}❌ El despliegue ha fallado y no hay versión anterior a la que volver.${NC}"
        echo "   Revisa: docker compose logs --tail=50"
        imprimir_resumen
        exit 1
    fi

    echo -e "${YELLOW}↩️  El despliegue ha fallado. Volviendo a la versión anterior...${NC}"
    docker compose logs --tail=30

    etapa=$(ahora)
    for imagen in "${IMAGENES[@]}"; do
        docker tag "${imagen%:latest}:previa" "$imagen"
    done
    docker compose up -d --force-recreate

    for servicio in "${SERVICIOS[@]}"; do
        esperar_sano "$servicio" || true
    done
    marcar "vuelta atrás" "$etapa"

    echo ""
    etapa=$(ahora)
    if ./tools/verificar-produccion.sh; then
        echo -e "${YELLOW}⚠️  Se ha vuelto a la versión anterior y responde. El cambio NO está desplegado.${NC}"
    else
        echo -e "${RED}❌ Ni siquiera la versión anterior responde. Revisa el servidor a mano.${NC}"
    fi
    marcar "verificación tras vuelta atrás" "$etapa"
    imprimir_resumen
    exit 1
fi

# --------------------------------------------------------------------------
# 6. Todo bien.
# --------------------------------------------------------------------------
echo ""
echo "📊 Estado de los servicios:"
docker compose ps

imprimir_resumen

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Actualización completada y verificada${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 URLs:"
echo "   • CV:        https://devapis.cloud/cv"
echo "   • Panel:     https://devapis.cloud/analytics    (requiere credenciales)"
echo "   • API:       https://devapis.cloud/api/analytics (requiere credenciales)"
echo ""
echo "🗄️  Mantenimiento:"
echo "   ./tools/respaldar-db.sh                                          # respaldo"
echo "   docker compose exec analytics-api python /app/depurar_visitas.py # retención (simulacro)"
echo ""
