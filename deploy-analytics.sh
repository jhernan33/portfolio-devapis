#!/bin/bash

# ============================================
# Script de Despliegue - CV Analytics
# ============================================
# Automatiza el despliegue del sistema de analytics
# Uso: ./deploy-analytics.sh

set -e  # Exit on error

echo "🚀 Iniciando despliegue de CV Analytics..."
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# 1. Verificar pre-requisitos
# ============================================

echo "📋 Verificando pre-requisitos..."

# Verificar que existe docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no está instalado${NC}"
    exit 1
fi

# Verificar que existe docker compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose no está instalado${NC}"
    exit 1
fi

# El contenedor de PostgreSQL se comprueba más abajo, una vez cargado .env:
# hay que contrastar el DB_HOST real, no una cadena fija. La versión anterior
# hacía `docker ps -a | grep -q postgres17` y daba verde en un host cuyo
# contenedor se llama `postgres17_qa-db-1` — es decir, aprobaba justo el caso
# que debía detectar, y el servicio arrancaba a estrellarse en bucle.

# Verificar que la red server existe
if ! docker network ls | grep -q server; then
    echo -e "${YELLOW}⚠️  Red 'server' no encontrada. Creándola...${NC}"
    docker network create server
fi

echo -e "${GREEN}✅ Pre-requisitos verificados${NC}"
echo ""

# ============================================
# 2. Verificar archivo .env
# ============================================

echo "🔧 Verificando configuración..."

if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Archivo .env no encontrado${NC}"
    echo "   Creando .env desde .env.example..."

    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  IMPORTANTE: Edita el archivo .env con tus credenciales reales${NC}"
        echo "   Ejecuta: nano .env"
        echo ""
        read -p "Presiona Enter cuando hayas configurado el archivo .env..."
    else
        echo -e "${RED}❌ Archivo .env.example no encontrado${NC}"
        exit 1
    fi
fi

# Cargar y validar las variables obligatorias
set -a
# shellcheck disable=SC1091
. ./.env
set +a

MISSING=""
for VAR in DB_HOST DB_NAME DB_USER DB_PASSWORD ANALYTICS_USER ANALYTICS_PASSWORD ANALYTICS_IP_SALT; do
    if [ -z "${!VAR}" ]; then
        MISSING="$MISSING $VAR"
    fi
done

if [ -n "$MISSING" ]; then
    echo -e "${RED}❌ Faltan variables obligatorias en .env:$MISSING${NC}"
    echo "   Genera los secretos con:"
    echo "     openssl rand -base64 32   # ANALYTICS_PASSWORD"
    echo "     openssl rand -hex 32      # ANALYTICS_IP_SALT"
    exit 1
fi

DB_PORT="${DB_PORT:-5432}"

# El contenedor tiene que existir con ESE nombre exacto. Comparación exacta,
# no `grep`: una subcadena coincide con contenedores que no son el nuestro.
if ! docker ps -a --format '{{.Names}}' | grep -qxF "$DB_HOST"; then
    echo -e "${RED}❌ No existe ningún contenedor llamado exactamente '${DB_HOST}'${NC}"
    echo "   DB_HOST es el nombre del contenedor de PostgreSQL. Candidatos:"
    docker ps -a --format '     {{.Names}}  ({{.Status}})' | grep -i postgres || echo "     (ninguno)"
    exit 1
fi

# Y tiene que compartir red con analytics-api, o el contenedor no resolverá
# el nombre por muy correcto que sea.
DB_NETS=$(docker inspect "$DB_HOST" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}')
echo "   Redes de ${DB_HOST}: ${DB_NETS}"
if ! grep -qE 'server|db-internal' <<<"$DB_NETS"; then
    echo -e "${YELLOW}⚠️  ${DB_HOST} no está en 'server' ni en 'db-internal'.${NC}"
    echo "   Añade su red a la clave 'networks' de analytics-api en docker-compose.yaml,"
    echo "   o analytics-api fallará con 'gaierror: name resolution'."
fi

echo -e "${GREEN}✅ Configuración verificada${NC}"
echo "   Base de datos: ${DB_USER}@${DB_HOST}/${DB_NAME}"
echo ""

# Todas las operaciones psql usan la base y el usuario de .env, no valores
# fijos: con una base dedicada (database/create-analytics-role.sql) el
# esquema debe crearse ahí y no en `postgres`.
# PGPASSWORD va por entorno para no dejar la contraseña en la lista de procesos.
PSQL="docker exec -i -e PGPASSWORD=${DB_PASSWORD} ${DB_HOST} psql -U ${DB_USER} -d ${DB_NAME}"

# Comprobar que las credenciales de .env funcionan antes de seguir
if ! $PSQL -tAc "SELECT 1" >/dev/null 2>&1; then
    echo -e "${RED}❌ No se puede conectar como ${DB_USER} a ${DB_NAME} en ${DB_HOST}${NC}"
    echo "   Comprueba DB_HOST / DB_NAME / DB_USER / DB_PASSWORD en .env y que la base exista."
    exit 1
fi

# ============================================
# 3. Crear tabla en PostgreSQL
# ============================================

