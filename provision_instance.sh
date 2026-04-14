#!/usr/bin/env bash
set -euo pipefail

ACTION="create"
SCHOOL_NAME=""
SUBDOMAIN=""
REPO_URL=""
BASE_DIR=""
PARENT_DOMAIN=""
HTTPS_PORT=""
HTTP_PORT=""
TLS_MODE="development"
APP_IMAGE_TAG="latest"
LIBRARY_ENABLED="0"
WILDCARD_CERT_FILE="/etc/nginx/certs/wildcard.meine-domain.crt"
WILDCARD_KEY_FILE="/etc/nginx/certs/wildcard.meine-domain.key"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"

print_kv() {
  local key="$1"
  local value="$2"
  printf '%s=%s\n' "$key" "$value"
}

fail() {
  local message="$1"
  print_kv "MESSAGE" "$message"
  print_kv "ERROR" "$message"
  exit 1
}

slugify() {
  local input="$1"
  input="${input,,}"
  input="$(echo "$input" | sed -E 's/ä/ae/g; s/ö/oe/g; s/ü/ue/g; s/ß/ss/g')"
  input="$(echo "$input" | sed -E 's/[^a-z0-9-]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')"
  printf '%s' "${input:0:63}"
}

is_valid_subdomain() {
  local value="$1"
  [[ "$value" =~ ^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])$ ]]
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail "Fehlender Befehl: $cmd"
}

is_port_in_use() {
  local port="$1"

  if docker ps --format '{{.Ports}}' | grep -Eq "(^|[,[:space:]])((0\.0\.0\.0|\[::\]):)?${port}->"; then
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :$port )" 2>/dev/null | awk 'NR>1 {print $4}' | grep -q . && return 0
  fi

  return 1
}

next_free_port() {
  local start_port="$1"
  local current="$start_port"
  while is_port_in_use "$current"; do
    current=$((current + 1))
  done
  printf '%s' "$current"
}

write_env_file() {
  local target_dir="$1"
  local http_port="$2"
  local https_port="$3"
  local app_image_tag="$4"

  cat > "$target_dir/.docker-build.env" <<EOF
NUITKA_BUILD=0
INVENTAR_HTTP_PORT=$http_port
INVENTAR_HTTPS_PORT=$https_port
INVENTAR_APP_IMAGE=ghcr.io/aiirondev/legendary-octo-garbanzo:$app_image_tag
EOF
}

