#!/bin/bash
#
# Respaldo de la base de analytics.
#
# Por qué existe: hasta ahora no había ninguno documentado en el repositorio.
# La tabla `cv_visits` es el único dato del proyecto que no se puede regenerar
# —el resto es código— y vive en un contenedor de PostgreSQL que además
# pertenece a otro proyecto. Un `docker volume rm` distraído y no queda nada.
#
# Qué hace:
#   1. Vuelca solo la base de analytics, comprimida, con la fecha en el nombre.
#   2. Comprueba que el volcado contiene de verdad la tabla, en lugar de dar
#      por bueno un fichero de cero bytes. Un respaldo que no se verifica no es
#      un respaldo, es un fichero.
#   3. Borra los más antiguos que RESPALDO_RETENER_DIAS.
#
# Uso:
#   ./tools/respaldar-db.sh
#
# En cron, a diario a las 3:30 (el volcado tarda segundos con este volumen):
#   30 3 * * * cd /ruta/al/repo && ./tools/respaldar-db.sh >> ~/respaldos/cv.log 2>&1
#
# Restaurar:
#   gunzip -c cv-analytics-2026-09-02.sql.gz | docker exec -i "$DB_HOST" \
#       psql -U "$DB_USER" -d "$DB_NAME"

set -euo pipefail

cd "$(dirname "$0")/.."

DESTINO="${RESPALDO_DIR:-$HOME/respaldos/cv-analytics}"
RETENER_DIAS="${RESPALDO_RETENER_DIAS:-30}"

if [ ! -f .env ]; then
    echo "❌ No encuentro .env. Este script usa las mismas credenciales que el servicio." >&2
    exit 1
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

for variable in DB_HOST DB_NAME DB_USER DB_PASSWORD; do
    if [ -z "${!variable:-}" ]; then
        echo "❌ Falta $variable en .env" >&2
        exit 1
    fi
done

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_HOST"; then
    echo "❌ No hay ningún contenedor llamado '$DB_HOST' en marcha." >&2
    echo "   DB_HOST es el nombre del contenedor de PostgreSQL; compruébalo con:" >&2
    echo "   docker ps --format '{{.Names}}' | grep -i postgres" >&2
    exit 1
fi

mkdir -p "$DESTINO"
FICHERO="$DESTINO/cv-analytics-$(date +%Y-%m-%d_%H%M).sql.gz"

echo "📦 Volcando $DB_NAME desde el contenedor $DB_HOST..."
docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_HOST" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
    | gzip -9 > "$FICHERO"

# Verificación: que el volcado traiga la tabla y, si hay visitas, sus filas.
if ! gunzip -c "$FICHERO" | grep -q 'CREATE TABLE public.cv_visits'; then
    echo "❌ El volcado no contiene cv_visits. Se descarta." >&2
    rm -f "$FICHERO"
    exit 1
fi

TAMANO=$(du -h "$FICHERO" | cut -f1)
FILAS=$(gunzip -c "$FICHERO" | grep -c '^[0-9]\+\s' || true)
echo "✅ $FICHERO ($TAMANO, ~$FILAS filas de datos)"

BORRADOS=$(find "$DESTINO" -name 'cv-analytics-*.sql.gz' -mtime "+$RETENER_DIAS" -print -delete | wc -l)
if [ "$BORRADOS" -gt 0 ]; then
    echo "🧹 $BORRADOS respaldos de más de $RETENER_DIAS días eliminados"
fi

echo "📚 Respaldos disponibles: $(find "$DESTINO" -name 'cv-analytics-*.sql.gz' | wc -l)"
