#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SESSION_COOKIE_SECURE="0"
export INSTANCE_TLS_MODE="development"
export INSTANCE_PARENT_DOMAIN="${INSTANCE_PARENT_DOMAIN:-meine-domain}"
export DEV_HOSTS_REFRESH_INTERVAL="${DEV_HOSTS_REFRESH_INTERVAL:-30}"

echo "Launching DEVELOPMENT stack"
echo "  SESSION_COOKIE_SECURE=$SESSION_COOKIE_SECURE"
echo "  INSTANCE_TLS_MODE=$INSTANCE_TLS_MODE"
echo "  INSTANCE_PARENT_DOMAIN=$INSTANCE_PARENT_DOMAIN"
echo "  DEV_HOSTS_REFRESH_INTERVAL=$DEV_HOSTS_REFRESH_INTERVAL"

docker compose build website
docker compose up -d

NGINX_SCRIPT="$SCRIPT_DIR/../nginx.sh"
if [[ -x "$NGINX_SCRIPT" ]]; then
	echo "Aktualisiere Nginx Reverse Proxy..."
	sudo "$NGINX_SCRIPT" apply || echo "Warnung: Nginx konnte nicht automatisch aktualisiert werden."
fi

if [[ -x "$SCRIPT_DIR/sync_dev_hosts.sh" ]]; then
	"$SCRIPT_DIR/sync_dev_hosts.sh" || true
	if [[ "${DEV_HOSTS_REFRESH_INTERVAL}" != "0" ]]; then
		nohup bash -lc "while true; do '$SCRIPT_DIR/sync_dev_hosts.sh' >/dev/null 2>&1 || true; sleep '$DEV_HOSTS_REFRESH_INTERVAL'; done" \
			>"$SCRIPT_DIR/dev-hosts-sync.log" 2>&1 &
		echo "  Dev-Hosts-Sync läuft im Hintergrund (Log: $SCRIPT_DIR/dev-hosts-sync.log)"
	fi
fi

echo "Development stack is running on http://localhost:4999"
echo "Provisioning creates self-signed certs per subdomain when needed."