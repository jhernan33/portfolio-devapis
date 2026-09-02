#!/bin/bash

# ============================================
# Script para actualizar en producción
# ============================================
# Sube los cambios al servidor y reinicia servicios

set -e  # Exit on error

echo "🚀 Actualizando servicios en producción..."
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Reconstruir LAS DOS imágenes. `docker compose up` no reconstruye una
#    imagen que ya existe, así que un cambio en un Dockerfile o en nginx.conf
#    no llegaría a producción. Con el paso a nginx-unprivileged eso sería
#    fatal: el compose envía el tráfico al 8080 y un Nginx antiguo sigue en
#    el 80, con lo que el CV dejaría de responder.
echo "📦 Reconstruyendo las imágenes (cv y analytics-api)..."
docker compose build

# 2. Recrear ambos servicios para aplicar cambios de red
echo "🔄 Recreando servicios con nueva configuración..."
docker compose up -d --force-recreate

# 3. Esperar a que estén healthy
echo "⏳ Esperando que los servicios estén healthy..."
sleep 10

# 4. Verificar estado
echo ""
echo "📊 Estado de los servicios:"
docker compose ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Actualización completada${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 URLs actualizadas:"
echo "   • CV: https://devapis.cloud/cv"
echo "   • Analytics Dashboard: https://devapis.cloud/analytics  (requiere login)"
echo "   • Analytics API: https://devapis.cloud/api/analytics    (requiere login)"
echo ""
echo "🔍 Verificar:"
echo "   curl https://devapis.cloud/cv"
echo "   curl https://devapis.cloud/health"
echo "   curl -X POST https://devapis.cloud/api/track"
echo "   curl -u \"\$ANALYTICS_USER:\$ANALYTICS_PASSWORD\" https://devapis.cloud/api/analytics"
echo ""
echo "⚠️  Comprueba que las estadísticas siguen protegidas:"
echo "   curl -o /dev/null -w '%{http_code}\\n' https://devapis.cloud/api/analytics   # debe dar 401"
echo ""
