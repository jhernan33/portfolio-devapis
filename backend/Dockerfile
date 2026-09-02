# Backend Analytics - Dockerfile
# FastAPI + uvicorn para tracking de visitas

FROM python:3.12-slim

LABEL org.opencontainers.image.authors="Jose Hernan Varela"
LABEL org.opencontainers.image.source="https://github.com/jhernan33/portfolio-devapis"
LABEL description="CV Analytics API - FastAPI"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuario de sistema sin shell ni home. El servicio acepta escrituras públicas
# en /api/track: si algo escapa del proceso, que no sea root. Se crea antes de
# copiar nada para que la capa no cambie con cada edición del código.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
#
# La migración va en la imagen a propósito: se ejecuta con
# `docker compose exec analytics-api python /app/migrar_user_agents.py`, y
# tenerla dentro evita el `docker cp` a mano justo cuando hay que tocar datos
# de producción. No se ejecuta sola: es un script, no parte del arranque.
COPY main.py migrar_user_agents.py ./
COPY app/ ./app/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Exponer puerto
EXPOSE 8000

# A partir de aquí todo corre como `app`. El código se copió como root y es
# solo lectura para este usuario: el servicio no escribe en disco
# (PYTHONDONTWRITEBYTECODE evita incluso los .pyc), y el compose monta el
# sistema de ficheros como read_only.
USER app

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
