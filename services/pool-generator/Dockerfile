FROM python:3.12-slim

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser

CMD ["celery", "-A", "src.main", "worker", "--beat", "--loglevel=info", "--concurrency=2", "-s", "/app/data/celerybeat-schedule"]
