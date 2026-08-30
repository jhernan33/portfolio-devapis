-- ============================================
-- CV ANALYTICS DATABASE SCHEMA
-- ============================================
-- Script para crear la tabla de tracking de visitas.
-- Compatible con PostgreSQL 13+
--
-- IMPORTANTE: este archivo debe mantenerse sincronizado con el DDL de
-- backend/main.py (constante DDL_SCRIPT), que se ejecuta al arrancar.
--
-- PRIVACIDAD: no se almacenan direcciones IP en claro. Se guardan:
--   - ip_prefix: la red truncada (/24 en IPv4, /48 en IPv6)
--   - ip_hash:   SHA-256 de la IP con una sal secreta (ANALYTICS_IP_SALT)
-- Esto permite estadísticas y conteo de únicos sin reidentificar personas.

-- Tabla de visitas
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
    visited_at TIMESTAMP DEFAULT NOW(),

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Migración para instalaciones anteriores que aún tienen ip_address
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_prefix VARCHAR(45);
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS ip_hash CHAR(64);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cv_visits' AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE cv_visits ALTER COLUMN ip_address DROP NOT NULL;
    END IF;
END $$;

-- Índices para mejorar performance de queries
DROP INDEX IF EXISTS idx_cv_visits_ip;
CREATE INDEX IF NOT EXISTS idx_cv_visits_ip_hash ON cv_visits(ip_hash);
CREATE INDEX IF NOT EXISTS idx_cv_visits_visited_at ON cv_visits(visited_at DESC);
CREATE INDEX IF NOT EXISTS idx_cv_visits_device ON cv_visits(device_type);
CREATE INDEX IF NOT EXISTS idx_cv_visits_browser ON cv_visits(browser);

-- Vista para analytics rápidos
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) as total_visits,
    COUNT(DISTINCT ip_hash) as unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') as visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') as visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') as visits_last_30d,
    COUNT(*) FILTER (WHERE visited_at::date = CURRENT_DATE) as visits_today
FROM cv_visits;

-- Comentarios para documentación
COMMENT ON TABLE cv_visits IS 'Registro de visitas al CV (sin datos personales identificables)';
COMMENT ON COLUMN cv_visits.ip_prefix IS 'Red de origen truncada (/24 IPv4, /48 IPv6). Nunca la IP completa';
COMMENT ON COLUMN cv_visits.ip_hash IS 'SHA-256 de la IP con sal secreta, solo para contar visitantes únicos';
COMMENT ON COLUMN cv_visits.user_agent IS 'User-Agent completo del navegador';
COMMENT ON COLUMN cv_visits.browser IS 'Navegador detectado (Chrome, Firefox, etc)';
COMMENT ON COLUMN cv_visits.os IS 'Sistema operativo detectado (Windows, Linux, etc)';
COMMENT ON COLUMN cv_visits.device_type IS 'Tipo de dispositivo (Mobile/Desktop)';
COMMENT ON COLUMN cv_visits.referer IS 'URL de origen de la visita';
COMMENT ON COLUMN cv_visits.language IS 'Idioma preferido del navegador';
COMMENT ON COLUMN cv_visits.visited_at IS 'Timestamp UTC de la visita';

-- Query de ejemplo para ver visitas recientes
-- SELECT * FROM cv_visits ORDER BY visited_at DESC LIMIT 10;

-- Query de ejemplo para ver resumen
-- SELECT * FROM cv_analytics_summary;

-- Query de ejemplo para top redes de origen
-- SELECT ip_prefix, COUNT(*) as visits FROM cv_visits GROUP BY ip_prefix ORDER BY visits DESC LIMIT 10;
