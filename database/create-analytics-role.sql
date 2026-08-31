-- ============================================
-- ROL DEDICADO PARA ANALYTICS
-- ============================================
--
-- Por defecto el servicio se conectaría como el superusuario `postgres`, de
-- modo que una vulnerabilidad en la API de analytics comprometería todo el
-- clúster: el resto de bases, `CREATE DATABASE`, `CREATE ROLE`.
--
-- Este script deja al servicio con un rol propio que solo alcanza su base.
-- Es idempotente: puede ejecutarse sobre una base recién creada o sobre una
-- que ya exista.
--
-- Uso (sustituye los dos valores antes de ejecutar):
--
--     docker exec -i <contenedor-postgres> psql -U postgres -d postgres \
--       -v analytics_password="'UNA_PASSWORD_LARGA_Y_ALEATORIA'" \
--       -v dbname=db_cv_analytics \
--       -f - < database/create-analytics-role.sql
--
-- Después, en .env:
--     DB_NAME=db_cv_analytics
--     DB_USER=cv_analytics
--     DB_PASSWORD=UNA_PASSWORD_LARGA_Y_ALEATORIA
--
-- Y ejecuta database/init-analytics.sql contra esa base, ya como cv_analytics.

-- ------------------------------------------------------------------
-- 1. Rol sin privilegios de superusuario ni de creación.
--    Si ya existe, solo se actualiza la contraseña.
-- ------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cv_analytics') THEN
        RAISE NOTICE 'El rol cv_analytics ya existe; actualizo su contraseña.';
    ELSE
        CREATE ROLE cv_analytics WITH LOGIN
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
        RAISE NOTICE 'Rol cv_analytics creado.';
    END IF;
END
$$;

ALTER ROLE cv_analytics WITH PASSWORD :analytics_password;

-- ------------------------------------------------------------------
-- 2. Base de datos propia. `CREATE DATABASE` no admite IF NOT EXISTS ni
--    puede ir dentro de un bloque DO, así que se genera con \gexec: la
--    consulta no devuelve filas cuando la base ya existe, y entonces no
--    se ejecuta nada.
-- ------------------------------------------------------------------
SELECT format('CREATE DATABASE %I OWNER cv_analytics', :'dbname')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'dbname'
)
\gexec

-- Si la base ya existía (creada a mano, o por un despliegue anterior),
-- traspasarla al rol. En PostgreSQL 15+ el esquema `public` pertenece a
-- `pg_database_owner`, de modo que ser dueño de la base es lo que permite
-- a cv_analytics crear sus tablas sin más concesiones.
ALTER DATABASE :"dbname" OWNER TO cv_analytics;

-- ------------------------------------------------------------------
-- 3. Revocar el acceso público por defecto.
-- ------------------------------------------------------------------
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO cv_analytics;

\echo 'Listo. Verifica con: \\du cv_analytics'