echo "📊 Creando tabla en PostgreSQL..."

# Verificar si la tabla ya existe
TABLE_EXISTS=$($PSQL -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='cv_visits')")

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${YELLOW}⚠️  La tabla cv_visits ya existe${NC}"
    read -p "¿Quieres recrearla? (elimina todos los datos) [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Eliminando tabla existente..."
        $PSQL -c "DROP TABLE IF EXISTS cv_visits CASCADE;"
    else
        echo "   Manteniendo tabla existente"
    fi
fi

# Ejecutar script SQL
echo "   Ejecutando script SQL..."
cat database/init-analytics.sql | $PSQL

# Verificar que se creó correctamente
TABLE_EXISTS=$($PSQL -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='cv_visits')")

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${GREEN}✅ Tabla creada correctamente${NC}"
else
    echo -e "${RED}❌ Error al crear la tabla${NC}"
    exit 1
fi

echo ""

# ============================================
# 4. Build y deploy
# ============================================

echo "🐳 Construyendo y desplegando servicios..."

# Build de la imagen
echo "   Building backend..."
docker compose build analytics-api

# Levantar servicios
echo "   Levantando servicios..."
docker compose up -d

echo -e "${GREEN}✅ Servicios levantados${NC}"
echo ""

# ============================================
# 5. Verificar health checks
# ============================================

echo "🏥 Verificando health checks..."
echo "   Esperando 10 segundos para que los servicios inicien..."
sleep 10

# Verificar estado de contenedores
echo ""
echo "Estado de contenedores:"
docker compose ps

echo ""

# Esperar a que el health check pase
MAX_RETRIES=30
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' cv-analytics 2>/dev/null || echo "unhealthy")

    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo -e "${GREEN}✅ Backend healthy${NC}"
        break
    fi

    echo -n "."
    sleep 2
    RETRY=$((RETRY + 1))
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ Backend no pasó el health check después de 60s${NC}"
    echo "   Ver logs: docker compose logs analytics-api"
    exit 1
fi

echo ""

# ============================================
# 6. Probar endpoints
# ============================================

echo "🧪 Probando endpoints..."

# Test 1: Health check
echo -n "   Probando /health... "
HEALTH_RESPONSE=$(curl -s https://devapis.cloud/health | grep -o "healthy" || echo "failed")

if [ "$HEALTH_RESPONSE" = "healthy" ]; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    echo "      Respuesta: $HEALTH_RESPONSE"
fi

# Test 2: Track endpoint
echo -n "   Probando /api/track... "
TRACK_RESPONSE=$(curl -s -X POST https://devapis.cloud/api/track | grep -o "tracked" || echo "failed")

if [ "$TRACK_RESPONSE" = "tracked" ]; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    echo "      Respuesta: $TRACK_RESPONSE"
fi

# Test 3: Analytics endpoint (autenticado)
echo -n "   Probando /api/analytics (con credenciales)... "
ANALYTICS_RESPONSE=$(curl -s -u "$ANALYTICS_USER:$ANALYTICS_PASSWORD" https://devapis.cloud/api/analytics | grep -o "total_visits" || echo "failed")

if [ "$ANALYTICS_RESPONSE" = "total_visits" ]; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
fi

# Test 4: el mismo endpoint SIN credenciales debe rechazar
echo -n "   Probando /api/analytics (sin credenciales, debe dar 401)... "
UNAUTH_CODE=$(curl -s -o /dev/null -w '%{http_code}' https://devapis.cloud/api/analytics)

if [ "$UNAUTH_CODE" = "401" ]; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌ devolvió $UNAUTH_CODE — ¡las estadísticas están expuestas!${NC}"
fi

echo ""

# ============================================
# 7. Mostrar información útil
# ============================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 ¡Despliegue completado exitosamente!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 URLs disponibles:"
echo "   • CV: https://devapis.cloud/cv"
echo "   • Dashboard: https://devapis.cloud/analytics  (requiere login)"
echo "   • API: https://devapis.cloud/api/analytics    (requiere login)"
echo "   • Health: https://devapis.cloud/health"
echo ""
echo "🔍 Comandos útiles:"
echo "   • Ver logs: docker compose logs -f analytics-api"
echo "   • Reiniciar: docker compose restart analytics-api"
echo "   • Ver stats: docker exec -i ${DB_HOST} psql -U ${DB_USER} -d ${DB_NAME} -c 'SELECT * FROM cv_analytics_summary;'"
echo ""
echo "📝 Próximos pasos:"
echo "   1. Visita tu CV: https://devapis.cloud/cv"
echo "   2. Abre el dashboard: https://devapis.cloud/analytics"
echo "   3. Si vienes de una versión anterior, purga las IPs históricas:"
echo "      cat database/migrate-anonymize-ips.sql | docker exec -i ${DB_HOST} psql -U ${DB_USER} -d ${DB_NAME}"
echo ""

# Mostrar visitas actuales
TOTAL_VISITS=$($PSQL -tAc "SELECT COUNT(*) FROM cv_visits" 2>/dev/null || echo "0")
echo -e "${GREEN}📊 Visitas registradas hasta ahora: $TOTAL_VISITS${NC}"
echo ""
