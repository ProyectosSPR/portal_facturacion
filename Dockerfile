# Dockerfile para Portal de Facturación Flask
FROM python:3.10-slim

# Metadata
LABEL maintainer="dml"
LABEL description="Portal de Facturación - Flask + n8n"

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 appuser

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copiar el resto de la aplicación
COPY . .

# Crear directorio de uploads y dar permisos
RUN mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Exponer puerto
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Comando por defecto (puede ser sobrescrito por docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
