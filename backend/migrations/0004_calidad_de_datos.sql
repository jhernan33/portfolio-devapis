-- 0004 · Columnas para separar visitas de ruido.
--
-- Hasta aquí "visita" era cualquier POST a /api/track. Eso incluye:
--
--   * los rastreadores que ejecutan JavaScript, que son muchos y no leen nada;
--   * cada recarga y cada pestaña de la misma persona;
--   * y no distinguía el CV en español del inglés, así que no había forma de
--     saber si la versión traducida servía para algo.
--
-- Con siete visitas externas reales, una persona curiosa que recarga tres
-- veces movía la métrica un 40%. Estas cuatro columnas separan el ruido sin
-- borrar nada: las filas se siguen guardando y se siguen viendo en /recent.

-- Rastreadores. Se deduce del User-Agent al registrar.
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS is_bot BOOLEAN NOT NULL DEFAULT FALSE;

-- Recarga o segunda pestaña del mismo visitante en menos de media hora.
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS is_repeat BOOLEAN NOT NULL DEFAULT FALSE;

-- Qué versión del CV se ha visto. Conjunto cerrado de valores: lo manda el
-- navegador y no se guarda nunca en crudo.
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS page VARCHAR(20);

-- Huella del visitante: hash con sal de IP + User-Agent.
--
-- `ip_hash` seguía contando como un visitante a toda una oficina detrás de un
-- NAT, y como varios a quien tiene IP dinámica. Añadir el User-Agent no lo
-- arregla del todo —nada lo hace sin cookies, que aquí no se quieren— pero
-- separa a dos personas distintas de la misma red. `ip_hash` se conserva: es
-- lo único que tienen las filas antiguas y romper esa continuidad sería
-- perder el histórico de visitantes únicos.
ALTER TABLE cv_visits ADD COLUMN IF NOT EXISTS visitor_hash CHAR(64);

-- Lo consulta el INSERT de cada visita para decidir si es una recarga.
CREATE INDEX IF NOT EXISTS idx_cv_visits_visitor_reciente
    ON cv_visits(visitor_hash, visited_at DESC);

-- El índice parcial de estadísticas pasa a excluir también los rastreadores,
-- que es lo que hacen ahora todas las consultas agregadas.
DROP INDEX IF EXISTS idx_cv_visits_externas;
CREATE INDEX IF NOT EXISTS idx_cv_visits_reales
    ON cv_visits(visited_at DESC) WHERE NOT is_internal AND NOT is_bot;

-- La vista sigue el mismo criterio que la API: personas, no rastreadores, y
-- una visita por persona cada media hora.
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) FILTER (WHERE NOT is_repeat) AS total_visits,
    COUNT(DISTINCT COALESCE(visitor_hash, ip_hash)) AS unique_visitors,
    COUNT(*) FILTER (WHERE NOT is_repeat AND visited_at > NOW() - INTERVAL '1 day')
        AS visits_last_24h,
    COUNT(*) FILTER (WHERE NOT is_repeat AND visited_at > NOW() - INTERVAL '7 days')
        AS visits_last_7d,
    COUNT(*) FILTER (WHERE NOT is_repeat AND visited_at > NOW() - INTERVAL '30 days')
        AS visits_last_30d
FROM cv_visits
WHERE NOT is_internal AND NOT is_bot;
