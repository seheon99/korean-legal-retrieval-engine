# Ingest service image — built once, code is bind-mounted at runtime.
FROM python:3.11-slim

WORKDIR /app

# psycopg[binary] bundles libpq, so no apt install of postgresql-client
# is needed. Keep the image lean.
COPY docker/ingest-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Source tree (src/ingest, data/raw) is bind-mounted by docker-compose
# at runtime — no COPY here. PYTHONPATH=/app/src is set in compose.

CMD ["python", "-m", "ingest", "--raw-dir", "data/raw"]
