#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="invario-stack-autostart"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SERVICE_TEMPLATE="$SCRIPT_DIR/${SERVICE_NAME}.service"
BOOT_SCRIPT="$SCRIPT_DIR/start-stack-on-boot.sh"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root. Use: sudo $0"
  exit 1
fi

if [[ ! -x "$BOOT_SCRIPT" ]]; then
  echo "Missing executable boot script: $BOOT_SCRIPT"
  exit 1
fi

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "Missing service template: $SERVICE_TEMPLATE"
  exit 1
fi

cp "$SERVICE_TEMPLATE" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"

echo "Autostart installed. Start it now with: systemctl start $SERVICE_NAME"
echo "Check status with: systemctl status $SERVICE_NAME"
