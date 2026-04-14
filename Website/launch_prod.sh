#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SESSION_COOKIE_SECURE="1"
export INSTANCE_TLS_MODE="production"
export INSTANCE_PARENT_DOMAIN="${INSTANCE_PARENT_DOMAIN:-meine-domain}"
export INSTANCE_WILDCARD_CERT_FILE="${INSTANCE_WILDCARD_CERT_FILE:-/etc/nginx/certs/wildcard.meine-domain.crt}"
export INSTANCE_WILDCARD_KEY_FILE="${INSTANCE_WILDCARD_KEY_FILE:-/etc/nginx/certs/wildcard.meine-domain.key}"

if [[ ! -f "$INSTANCE_WILDCARD_CERT_FILE" || ! -f "$INSTANCE_WILDCARD_KEY_FILE" ]]; then
  echo "Error: Wildcard certificate missing for production mode"
  echo "  CERT: $INSTANCE_WILDCARD_CERT_FILE"
  echo "  KEY:  $INSTANCE_WILDCARD_KEY_FILE"
  exit 1
fi

echo "Launching PRODUCTION stack"
echo "  SESSION_COOKIE_SECURE=$SESSION_COOKIE_SECURE"
echo "  INSTANCE_TLS_MODE=$INSTANCE_TLS_MODE"
echo "  INSTANCE_PARENT_DOMAIN=$INSTANCE_PARENT_DOMAIN"
echo "  INSTANCE_WILDCARD_CERT_FILE=$INSTANCE_WILDCARD_CERT_FILE"
echo "  INSTANCE_WILDCARD_KEY_FILE=$INSTANCE_WILDCARD_KEY_FILE"

docker compose build website
docker compose up -d

echo "Production stack is running on http://localhost:4999"
echo "Provisioning expects wildcard certificate for all subdomains."
