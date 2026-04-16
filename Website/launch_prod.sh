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

NGINX_SCRIPT="$SCRIPT_DIR/../nginx.sh"
if [[ -x "$NGINX_SCRIPT" ]]; then
	echo "Aktualisiere Nginx Reverse Proxy..."
	sudo "$NGINX_SCRIPT" apply || echo "Warnung: Nginx konnte nicht automatisch aktualisiert werden."
fi

# Automatically sync hosts after container start
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/sync_dev_hosts.sh" ]]; then
	echo "Warte auf MongoDB-Verfügbarkeit..."
	sleep 5
	"$SCRIPT_DIR/sync_dev_hosts.sh" || true
	echo "Production Hosts werden synchronisiert (stündlich)"
	
	# Starte Background-Daemon für stündliche Sync
	if [[ "${PROD_HOSTS_REFRESH_INTERVAL}" != "0" ]]; then
		nohup bash -lc "while true; do '$SCRIPT_DIR/sync_dev_hosts.sh' >/dev/null 2>&1 || true; sleep ${PROD_HOSTS_REFRESH_INTERVAL:-3600}; done" \
			>"$SCRIPT_DIR/prod-hosts-sync.log" 2>&1 &
		echo "  Prod-Hosts-Sync läuft im Hintergrund (Log: $SCRIPT_DIR/prod-hosts-sync.log)"
	fi
fi

echo "Production stack is running on http://localhost:4999"
echo "Provisioning expects wildcard certificate for all subdomains."
