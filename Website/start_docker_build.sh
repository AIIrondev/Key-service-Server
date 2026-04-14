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

echo "==> Building website image (pure Python runtime)"
"${DOCKER_CMD[@]}" compose build website

echo "==> Starting internal MongoDB + Website containers"
"${DOCKER_CMD[@]}" compose up -d

echo "==> Container status"
"${DOCKER_CMD[@]}" compose ps

echo "Application is starting on: http://localhost:4999"
echo "Use: docker compose logs -f website"
echo "Provisioning is available in the container via /app/provision_instance.sh"
