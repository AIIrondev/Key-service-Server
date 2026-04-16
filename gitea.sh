#!/usr/bin/env bash
set -euo pipefail

# Konfiguration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITEA_DIR="/opt/gitea-server"
WEBSITE_DIR="$SCRIPT_DIR/Website"
GITEA_DOMAIN="update.meine-domain"
GITEA_HTTP_PORT=3001
GITEA_SSH_PORT=2222
GITEA_BIND_IP="127.0.0.1"
WEBSITE_DOMAIN="meine-domain"
WEBSITE_UPSTREAM_PORT=4999
RUNTIME_ENV_FILE="$GITEA_DIR/runtime.env"
ACTION="${1:-start}"

usage() {
  echo "Nutzung: $0 [start|stop|restart|status]"
}

current_host_info() {
  local host_name
  local host_ip
  host_name="$(hostname)"
  host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"

  if [ -z "$host_ip" ]; then
    host_ip="unbekannt"
  fi

  echo "$host_name ($host_ip)"
}

write_gitea_compose() {
  local gitea_http_port="$1"

  echo "Erstelle docker-compose.yml fuer Gitea..."
  cat <<EOF > "$GITEA_DIR/docker-compose.yml"
networks:
  gitea:
    external: false

services:
  server:
    image: gitea/gitea:1.21
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - GITEA__database__DB_TYPE=sqlite3
      - GITEA__server__DOMAIN=$GITEA_DOMAIN
      - GITEA__server__SSH_DOMAIN=$GITEA_DOMAIN
      - GITEA__server__HTTP_PORT=3001
      - GITEA__server__ROOT_URL=https://$GITEA_DOMAIN
      - GITEA__server__SSH_PORT=$GITEA_SSH_PORT
    restart: always
    networks:
      - gitea
    volumes:
      - ./data:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "$GITEA_BIND_IP:$gitea_http_port:3001"
      - "$GITEA_SSH_PORT:22"
EOF
}

write_runtime_config() {
  local gitea_http_port="$1"

  # Runtime-Konfiguration fuer getrenntes nginx Setup speichern.
  sudo tee "$RUNTIME_ENV_FILE" >/dev/null <<EOF
GITEA_DOMAIN=$GITEA_DOMAIN
GITEA_HTTP_PORT=$gitea_http_port
WEBSITE_DOMAIN=$WEBSITE_DOMAIN
WEBSITE_UPSTREAM_PORT=$WEBSITE_UPSTREAM_PORT
EOF
}

start_website_service() {
  if [ ! -d "$WEBSITE_DIR" ]; then
    echo "Fehler: Website Verzeichnis nicht gefunden: $WEBSITE_DIR"
    exit 1
  fi

  echo "Starte Website Docker Services..."
  cd "$WEBSITE_DIR"
  sudo docker compose up -d
}

start_gitea_service() {
  echo "Starte Gitea Docker Service..."
  cd "$GITEA_DIR"
  sudo docker compose up -d
}

stop_services() {
  echo "Stoppe Docker Services (Gitea + Website)..."

  if [ -f "$GITEA_DIR/docker-compose.yml" ]; then
    cd "$GITEA_DIR"
    sudo docker compose down
  elif sudo docker ps -a --format '{{.Names}}' | grep -qx gitea; then
    sudo docker stop gitea >/dev/null
    sudo docker rm gitea >/dev/null
  fi

  if [ -f "$WEBSITE_DIR/docker-compose.yml" ]; then
    cd "$WEBSITE_DIR"
    sudo docker compose down || true
  fi

  echo "-------------------------------------------------------"
  echo "Services wurden gestoppt."
  echo "Hinweis: nginx Proxy-Konfiguration bleibt aktiv und getrennt verwaltet."
  echo "-------------------------------------------------------"
}

start_services() {
  echo "Erstelle Gitea-Verzeichnisse in $GITEA_DIR..."
  sudo mkdir -p "$GITEA_DIR/data" "$GITEA_DIR/config"

  write_gitea_compose "$GITEA_HTTP_PORT"
  write_runtime_config "$GITEA_HTTP_PORT"
  start_gitea_service
  start_website_service

  if [ -x "$SCRIPT_DIR/nginx.sh" ]; then
    echo "Aktualisiere Nginx Reverse Proxy..."
    sudo "$SCRIPT_DIR/nginx.sh" apply || echo "Warnung: Nginx konnte nicht automatisch aktualisiert werden."
  fi

  if [ -x "$WEBSITE_DIR/sync_dev_hosts.sh" ]; then
    echo "Aktualisiere Hosts-Datei fuer Subdomains..."
    sudo "$WEBSITE_DIR/sync_dev_hosts.sh" || echo "Warnung: Hosts-Sync konnte nicht automatisch aktualisiert werden."
  fi

  echo "-------------------------------------------------------"
  echo "Docker Services wurden gestartet!"
  echo "Gitea Intern:  $GITEA_BIND_IP:$GITEA_HTTP_PORT"
  echo "Gitea SSH:     $GITEA_SSH_PORT"
  echo "Website Port:  $WEBSITE_UPSTREAM_PORT"
  echo "Gitea Domain:  $GITEA_DOMAIN"
  echo "Web Domain:    $WEBSITE_DOMAIN"
  echo "Aktueller Host: $(current_host_info)"
  echo ""
  echo "Nginx Reverse Proxy wurde automatisch aktualisiert, falls verfuegbar."
  echo "Hosts-Datei wurde automatisch synchronisiert, falls verfuegbar."
  echo "-------------------------------------------------------"
}

show_status() {
  echo "Docker Status (gitea / website):"
  sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|gitea|website-website-1|website-mongodb-1' || true
}

case "$ACTION" in
  start)
    start_services
    ;;
  stop)
    stop_services
    ;;
  restart)
    stop_services
    start_services
    ;;
  status)
    show_status
    ;;
  *)
    usage
    exit 1
    ;;
esac