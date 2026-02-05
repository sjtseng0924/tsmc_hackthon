#!/bin/sh
set -e

alembic upgrade head
python app/script/ingest_knowledge.py
python app/script/ingest_logs.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
