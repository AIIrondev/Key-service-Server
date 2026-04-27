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

# Ensure required runtime files exist before building
if [ ! -f "$SCRIPT_DIR/gunicorn.conf.py" ]; then
	echo "[FEHLER] gunicorn.conf.py fehlt in $SCRIPT_DIR. Bitte prüfen." >&2
	exit 2
fi

docker compose build website
docker compose up -d

NGINX_SCRIPT="$SCRIPT_DIR/../nginx.sh"
if [[ -x "$NGINX_SCRIPT" ]]; then
	echo "Aktualisiere Nginx Reverse Proxy..."
	sudo "$NGINX_SCRIPT" apply || echo "Warnung: Nginx konnte nicht automatisch aktualisiert werden."
fi

# Wait for website to become healthy (simple HTTP check)
check_url="http://127.0.0.1:4999/"
timeout_seconds=60
interval=2
elapsed=0

echo "Warte auf Website (${check_url}) bis ${timeout_seconds}s..."
while [ $elapsed -lt $timeout_seconds ]; do
	if curl -sS --max-time 2 "$check_url" >/dev/null 2>&1; then
		echo "Website erreichbar nach ${elapsed}s"
		break
	fi
	sleep $interval
	elapsed=$((elapsed + interval))
done

if [ $elapsed -ge $timeout_seconds ]; then
	echo "[FEHLER] Website nicht erreichbar nach ${timeout_seconds}s. Sammle Diagnosedaten..."
	echo "--- docker compose ps ---"
	docker compose ps || true
	echo "--- docker logs website (tail 200) ---"
	docker logs --tail 200 website-website-1 || true
	echo "Bitte prüfe Container-Logs und nginx-Konfiguration."
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