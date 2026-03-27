#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed."
  exit 1
fi

DOCKER_CMD=(docker)

if ! docker info >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
    DOCKER_CMD=(sudo docker)
    echo "==> Docker daemon requires elevated permissions; using sudo docker"
  else
    echo "Error: cannot access Docker daemon (/var/run/docker.sock)."
    echo ""
    echo "Fix options:"
    echo "  1) Run once with sudo: sudo ./start_docker_build.sh"
    echo "  2) Permanent fix (recommended):"
    echo "     sudo usermod -aG docker $USER"
    echo "     newgrp docker"
    echo "     # or logout/login"
    exit 1
  fi
fi

if ! "${DOCKER_CMD[@]}" compose version >/dev/null 2>&1; then
  echo "Error: docker compose plugin is not available."
  exit 1
fi

NUITKA_JOBS="${NUITKA_JOBS:-1}"
NUITKA_LOW_MEMORY="${NUITKA_LOW_MEMORY:-1}"

echo "==> Safe Nuitka build settings"
echo "    NUITKA_JOBS=${NUITKA_JOBS}"
echo "    NUITKA_LOW_MEMORY=${NUITKA_LOW_MEMORY}"

echo "==> Building website image (Nuitka standalone conversion runs in Dockerfile)"
NUITKA_JOBS="$NUITKA_JOBS" NUITKA_LOW_MEMORY="$NUITKA_LOW_MEMORY" "${DOCKER_CMD[@]}" compose build website

echo "==> Starting internal MongoDB + Website containers"
"${DOCKER_CMD[@]}" compose up -d

echo "==> Container status"
"${DOCKER_CMD[@]}" compose ps

echo "Application is starting on: http://localhost:4999"
echo "Use: docker compose logs -f website"
echo "Tip: If build is still too heavy, run with NUITKA_JOBS=1 NUITKA_LOW_MEMORY=1 ./start_docker_build.sh"
