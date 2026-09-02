-- 0002 · Las marcas de tiempo pasan a TIMESTAMPTZ.
--
-- Por qué: las columnas eran TIMESTAMP sin zona. La aplicación insertaba UTC,
-- pero `NOW()` y `CURRENT_DATE` los resolvía PostgreSQL con la zona de SU
-- servidor. Si ese contenedor no está en UTC —y nada garantizaba que lo
-- estuviera— los cortes de "hoy" y "últimas 24 horas" salían desplazados sin
-- que nada fallara: los números seguían apareciendo, solo que mal.
--
-- `AT TIME ZONE 'UTC'` interpreta lo ya guardado como UTC, que es lo que era.

-- La vista depende de estas columnas y PostgreSQL no deja cambiarles el tipo
-- mientras exista. Se recrea abajo.
DROP VIEW IF EXISTS cv_analytics_summary;

ALTER TABLE cv_visits
    ALTER COLUMN visited_at TYPE TIMESTAMPTZ USING visited_at AT TIME ZONE 'UTC',
    ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

ALTER TABLE cv_visits ALTER COLUMN visited_at SET DEFAULT NOW();
ALTER TABLE cv_visits ALTER COLUMN created_at SET DEFAULT NOW();

-- La vista vuelve, pero sin `visits_today`.
--
-- Esa columna era la única que dependía de una zona horaria, y "hoy" ya no se
-- puede definir aquí sin duplicar una decisión que ahora vive en un solo sitio:
-- ANALYTICS_DISPLAY_TZ, que la API aplica en sus consultas. Una vista que
-- responde "hoy" en UTC mientras el panel responde "hoy" en Caracas no es una
-- comodidad, es una discrepancia esperando a confundir a alguien.
--
-- Las ventanas móviles que quedan (24 h, 7 días, 30 días) no dependen de la
-- zona: son intervalos, no días del calendario.
CREATE OR REPLACE VIEW cv_analytics_summary AS
SELECT
    COUNT(*) AS total_visits,
    COUNT(DISTINCT ip_hash) AS unique_visitors,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '1 day') AS visits_last_24h,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '7 days') AS visits_last_7d,
    COUNT(*) FILTER (WHERE visited_at > NOW() - INTERVAL '30 days') AS visits_last_30d
FROM cv_visits
WHERE NOT is_internal;
