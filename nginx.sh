#!/usr/bin/env bash
set -euo pipefail

# Konfiguration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_TEMPLATE_DIR="$SCRIPT_DIR/nginx"
GITEA_DIR="/opt/gitea-server"
RUNTIME_ENV_FILE="$GITEA_DIR/runtime.env"
CERT_DIR="/etc/nginx/certs"
SSL_CERT_DAYS="825"

# Fallback-Werte (werden durch runtime.env ueberschrieben, wenn vorhanden)
GITEA_DOMAIN="update.meine-domain"
GITEA_HTTP_PORT="3001"
WEBSITE_DOMAIN="meine-domain"
WEBSITE_UPSTREAM_PORT="4999"

ACTION="${1:-apply}"

usage() {
  echo "Nutzung: $0 [apply|disable|deactivate]"
  echo "Hinweis: Docker Services mit ./gitea.sh [start|stop|restart|status] verwalten."
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

load_runtime_config() {
  if [ -f "$RUNTIME_ENV_FILE" ]; then
    # Nur erwartete Keys werden geladen.
    while IFS='=' read -r key value; do
      case "$key" in
        GITEA_DOMAIN) GITEA_DOMAIN="$value" ;;
        GITEA_HTTP_PORT) GITEA_HTTP_PORT="$value" ;;
        WEBSITE_DOMAIN) WEBSITE_DOMAIN="$value" ;;
        WEBSITE_UPSTREAM_PORT) WEBSITE_UPSTREAM_PORT="$value" ;;
      esac
    done < "$RUNTIME_ENV_FILE"
  else
    echo "Warnung: $RUNTIME_ENV_FILE nicht gefunden, nutze Standardwerte."
  fi
}

render_nginx_template() {
  local template_file="$1"
  local output_file="$2"
  local domain="$3"
  local upstream_port="$4"
  local cert_file="$5"
  local key_file="$6"

  sed \
    -e "s|__DOMAIN__|$domain|g" \
    -e "s|__PORT__|$upstream_port|g" \
    -e "s|__CERT_FILE__|$cert_file|g" \
    -e "s|__KEY_FILE__|$key_file|g" \
    "$template_file" | sudo tee "$output_file" >/dev/null
}

configure_nginx_site() {
  local site_name="$1"
  local domain="$2"
  local upstream_port="$3"
  local cert_file="$CERT_DIR/$domain.crt"
  local key_file="$CERT_DIR/$domain.key"
  local template_file="$NGINX_TEMPLATE_DIR/$site_name.https.conf.template"
  local site_file="/etc/nginx/sites-available/$site_name"
  local site_link="/etc/nginx/sites-enabled/$site_name"

  ensure_ssl_certificate "$domain" "$cert_file" "$key_file"
  echo "Nutze HTTPS nginx Template fuer $domain."

  if [ ! -f "$template_file" ]; then
    echo "[FEHLER] nginx Template nicht gefunden: $template_file" >&2
    echo "[HINWEIS] Prüfe, ob die Datei existiert und korrekt benannt ist." >&2
    exit 11
  fi

  if ! render_nginx_template "$template_file" "$site_file" "$domain" "$upstream_port" "$cert_file" "$key_file"; then
    echo "[FEHLER] nginx Template konnte nicht gerendert werden: $template_file" >&2
    exit 12
  fi
  if ! sudo ln -sf "$site_file" "$site_link"; then
    echo "[FEHLER] Symlink für nginx Site konnte nicht erstellt werden: $site_link" >&2
    exit 13
  fi
}

ensure_ssl_certificate() {
  local domain="$1"
  local cert_file="$2"
  local key_file="$3"

  if ! command -v openssl >/dev/null 2>&1; then
    echo "[FEHLER] openssl ist nicht installiert. Bitte installiere openssl." >&2
    exit 21
  fi

  sudo mkdir -p "$CERT_DIR"

  if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
    if sudo openssl x509 -in "$cert_file" -noout >/dev/null 2>&1; then
      echo "SSL Zertifikat gefunden fuer $domain: $cert_file"
      return
    else
      echo "[WARNUNG] Zertifikat $cert_file ist beschädigt oder ungültig. Erstelle neu..."
      sudo rm -f "$cert_file" "$key_file"
    fi
  fi

  echo "Kein gültiges SSL Zertifikat für $domain gefunden. Erzeuge self-signed Zertifikat..."
  if ! sudo openssl req -x509 -nodes -newkey rsa:2048 -sha256 \
    -days "$SSL_CERT_DAYS" \
    -keyout "$key_file" \
    -out "$cert_file" \
    -subj "/CN=$domain" \
    -addext "subjectAltName=DNS:$domain"; then
    # Fallback für ältere openssl-Versionen ohne -addext.
    sudo openssl req -x509 -nodes -newkey rsa:2048 -sha256 \
      -days "$SSL_CERT_DAYS" \
      -keyout "$key_file" \
      -out "$cert_file" \
      -subj "/CN=$domain"
  fi

  sudo chmod 600 "$key_file"
  sudo chmod 644 "$cert_file"
  echo "[INFO] Selbstsigniertes Zertifikat für $domain wurde erstellt: $cert_file"
}

