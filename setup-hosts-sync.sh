#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="invario-hosts-sync"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SYNC_SCRIPT="$SCRIPT_DIR/Website/sync_dev_hosts.sh"
SERVICE_TEMPLATE="$SCRIPT_DIR/${SERVICE_NAME}.service"

echo "=== Invario Hosts-Sync Automatische Einrichtung ==="
echo ""

# Prüfe ob root
if [[ "${EUID}" -ne 0 ]]; then
  echo "❌ Fehler: Dieses Skript benötigt root-Rechte"
  echo "   Starten Sie mit: sudo $0"
  exit 1
fi

# Prüfe Abhängigkeiten
if [[ ! -x "$SYNC_SCRIPT" ]]; then
  echo "❌ Fehler: sync_dev_hosts.sh nicht gefunden unter $SYNC_SCRIPT"
  exit 1
fi

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
  echo "❌ Fehler: Service-Template nicht gefunden unter $SERVICE_TEMPLATE"
  exit 1
fi

# Installiere Service-Datei
echo "📋 Installiere systemd-Service..."
cp "$SERVICE_TEMPLATE" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# Lade systemd-Konfiguration neu
echo "🔄 Lade systemd-Konfiguration neu..."
systemctl daemon-reload

# Aktiviere und starte Service
echo "▶️  Starte und aktiviere ${SERVICE_NAME}.service..."
systemctl enable "$SERVICE_NAME.service"
systemctl start "$SERVICE_NAME.service"

# Anzeige Status
echo ""
echo "✅ Installation abgeschlossen!"
echo ""
echo "📊 Status überprüfen:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "📝 Logs anschauen:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "🛑 Service stoppen:"
echo "   sudo systemctl stop $SERVICE_NAME"
echo ""
echo "🗑️  Service deinstallieren:"
echo "   sudo systemctl disable $SERVICE_NAME"
echo "   sudo systemctl stop $SERVICE_NAME"
echo "   sudo rm $SERVICE_FILE"
echo "   sudo systemctl daemon-reload"