set_library_enabled() {
  local instance_dir="$1"
  local enabled="$2"
  local cfg="$instance_dir/config.json"
  [ -f "$cfg" ] || return 0

  python3 - <<'PY' "$cfg" "$enabled"
import json
import sys

cfg_path = sys.argv[1]
enabled = sys.argv[2] == "1"

with open(cfg_path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

modules = data.get("modules")
if not isinstance(modules, dict):
    modules = {}
    data["modules"] = modules

library = modules.get("library")
if not isinstance(library, dict):
    library = {}
    modules["library"] = library

library["enabled"] = enabled

with open(cfg_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

normalize_instance_compose() {
  local compose_file="docker-compose.yml"
  [ -f "$compose_file" ] || return 0

  python3 - <<'PY'
from pathlib import Path

path = Path("docker-compose.yml")
content = path.read_text(encoding="utf-8")
lines = content.splitlines()

out = []
in_nginx = False
i = 0

while i < len(lines):
  line = lines[i]
  stripped = line.strip()
  indent = len(line) - len(line.lstrip(" "))

  if stripped.startswith("nginx:") and indent == 2:
    in_nginx = True
    out.append(line)
    i += 1
    continue

  if in_nginx and indent == 2 and stripped.endswith(":") and not stripped.startswith("nginx:"):
    in_nginx = False

  if stripped.startswith("container_name:") and indent == 4:
    i += 1
    continue

  if in_nginx and stripped.startswith("ports:") and indent == 4:
    out.append(line)
    out.append("      - \"${INVENTAR_HTTP_PORT:-80}:80\"")
    out.append("      - \"${INVENTAR_HTTPS_PORT:-443}:443\"")
    i += 1
    while i < len(lines):
      nxt = lines[i]
      nxt_stripped = nxt.strip()
      nxt_indent = len(nxt) - len(nxt.lstrip(" "))
      if nxt_stripped.startswith("-") and nxt_indent >= 6:
        i += 1
        continue
      break
    continue

  out.append(line)
  i += 1

normalized = "\n".join(out)
if content.endswith("\n"):
  normalized += "\n"

if normalized != content:
  path.write_text(normalized, encoding="utf-8")
PY
}

run_instance_start() {
  local start_output
  local retry_output
  local update_output

  stack_is_running() {
    local running_services
    running_services="$(docker compose --env-file .docker-build.env ps --status running --services 2>/dev/null || true)"
    printf '%s\n' "$running_services" | grep -Fxq app || return 1
    printf '%s\n' "$running_services" | grep -Fxq nginx || return 1
    printf '%s\n' "$running_services" | grep -Fxq mongodb || return 1
    return 0
  }

  if start_output="$(INVENTAR_SETUP_CRON=0 INVENTAR_HTTP_PORT="$HTTP_PORT" INVENTAR_HTTPS_PORT="$HTTPS_PORT" bash ./start.sh --no-cron 2>&1)"; then
    return 0
  fi

  if stack_is_running; then
    print_kv "MESSAGE" "Instanz gestartet (Healthcheck im Startskript war nicht erreichbar, Dienste laufen)."
    return 0
  fi

  if printf '%s' "$start_output" | grep -qi "local app image not found"; then
    if [ ! -x ./update.sh ]; then
      fail "start.sh fehlgeschlagen und update.sh fehlt. Letzte Meldung: $(printf '%s' "$start_output" | tail -n1)"
    fi

    if ! update_output="$(bash ./update.sh 2>&1)"; then
      if stack_is_running; then
        print_kv "MESSAGE" "Instanz gestartet (update.sh meldete Healthcheck-Fehler, Dienste laufen)."
        return 0
      fi
      fail "update.sh fehlgeschlagen: $(printf '%s' "$update_output" | tail -n1)"
    fi

    if retry_output="$(INVENTAR_SETUP_CRON=0 INVENTAR_HTTP_PORT="$HTTP_PORT" INVENTAR_HTTPS_PORT="$HTTPS_PORT" bash ./start.sh --no-cron 2>&1)"; then
      print_kv "MESSAGE" "Instanz gestartet (Image automatisch per update.sh geladen)."
      return 0
    fi

    fail "Start nach update.sh fehlgeschlagen: $(printf '%s' "$retry_output" | tail -n1)"
  fi

  fail "start.sh fehlgeschlagen: $(printf '%s' "$start_output" | tail -n1)"
}

setup_or_update_repo() {
  local target_dir="$1"
  local repo_url="$2"
  local installer_url="https://raw.githubusercontent.com/AIIrondev/legendary-octo-garbanzo/main/install.sh"
  local installer_script=""

  if [ -f "$target_dir/start.sh" ]; then
    # Existing installation: keep it docker-only and update via project tooling.
    if [ -x "$target_dir/update.sh" ]; then
      (cd "$target_dir" && bash ./update.sh >/dev/null 2>&1 || true)
    fi
    return 0
  fi

  if [ -d "$target_dir" ] && [ "$(find "$target_dir" -mindepth 1 -maxdepth 1 | wc -l)" -gt 0 ]; then
    fail "Zielverzeichnis ist nicht leer: $target_dir"
  fi

  mkdir -p "$target_dir"
  installer_script="$(mktemp)"
  if ! wget -qO- "$installer_url" > "$installer_script"; then
    rm -f "$installer_script"
    fail "Installer konnte nicht geladen werden: $installer_url"
  fi

  # Patch only the target directory variable so we can install per instance.
  if ! sed -i "s|^PROJECT_DIR=.*$|PROJECT_DIR=\"$target_dir\"|" "$installer_script"; then
    rm -f "$installer_script"
    fail "Installer konnte nicht vorbereitet werden."
  fi

  if ! bash "$installer_script" --skip-cleanup-old; then
    rm -f "$installer_script"
    fail "Installer-Ausführung fehlgeschlagen."
  fi

  rm -f "$installer_script"
}

write_nginx_site() {
  local subdomain="$1"
  local full_domain="$2"
  local https_port="$3"
  local cert_file=""
  local key_file=""
  local cert_dir="/etc/nginx/certs"
  local site_name="inventarsystem-${subdomain}.conf"
  local avail_file="$NGINX_SITES_AVAILABLE/$site_name"
  local enabled_file="$NGINX_SITES_ENABLED/$site_name"

  if [ ! -d "$NGINX_SITES_AVAILABLE" ] || [ ! -d "$NGINX_SITES_ENABLED" ]; then
    print_kv "NGINX_STATUS" "skipped"
    print_kv "MESSAGE" "Instanz gestartet. Nginx-Verzeichnisse nicht gefunden, Reverse-Proxy manuell anlegen."
    return 0
  fi

  if [ ! -w "$NGINX_SITES_AVAILABLE" ] || [ ! -w "$NGINX_SITES_ENABLED" ]; then
    print_kv "NGINX_STATUS" "manual_required"
    print_kv "MESSAGE" "Instanz gestartet. Keine Schreibrechte auf Nginx-Konfiguration, bitte als root/sudo ausführen."
    return 0
  fi

  if [ "$TLS_MODE" = "production" ]; then
    cert_file="$WILDCARD_CERT_FILE"
    key_file="$WILDCARD_KEY_FILE"

    if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
      print_kv "NGINX_STATUS" "error"
      print_kv "MESSAGE" "Produktivmodus aktiv, aber Wildcard-Zertifikat fehlt: $cert_file / $key_file"
      return 0
    fi
  else
    cert_file="$cert_dir/$full_domain.crt"
    key_file="$cert_dir/$full_domain.key"

    if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
      if ! command -v openssl >/dev/null 2>&1; then
        print_kv "NGINX_STATUS" "manual_required"
        print_kv "MESSAGE" "Instanz gestartet. openssl fehlt für Development-Zertifikat, Zertifikat bitte manuell anlegen."
        return 0
      fi

      if [ ! -d "$cert_dir" ] || [ ! -w "$cert_dir" ]; then
        print_kv "NGINX_STATUS" "manual_required"
        print_kv "MESSAGE" "Instanz gestartet. Keine Schreibrechte auf $cert_dir für Development-Zertifikat."
        return 0
      fi

      if ! openssl req -x509 -nodes -newkey rsa:2048 -sha256 \
        -days 825 \
        -keyout "$key_file" \
        -out "$cert_file" \
        -subj "/CN=$full_domain" \
        -addext "subjectAltName=DNS:$full_domain" >/dev/null 2>&1; then
        openssl req -x509 -nodes -newkey rsa:2048 -sha256 \
          -days 825 \
          -keyout "$key_file" \
          -out "$cert_file" \
          -subj "/CN=$full_domain" >/dev/null 2>&1 || {
            print_kv "NGINX_STATUS" "manual_required"
            print_kv "MESSAGE" "Instanz gestartet. Development-Zertifikat konnte nicht erstellt werden."
            return 0
          }
      fi

      chmod 600 "$key_file" 2>/dev/null || true
      chmod 644 "$cert_file" 2>/dev/null || true
    fi
  fi

  cat > "$avail_file" <<EOF
server {
    listen 80;
    server_name $full_domain;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $full_domain;

  ssl_certificate $cert_file;
  ssl_certificate_key $key_file;

    location / {
        proxy_pass https://127.0.0.1:$https_port;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_ssl_verify off;
        proxy_read_timeout 120s;
    }
}
EOF

  ln -sfn "$avail_file" "$enabled_file"

  if ! command -v nginx >/dev/null 2>&1; then
    print_kv "NGINX_STATUS" "manual_required"
    print_kv "MESSAGE" "Instanz gestartet. Nginx-Site wurde geschrieben, Reload bitte auf dem Host ausführen."
    return 0
  fi

  if nginx -t >/dev/null 2>&1; then
    nginx -s reload >/dev/null 2>&1 || true
    print_kv "NGINX_STATUS" "ok"
  else
    print_kv "NGINX_STATUS" "error"
    print_kv "MESSAGE" "Instanz gestartet, aber nginx -t ist fehlgeschlagen."
    return 0
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --action)
      ACTION="${2:-}"
      shift 2
      ;;
    --school-name)
      SCHOOL_NAME="${2:-}"
      shift 2
      ;;
    --subdomain)
      SUBDOMAIN="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --base-dir)
      BASE_DIR="${2:-}"
      shift 2
      ;;
    --domain)
      PARENT_DOMAIN="${2:-}"
      shift 2
      ;;
    --https-port)
      HTTPS_PORT="${2:-}"
      shift 2
      ;;
    --http-port)
      HTTP_PORT="${2:-}"
      shift 2
      ;;
    --tls-mode)
      TLS_MODE="${2:-}"
      shift 2
      ;;
    --wildcard-cert-file)
      WILDCARD_CERT_FILE="${2:-}"
      shift 2
      ;;
    --wildcard-key-file)
      WILDCARD_KEY_FILE="${2:-}"
      shift 2
      ;;
    --app-image-tag)
      APP_IMAGE_TAG="${2:-latest}"
      shift 2
      ;;
    --library-enabled)
      LIBRARY_ENABLED="${2:-0}"
      shift 2
      ;;
    *)
      fail "Unbekannter Parameter: $1"
      ;;
  esac
