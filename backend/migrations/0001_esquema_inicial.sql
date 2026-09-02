-- 0001 · Esquema inicial de cv_visits.
--
-- Es el DDL que hasta ahora se ejecutaba en cada arranque. Se conserva tal
-- cual, con sus reparaciones idempotentes para instalaciones anteriores, para
-- que aplicarlo sobre la base de producción no cambie nada: la numeración
-- cuenta la historia real del esquema, no la que nos habría gustado tener.
-- Tabla de visitas (sin IPs en claro)
CREATE TABLE IF NOT EXISTS cv_visits (
    id SERIAL PRIMARY KEY,
    ip_prefix VARCHAR(45),
    ip_hash CHAR(64),
    user_agent TEXT,
    browser VARCHAR(100),
    os VARCHAR(100),
    device_type VARCHAR(20),
    referer TEXT,
    language VARCHAR(50),
    -- Tráfico propio: red interna, health checks y el servidor llamándose a
    -- sí mismo. Se guarda igualmente, porque sirve para diagnosticar, pero
    -- queda fuera de las estadísticas.
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    visited_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Migración para instalaciones anteriores que aún tienen ip_address
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_prefix VARCHAR(45);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_hash CHAR(64);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS is_internal BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE cv_visits ALTER COLUMN ip_address DROP NOT NULL;
    END IF;
END $$;

-- Índices
DROP INDEX IF EXISTS idx_cv_visits_ip;
CREATE INDEX IF NOT EXISTS idx_cv_visits_ip_hash ON cv_visits(ip_hash);
CREATE INDEX IF NOT EXISTS idx_cv_visits_visited_at ON cv_visits(visited_at DESC);
CREATE INDEX IF NOT EXISTS idx_cv_visits_device ON cv_visits(device_type);
CREATE INDEX IF NOT EXISTS idx_cv_visits_browser ON cv_visits(browser);

-- Índice parcial: todas las consultas de estadísticas filtran por
-- `NOT is_internal`, así que el índice solo cubre esas filas.
CREATE INDEX IF NOT EXISTS idx_cv_visits_externas
    ON cv_visits(visited_at DESC) WHERE NOT is_internal;

-- Vista para analytics rápidos.
-- Se recrea sobre ip_hash para eliminar la dependencia con ip_address y
-- permitir que la columna antigua pueda purgarse.
--
-- Excluye el tráfico interno. En la primera medición con tráfico real, de 23
-- visitas registradas 16 eran navegación propia o comprobaciones lanzadas
-- desde el propio servidor: el 70%. Contarlas convierte la única métrica que
-- el CV usa para medirse en ruido.
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_hash) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') as visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d,
    COUNT(*) FILTER (WHERE visited_at::date = CURRENT_DATE) as visits_today
FROM cv_visits
WHERE NOT is_internal;
