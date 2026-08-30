-- ============================================
-- MIGRACIÓN: purgar las IPs en claro
-- ============================================
--
-- ⚠️  ESTE SCRIPT ES IRREVERSIBLE. HAZ UNA COPIA DE SEGURIDAD ANTES:
--
--     set -a; . ./.env; set +a
--     docker exec "$DB_HOST" pg_dump -U "$DB_USER" -d "$DB_NAME" -t cv_visits \
--       > cv_visits_backup_$(date +%F).sql
--
-- Contexto:
--   El backend ya no escribe IPs en claro. Al arrancar, rellena
--   automáticamente ip_prefix e ip_hash de las filas antiguas a partir de
--   la columna ip_address. Ese paso NO es destructivo.
--
--   Este script ejecuta el paso final: eliminar la columna ip_address con
--   los datos personales históricos. Ejecútalo solo DESPUÉS de haber
--   desplegado el backend nuevo y comprobado que las filas antiguas ya
--   tienen ip_hash relleno.
--
-- Uso:
--     cat database/migrate-anonymize-ips.sql | \
--       docker exec -i "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME"
--
--   Debe ejecutarse contra la MISMA base que usa el servicio (la de .env).

BEGIN;

-- 1. Comprobación previa: no debe quedar ninguna fila sin anonimizar.
DO $$
DECLARE
    pending INTEGER;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
    ) THEN
        RAISE NOTICE 'La columna ip_address ya no existe. Nada que purgar.';
        RETURN;
    END IF;

    SELECT COUNT(*) INTO pending
    FROM cv_visits
    WHERE ip_address IS NOT NULL AND ip_hash IS NULL;

    IF pending > 0 THEN
        RAISE EXCEPTION
            'Hay % filas con ip_address pero sin ip_hash. Arranca primero el backend nuevo para que las anonimice.',
            pending;
    END IF;
END $$;

-- 2. La vista depende de la tabla: se recrea sin referencias a ip_address.
DROP VIEW IF EXISTS cv_analytics_summary;

-- 3. Eliminar la columna con las IPs en claro.
ALTER TABLE cv_visits DROP COLUMN IF EXISTS ip_address;

-- 4. Recrear la vista sobre ip_hash.
CREATE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_hash) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') as visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d,
    COUNT(*) FILTER (WHERE visited_at::date = CURRENT_DATE) as visits_today
FROM cv_visits;

COMMIT;
