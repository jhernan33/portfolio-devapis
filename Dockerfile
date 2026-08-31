# Dockerfile para Landing Page estática (CV)
# Proyecto: landPage
# Descripción: Sirve contenido HTML/CSS/JS estático con Nginx

FROM nginx:1.27-alpine

# Metadatos
LABEL org.opencontainers.image.authors="Jose Hernan Varela"
LABEL org.opencontainers.image.source="https://github.com/jhernan33/portfolio-devapis"
LABEL description="Landing page - CV profesional"
LABEL version="1.0"

# Variables de ambiente
ENV NGINX_HOST=localhost
ENV NGINX_PORT=80

# Copiar contenido estático
COPY src/ /usr/share/nginx/html/

# Copiar configuración de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# No es necesario especificar CMD (heredado de nginx:1.27-alpine)
# CMD ["nginx", "-g", "daemon off;"]