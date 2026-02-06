#!/usr/bin/env bash
set -euo pipefail

IMG="us-central1-docker.pkg.dev/tsmccareerhack2026-icsple-grp3/tsmccareerhack2026-icsple-grp3-repository/backend:latest"
NAME="backend"

sudo docker pull "$IMG"

sudo docker rm -f "$NAME" >/dev/null 2>&1 || true

# 直接跑新的
sudo docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  -p 8000:8000 \
  "$IMG"

sudo docker ps --filter "name=$NAME"
