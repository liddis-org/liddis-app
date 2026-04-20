# syntax=docker/dockerfile:1
# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.11/site-packages"

WORKDIR /app

# Apenas libpq runtime (sem gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copia pacotes instalados do builder
COPY --from=builder /install /install

# Copia o projeto
COPY . .

# Coleta arquivos estáticos (usa SECRET_KEY padrão — sem acesso ao banco)
RUN python manage.py collectstatic --noinput

# Usuário sem privilégios para segurança
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD exec gunicorn config.wsgi:application \
    --workers 2 \
    --threads 2 \
    --timeout 60 \
    --bind "0.0.0.0:${PORT}"
