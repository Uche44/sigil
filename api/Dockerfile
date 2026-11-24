FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SIGIL_PACKS_DIR=/app/packs \
    SIGIL_DB_PATH=/data/sigil.db \
    SIGIL_UPLOADS_DIR=/data/uploads

WORKDIR /app

COPY api/pyproject.toml ./
COPY api/sigil ./sigil
RUN pip install --no-cache-dir .

COPY packs ./packs
RUN mkdir -p /data/uploads

EXPOSE 8000

CMD ["sh", "-c", "uvicorn sigil.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
