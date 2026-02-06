#!/bin/sh
set -e

# Wait for DB -> avoid backend fail to start due to database not ready
echo "Waiting for database to be ready..."
while ! python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('db', 5432))" 2>/dev/null; do
    echo "Waiting for db:5432..."
    sleep 2
done
echo "Database is ready!"

alembic upgrade head
python script/seed_initial_data.py
python app/script/ingest_knowledge.py
python app/script/ingest_logs.py
python app/script/ingest_code_file.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