done

[ -n "$REPO_URL" ] || fail "Repository-URL fehlt"
[ -n "$BASE_DIR" ] || fail "Basisverzeichnis fehlt"
[ -n "$PARENT_DOMAIN" ] || fail "Parent-Domain fehlt"

if [ -z "$SUBDOMAIN" ]; then
  SUBDOMAIN="$(slugify "$SCHOOL_NAME")"
else
  SUBDOMAIN="$(slugify "$SUBDOMAIN")"
fi

is_valid_subdomain "$SUBDOMAIN" || fail "Ungueltige Subdomain: $SUBDOMAIN"

INSTANCE_DIR="$BASE_DIR/$SUBDOMAIN"
FULL_DOMAIN="$SUBDOMAIN.$PARENT_DOMAIN"

require_cmd docker
require_cmd bash
require_cmd wget

mkdir -p "$BASE_DIR"

if [ -z "$HTTPS_PORT" ]; then
  HTTPS_PORT="$(next_free_port 15443)"
fi

if [ -z "$HTTP_PORT" ]; then
  HTTP_PORT="$(next_free_port 15080)"
fi

if [ "$ACTION" = "create" ] || [ "$ACTION" = "start" ]; then
  setup_or_update_repo "$INSTANCE_DIR" "$REPO_URL"

  [ -f "$INSTANCE_DIR/start.sh" ] || fail "start.sh im Zielrepository nicht gefunden: $INSTANCE_DIR"

  write_env_file "$INSTANCE_DIR" "$HTTP_PORT" "$HTTPS_PORT" "$APP_IMAGE_TAG"
  set_library_enabled "$INSTANCE_DIR" "$LIBRARY_ENABLED"

  cd "$INSTANCE_DIR"
  normalize_instance_compose
  run_instance_start

  write_nginx_site "$SUBDOMAIN" "$FULL_DOMAIN" "$HTTPS_PORT"

  print_kv "SUBDOMAIN" "$SUBDOMAIN"
  print_kv "DOMAIN" "$FULL_DOMAIN"
  print_kv "HTTPS_PORT" "$HTTPS_PORT"
  print_kv "HTTP_PORT" "$HTTP_PORT"
  print_kv "APP_IMAGE_TAG" "$APP_IMAGE_TAG"
  print_kv "LIBRARY_ENABLED" "$LIBRARY_ENABLED"
  print_kv "INSTANCE_DIR" "$INSTANCE_DIR"
  exit 0
fi

fail "Nicht unterstuetzte Action: $ACTION"
