FROM node:20.18.1-bookworm-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci --no-audit --no-fund

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src

RUN npm test
RUN npm run build


FROM python:3.11.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd \
    --create-home \
    --uid 1000 \
    appuser

WORKDIR /home/appuser/app

COPY requirements.txt ./

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY --chown=appuser:appuser . .

COPY \
    --from=frontend-build \
    --chown=appuser:appuser \
    /frontend/dist \
    ./app/static

RUN mkdir -p \
        data/runtime \
        data/chroma \
        data/eval_runtime \
    && chown -R \
        appuser:appuser \
        /home/appuser/app

USER appuser

EXPOSE 7860

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=30s \
    --retries=3 \
    CMD curl --fail \
        http://127.0.0.1:7860/api/health/live \
        || exit 1

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]