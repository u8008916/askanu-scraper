FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCRAPER_STORAGE_PATH=/data \
    SCRAPER_DRY_RUN=true

WORKDIR /app

RUN addgroup --system askanu \
    && adduser --system --ingroup askanu askanu

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && chown askanu:askanu /data

USER askanu

ENTRYPOINT ["askanu-scraper-job"]
