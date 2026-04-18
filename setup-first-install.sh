#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUN_START=1
RUN_NGINX=1
RUN_HOSTS_SYNC=1
RUN_AUTOSTART=1

usage() {
  cat <<'EOF'
Usage: sudo ./setup-first-install.sh [options]

Options:
  --skip-start         Skip stack start via gitea.sh
  --skip-nginx         Skip nginx apply via nginx.sh
  --skip-hosts-sync    Skip installation of invario-hosts-sync.service
  --skip-autostart     Skip installation of invario-stack-autostart.service
  -h, --help           Show this help

Default behavior:
  1) Start stack
  2) Apply nginx
  3) Install hosts-sync service
  4) Install stack-autostart service
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-start)
      RUN_START=0
      shift
      ;;
    --skip-nginx)
      RUN_NGINX=0
      shift
      ;;
    --skip-hosts-sync)
      RUN_HOSTS_SYNC=0
      shift
      ;;
    --skip-autostart)
      RUN_AUTOSTART=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root. Use: sudo $0"
  exit 1
fi

require_script() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file"
    exit 1
  fi
  if [[ ! -x "$file" ]]; then
    chmod +x "$file"
  fi
}

require_script "$SCRIPT_DIR/gitea.sh"
require_script "$SCRIPT_DIR/nginx.sh"
require_script "$SCRIPT_DIR/setup-hosts-sync.sh"
require_script "$SCRIPT_DIR/setup-stack-autostart.sh"

echo "Running first installation setup in: $SCRIPT_DIR"

action_or_skip() {
  local flag="$1"
  local title="$2"
  shift 2

  if [[ "$flag" -eq 1 ]]; then
    echo "[RUN ] $title"
    "$@"
  else
    echo "[SKIP] $title"
  fi
}

action_or_skip "$RUN_START" "Start stack (gitea.sh start)" "$SCRIPT_DIR/gitea.sh" start
action_or_skip "$RUN_NGINX" "Apply nginx (nginx.sh apply)" "$SCRIPT_DIR/nginx.sh" apply
action_or_skip "$RUN_HOSTS_SYNC" "Install hosts-sync service" "$SCRIPT_DIR/setup-hosts-sync.sh"
action_or_skip "$RUN_AUTOSTART" "Install stack-autostart service" "$SCRIPT_DIR/setup-stack-autostart.sh"

echo
echo "First installation setup completed."
echo "Service status checks:"
echo "  systemctl status invario-hosts-sync"
echo "  systemctl status invario-stack-autostart"
echo "Stack status:"
echo "  $SCRIPT_DIR/gitea.sh status"
