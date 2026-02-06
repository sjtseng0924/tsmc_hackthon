#!/bin/sh
set -e

# Wait for DB -> avoid backend fail to start due to database not ready
echo "Waiting for database to be ready..."
DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
while ! python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('${DB_HOST}', ${DB_PORT}))" 2>/dev/null; do
    echo "Waiting for ${DB_HOST}:${DB_PORT}..."
    sleep 2
done
echo "Database is ready!"

alembic upgrade head
python app/script/ingest_knowledge.py
python app/script/ingest_logs.py
python app/script/ingest_code_file.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
