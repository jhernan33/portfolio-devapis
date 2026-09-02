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
docker compose build

echo "🔄 Recreando los servicios..."
docker compose up -d --force-recreate

# --------------------------------------------------------------------------
# 3. Esperar a que estén sanos, preguntando en lugar de adivinar.
# --------------------------------------------------------------------------
esperar_sano() {
    local servicio="$1" contenedor estado
    contenedor=$(docker compose ps -q "$servicio")
    if [ -z "$contenedor" ]; then
        echo -e "   ${RED}$servicio no ha llegado a arrancar${NC}"
        return 1
    fi

    for _ in $(seq 1 "$ESPERA_MAXIMA"); do
        estado=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$contenedor")
        case "$estado" in
            healthy|running) echo "   $servicio: $estado"; return 0 ;;
            unhealthy)       echo -e "   ${RED}$servicio: unhealthy${NC}"; return 1 ;;
        esac
        sleep 1
    done

    echo -e "   ${RED}$servicio sigue en '$estado' tras ${ESPERA_MAXIMA}s${NC}"
    return 1
}

echo "⏳ Esperando a que los servicios estén sanos..."
sano=1
for servicio in "${SERVICIOS[@]}"; do
    esperar_sano "$servicio" || sano=0
done

# --------------------------------------------------------------------------
# 4. Comprobar desde fuera, con las mismas comprobaciones que el monitor.
# --------------------------------------------------------------------------
if [ "$sano" -eq 1 ]; then
    echo ""
    echo "🔍 Verificando producción..."
    ./tools/verificar-produccion.sh || sano=0
fi

# --------------------------------------------------------------------------
# 5. Si algo falló, volver atrás.
# --------------------------------------------------------------------------
if [ "$sano" -eq 0 ]; then
    echo ""
    if [ "$hay_respaldo" -eq 0 ]; then
        echo -e "${RED}❌ El despliegue ha fallado y no hay versión anterior a la que volver.${NC}"
        echo "   Revisa: docker compose logs --tail=50"
        exit 1
    fi

    echo -e "${YELLOW}↩️  El despliegue ha fallado. Volviendo a la versión anterior...${NC}"
    docker compose logs --tail=30

    for imagen in "${IMAGENES[@]}"; do
        docker tag "${imagen%:latest}:previa" "$imagen"
    done
    docker compose up -d --force-recreate

    for servicio in "${SERVICIOS[@]}"; do
        esperar_sano "$servicio" || true
    done

    echo ""
    if ./tools/verificar-produccion.sh; then
        echo -e "${YELLOW}⚠️  Se ha vuelto a la versión anterior y responde. El cambio NO está desplegado.${NC}"
    else
        echo -e "${RED}❌ Ni siquiera la versión anterior responde. Revisa el servidor a mano.${NC}"
    fi
    exit 1
fi

# --------------------------------------------------------------------------
# 6. Todo bien.
# --------------------------------------------------------------------------
echo ""
echo "📊 Estado de los servicios:"
docker compose ps

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
