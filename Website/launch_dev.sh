#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SESSION_COOKIE_SECURE="0"
export INSTANCE_TLS_MODE="development"
export INSTANCE_PARENT_DOMAIN="${INSTANCE_PARENT_DOMAIN:-meine-domain}"

echo "Launching DEVELOPMENT stack"
echo "  SESSION_COOKIE_SECURE=$SESSION_COOKIE_SECURE"
echo "  INSTANCE_TLS_MODE=$INSTANCE_TLS_MODE"
echo "  INSTANCE_PARENT_DOMAIN=$INSTANCE_PARENT_DOMAIN"

docker compose build website
docker compose up -d

if [[ -x "$SCRIPT_DIR/sync_dev_hosts.sh" ]]; then
	"$SCRIPT_DIR/sync_dev_hosts.sh" || true
fi

echo "Development stack is running on http://localhost:4999"
echo "Provisioning creates self-signed certs per subdomain when needed."