reload_nginx() {
  echo "Pruefe nginx Konfiguration..."
  if ! sudo nginx -t; then
    echo "[FEHLER] nginx Konfiguration fehlerhaft! Bitte prüfe die Ausgaben oben." >&2
    exit 31
  fi

  if sudo pgrep -x nginx >/dev/null 2>&1; then
    echo "Nginx Prozess gefunden, lade Konfiguration neu..."
    if ! sudo nginx -s reload; then
      echo "[WARNUNG] nginx konnte nicht automatisch neu geladen werden."
      echo "Die Konfiguration wurde geschrieben; bitte nginx bei Bedarf manuell neu laden."
    fi
  elif sudo systemctl is-active --quiet nginx; then
    echo "Lade nginx neu..."
    if ! sudo systemctl reload nginx; then
      echo "[WARNUNG] nginx reload via systemd fehlgeschlagen."
      echo "Bitte prüfe: sudo systemctl status nginx.service"
    fi
  else
    echo "Nginx ist nicht aktiv, starte nginx..."
    if ! sudo systemctl start nginx; then
      echo "[WARNUNG] Nginx konnte nicht über systemd gestartet werden."
      echo "Falls nginx bereits manuell läuft, kann die Weiterleitung trotzdem funktionieren."
      echo "Ansonsten prüfe: sudo systemctl status nginx.service"
      echo "Und Logs mit: sudo journalctl -xeu nginx.service"
    fi
  fi
}

ensure_firewall_http_https() {
  if ! command -v ufw >/dev/null 2>&1; then
    return
  fi

  if sudo ufw status 2>/dev/null | grep -qi "Status: active"; then
    echo "Oeffne Firewall fuer 80/tcp und 443/tcp (ufw)..."
    sudo ufw allow 80/tcp >/dev/null || true
    sudo ufw allow 443/tcp >/dev/null || true
  fi
}

apply_nginx() {
  if ! command -v nginx >/dev/null 2>&1; then
    echo "Fehler: nginx ist nicht installiert. Bitte zuerst nginx installieren."
    exit 1
  fi

  load_runtime_config

  echo "Erstelle nginx Reverse-Proxy Konfigurationen..."
  configure_nginx_site "gitea" "$GITEA_DOMAIN" "$GITEA_HTTP_PORT"
  configure_nginx_site "website" "$WEBSITE_DOMAIN" "$WEBSITE_UPSTREAM_PORT"

  ensure_firewall_http_https
  reload_nginx

  echo "-------------------------------------------------------"
  echo "Nginx wurde aktualisiert."
  echo "Gitea Domain:  $GITEA_DOMAIN -> 127.0.0.1:$GITEA_HTTP_PORT"
  echo "Web Domain:    $WEBSITE_DOMAIN -> 127.0.0.1:$WEBSITE_UPSTREAM_PORT"
  echo "Zertifikat Ordner: $CERT_DIR"
  echo "Aktueller Host: $(current_host_info)"
  echo "-------------------------------------------------------"
}

disable_nginx() {
  local changed=0

  if ! command -v nginx >/dev/null 2>&1; then
    echo "Fehler: nginx ist nicht installiert."
    exit 1
  fi

  for site_name in gitea website; do
    local site_link="/etc/nginx/sites-enabled/$site_name"
    if [ -L "$site_link" ] || [ -e "$site_link" ]; then
      echo "Deaktiviere nginx Site: $site_name"
      sudo rm -f "$site_link"
      changed=1
    fi
  done

  if [ "$changed" -eq 1 ]; then
    reload_nginx
    echo "-------------------------------------------------------"
    echo "Nginx Reverse-Proxy Sites wurden deaktiviert."
    echo "Aktueller Host: $(current_host_info)"
    echo "-------------------------------------------------------"
  else
    echo "Keine verwalteten nginx Sites aktiv (gitea/website)."
  fi
}

case "$ACTION" in
  apply)
    apply_nginx
    ;;
  disable|deactivate)
    disable_nginx
    ;;
  *)
    usage
    exit 1
    ;;
esac
