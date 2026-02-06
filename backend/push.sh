#!/usr/bin/env bash
set -euo pipefail

IMG="us-central1-docker.pkg.dev/tsmccareerhack2026-icsple-grp3/tsmccareerhack2026-icsple-grp3-repository/backend"

docker buildx build \
  --platform linux/amd64 \
  -t $IMG:latest \
  --push .

set +e
gcloud artifacts docker images list $IMG \
--include-tags | grep latest
set -e
