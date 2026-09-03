# syntax=docker/dockerfile:1

FROM node:22-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /build/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOST=0.0.0.0 \
    PORT=7860 \
    UPLOAD_DIR=/app/uploads \
    VECTOR_STORE_DIR=/app/vector_store

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 user \
    && mkdir -p /app/uploads /app/vector_store \
    && chown -R 1000:1000 /app

COPY --from=python-builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=1000:1000 backend/app ./app
COPY --from=frontend-builder --chown=1000:1000 /build/frontend/dist ./static

USER 1000
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '7860')}/health\", timeout=4)"]

CMD ["python", "-m", "app"]
