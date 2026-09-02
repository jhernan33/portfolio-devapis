# Dockerfile para Landing Page estática (CV)
# Proyecto: landPage
# Descripción: Sirve contenido HTML/CSS/JS estático con Nginx

# Variante sin privilegios: el proceso maestro corre como el usuario `nginx`
# (uid 101) y no como root, así que escucha en 8080, que no requiere
# CAP_NET_BIND_SERVICE. Traefik habla con el contenedor por el puerto que
# declara la etiqueta loadbalancer.server.port; el visitante no lo ve.
FROM nginxinc/nginx-unprivileged:1.31-alpine

# Metadatos
LABEL org.opencontainers.image.authors="Jose Hernan Varela"
LABEL org.opencontainers.image.source="https://github.com/jhernan33/portfolio-devapis"
LABEL description="Landing page - CV profesional"
LABEL version="1.0"

# Variables de ambiente
ENV NGINX_HOST=localhost
ENV NGINX_PORT=8080

# Copiar contenido estático
COPY src/ /usr/share/nginx/html/

# Copiar configuración de Nginx. El snippet de cabeceras va aparte porque
# nginx.conf lo incluye en el server y en cada location (ver ese fichero).
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-security-headers.conf /etc/nginx/snippets/security-headers.conf

# Exponer puerto
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

# No es necesario especificar CMD (heredado de nginx:1.27-alpine)
# CMD ["nginx", "-g", "daemon off;"]