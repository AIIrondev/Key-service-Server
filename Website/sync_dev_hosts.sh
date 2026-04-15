#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOSTS_FILE="/etc/hosts"
START_MARK="# >>> invario-dev-hosts >>>"
END_MARK="# <<< invario-dev-hosts <<<"

HOST_IP="${DEV_HOSTS_IP:-}"
if [[ -z "$HOST_IP" ]]; then
  HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi

if [[ -z "$HOST_IP" ]]; then
  HOST_IP="127.0.0.1"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker fehlt; Hosts-Sync übersprungen"
  exit 0
fi

if ! docker compose ps mongodb >/dev/null 2>&1; then
  echo "mongodb-compose-Service nicht erreichbar; Hosts-Sync übersprungen"
  exit 0
fi

DOMAINS_RAW="$(docker compose exec -T mongodb mongosh --quiet --eval 'db.getSiblingDB("Invario_Website").school_instances.find({},{_id:0,domain:1}).toArray().forEach(d=>{ if(d.domain){ print(String(d.domain).trim()) } })' 2>/dev/null || true)"

TMP_BLOCK="$(mktemp)"
trap 'rm -f "$TMP_BLOCK"' EXIT

{
  echo "$START_MARK"
  echo "127.0.0.1 localhost"
  while IFS= read -r line; do
    domain="$(echo "$line" | tr -d '\r' | xargs)"
    if [[ -n "$domain" ]]; then
      echo "$HOST_IP $domain"
    fi
  done <<< "$DOMAINS_RAW"
  echo "$END_MARK"
} > "$TMP_BLOCK"

if [[ "${EUID}" -eq 0 ]]; then
  sed -i "/$START_MARK/,/$END_MARK/d" "$HOSTS_FILE"
  cat "$TMP_BLOCK" >> "$HOSTS_FILE"
else
  sudo sed -i "/$START_MARK/,/$END_MARK/d" "$HOSTS_FILE"
  sudo tee -a "$HOSTS_FILE" < "$TMP_BLOCK" >/dev/null
fi

echo "Hosts-Sync abgeschlossen"