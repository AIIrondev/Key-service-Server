# Automatische Subdomain-Hosts-Synchronisation

## Problem
Nach jedem Neustart waren die Subdomains nicht mehr im `/etc/hosts` eingetragen, was zu Verbindungsproblemen führte. Das musste manuell mit `sync_dev_hosts.sh` behoben werden.

## Lösung

Diese Lösung bietet **3 Ebenen der Automatisierung**:

### 1. ✅ Automatische Sync bei Container-Start
**Datei:** `launch_prod.sh` und `launch_dev.sh`

- Nach `docker compose up` wird `sync_dev_hosts.sh` automatisch aufgerufen
- Ein Background-Daemon sorgt für regelmäßige Synchronisation
- **Development:** Alle 30 Sekunden (konfigurierbar via `DEV_HOSTS_REFRESH_INTERVAL`)
- **Production:** Alle 3600 Sekunden/1 Stunde (konfigurierbar via `PROD_HOSTS_REFRESH_INTERVAL`)

### 2. ✅ systemd Service für permanente Automatisierung
**Dateien:** `invario-hosts-sync.service`, `setup-hosts-sync.sh`

Der systemd-Service stellt sicher, dass die Hosts-Synchronisation auch nach System-Reboots aktiviert bleibt.

#### Installation:
```bash
cd /home/max/Dokumente/repos/Key-service-Server
sudo ./setup-hosts-sync.sh
```

#### Status überprüfen:
```bash
sudo systemctl status invario-hosts-sync
```

#### Logs anschauen:
```bash
sudo journalctl -u invario-hosts-sync -f
```

#### Deinstallation:
```bash
sudo systemctl disable invario-hosts-sync
sudo systemctl stop invario-hosts-sync
sudo rm /etc/systemd/system/invario-hosts-sync.service
sudo systemctl daemon-reload
```

### 3. ✅ Manuelle Synchronisation
Jederzeit manuell möglich:
```bash
cd /home/max/Dokumente/repos/Key-service-Server/Website
./sync_dev_hosts.sh
```

## Wie es funktioniert

1. **sync_dev_hosts.sh** liest alle Subdomains aus der MongoDB-Datenbank
2. Aktualisiert `/etc/hosts` mit den gültigen Subdomains
3. Läuft auf verschiedenen Ebenen:
   - Beim Container-Start (launch_prod.sh/launch_dev.sh)
   - Im Hintergrund als regelmäßiger Job
   - Als systemd-Service für permanente Überwachung

## Konfiguration

### Environment-Variablen:

**Für Development:**
```bash
DEV_HOSTS_IP=192.168.1.100      # Optionale IP (Standard: auto-detect)
DEV_HOSTS_REFRESH_INTERVAL=30   # Sekunden zwischen Syncs (0 = deaktiviert)
```

**Für Production:**
```bash
PROD_HOSTS_REFRESH_INTERVAL=3600  # Sekunden zwischen Syncs (0 = deaktiviert)
```

## Troubleshooting

### Service startet nicht
```bash
# Logs prüfen
sudo journalctl -u invario-hosts-sync --no-pager

# Service neu laden
sudo systemctl daemon-reload
sudo systemctl restart invario-hosts-sync
```

### Hosts werden nicht aktualisiert
```bash
# Manuell test
./Website/sync_dev_hosts.sh

# MongoDB-Verbindung prüfen
docker compose ps mongodb
docker compose logs mongodb
```

### Berechtigungen-Fehler
Das Script benötigt Zugriff auf `/etc/hosts`. Normalerweise wird es als `root` ausgeführt:
```bash
# Wenn nötig mit sudo
sudo ./Website/sync_dev_hosts.sh
```
