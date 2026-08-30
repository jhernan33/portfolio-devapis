-- ============================================
-- BASE DE DATOS Y ROL DEDICADOS PARA ANALYTICS
-- ============================================
--
-- Por defecto el servicio se conecta como el superusuario `postgres` a la
-- base `postgres`. Eso significa que una vulnerabilidad en la API de
-- analytics compromete todo el clúster.
--
-- Este script crea una base y un rol con los permisos mínimos. Es un paso
-- de infraestructura opcional pero recomendado.
--
-- Uso (sustituye la contraseña antes de ejecutar):
--     docker exec -i postgres17 psql -U postgres -d postgres \
--       -v analytics_password="'UNA_PASSWORD_LARGA_Y_ALEATORIA'" \
--       -f - < database/create-analytics-role.sql
--
-- Después, en .env:
--     DB_NAME=cv_analytics
--     DB_USER=cv_analytics
--     DB_PASSWORD=UNA_PASSWORD_LARGA_Y_ALEATORIA
--
-- Y vuelve a ejecutar database/init-analytics.sql contra la base nueva.

-- 1. Rol sin privilegios de superusuario ni de creación.
CREATE ROLE cv_analytics WITH LOGIN PASSWORD :analytics_password
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

-- 2. Base de datos propia, aislada del resto del clúster.
CREATE DATABASE cv_analytics OWNER cv_analytics;

-- 3. Revocar el acceso público por defecto.
REVOKE ALL ON DATABASE cv_analytics FROM PUBLIC;
GRANT CONNECT ON DATABASE cv_analytics TO cv_analytics;
