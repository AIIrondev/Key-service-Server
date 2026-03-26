#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose plugin is not available."
  exit 1
fi

NUITKA_JOBS="${NUITKA_JOBS:-1}"
NUITKA_LOW_MEMORY="${NUITKA_LOW_MEMORY:-1}"

echo "==> Safe Nuitka build settings"
echo "    NUITKA_JOBS=${NUITKA_JOBS}"
echo "    NUITKA_LOW_MEMORY=${NUITKA_LOW_MEMORY}"

echo "==> Building website image (Nuitka standalone conversion runs in Dockerfile)"
NUITKA_JOBS="$NUITKA_JOBS" NUITKA_LOW_MEMORY="$NUITKA_LOW_MEMORY" docker compose build website

echo "==> Starting internal MongoDB + Website containers"
docker compose up -d

echo "==> Container status"
docker compose ps

echo "Application is starting on: http://localhost:4999"
echo "Use: docker compose logs -f website"
echo "Tip: If build is still too heavy, run with NUITKA_JOBS=1 NUITKA_LOW_MEMORY=1 ./start_docker_build.sh"
