# Key Service Server

Dieses Repository ist auf einen schlanken, Docker-first Betrieb ausgerichtet.

## Voraussetzungen

- Docker Engine + Docker Compose Plugin
- Nginx
- OpenSSL
- Optional: UFW (Ports 80/443 werden bei aktivem UFW automatisch freigegeben)

## Script Matrix

### Core-Skripte (aktiv)

- [gitea.sh](gitea.sh)
  - Start/Stop/Restart/Status für Gitea + Website-Stack
- [nginx.sh](nginx.sh)
  - Nginx-Konfiguration anwenden/deaktivieren
- [Website/provision_instance.sh](Website/provision_instance.sh)
  - Instanz-Provisioning für Inventarsystem (release-basiert, Multiinstancing-aware)
- [Website/launch_dev.sh](Website/launch_dev.sh)
  - Dev-Start der Website inkl. Host-Sync
- [Website/launch_prod.sh](Website/launch_prod.sh)
  - Prod-Start der Website inkl. Host-Sync
- [Website/start_docker_build.sh](Website/start_docker_build.sh)
  - Build/Start-Helfer für Website-Container
- [Website/sync_dev_hosts.sh](Website/sync_dev_hosts.sh)
  - Synchronisiert dynamische Subdomains in /etc/hosts

### Setup-Skripte (optional, aktiv)

- [setup-first-install.sh](setup-first-install.sh)
  - Führt Erstinstallation in einem Ablauf aus (Start, Nginx, Hosts-Sync-Service, Autostart-Service)
- [setup-hosts-sync.sh](setup-hosts-sync.sh)
  - Installiert den systemd-Service für automatische Hosts-Synchronisierung
- [setup-stack-autostart.sh](setup-stack-autostart.sh)
  - Installiert den systemd-Service für Stack-Autostart über gitea.sh

### Legacy-Skripte (entfernt)

- start-stack-on-boot.sh (durch direkten systemd-ExecStart auf gitea.sh ersetzt)
- provision_instance.sh im Repo-Root (Duplikat, Website-Version ist Single Source)
- Website/run.sh (alt, nicht Teil des aktuellen Flows)
- Website/test.sh (alt, nicht Teil des aktuellen Flows)

## Core Betrieb

### Docker Services

Datei: [gitea.sh](gitea.sh)

Befehle:

- sudo ./gitea.sh start
- sudo ./gitea.sh stop
- sudo ./gitea.sh restart
- sudo ./gitea.sh status

Wichtige Ports:

- Gitea intern: 127.0.0.1:3001
- Gitea SSH: 2222
- Website Upstream: 4999

### Nginx

Datei: [nginx.sh](nginx.sh)

Befehle:

- sudo ./nginx.sh apply
- sudo ./nginx.sh disable
- sudo ./nginx.sh deactivate

Nginx-Templates:

- [nginx/gitea.http.conf.template](nginx/gitea.http.conf.template)
- [nginx/gitea.https.conf.template](nginx/gitea.https.conf.template)
- [nginx/website.http.conf.template](nginx/website.http.conf.template)
- [nginx/website.https.conf.template](nginx/website.https.conf.template)

## Inventarsystem Instanzen

Admin-Oberfläche:

- Route: /admin/instances
- Menu: Schul-Instanzen

Provisioning-Flow:

1. Admin wählt Nutzer, Schule, Version und optional Subdomain.
2. Backend ruft [Website/provision_instance.sh](Website/provision_instance.sh) auf.
3. Provisioning installiert release-basiert aus GitHub-Releases.
4. Wenn verfügbar, wird docker-compose-multitenant.yml bevorzugt genutzt.
5. Instanzstatus wird in school_instances gespeichert.

Wichtige Website-Variablen:

- INSTANCE_REPO_URL (default: https://github.com/AIIrondev/legendary-octo-garbanzo)
- INSTANCE_PARENT_DOMAIN (default: meine-domain)
- INSTANCE_BASE_DIR (default: /opt/inventarsystem-instances)
- INSTANCE_PROVISION_SCRIPT (default: Website/provision_instance.sh)

Berechtigungen für Provisioning:

- Docker-Zugriff
- Schreibrechte auf /etc/nginx/sites-available und /etc/nginx/sites-enabled
- nginx -t und nginx reload/signal-Rechte

## Admin Homepage: Live-Logs

Die Admin-Seite unter /admin/system zeigt jetzt Live-Logs direkt im Frontend.

Enthaltene Quellen:

- Core Docker Logs (website + mongodb)
- invario-hosts-sync.service
- invario-stack-autostart.service
- nginx.service

Verhalten:

- Auto-Refresh alle 20 Sekunden
- Manuelles Aktualisieren per Button
- Auswahl der Log-Quelle per Dropdown

Hinweis:

- Wenn die Website ohne Zugriff auf systemd/journalctl läuft (z. B. in eingeschränkten Containern), bleiben Core-Docker-Logs verfügbar, während Service-Logs als nicht verfügbar angezeigt werden können.

## Betriebsmodi Website

- Development: [Website/launch_dev.sh](Website/launch_dev.sh)
- Production: [Website/launch_prod.sh](Website/launch_prod.sh)

### Neues: Start-Health-Check im `launch_dev.sh`

`Website/launch_dev.sh` führt jetzt vor dem Build eine kurze Prüfung durch und wartet nach dem Start auf eine erreichbare HTTP-Antwort:

- Vor dem Build wird geprüft, ob `gunicorn.conf.py` im `Website/`-Verzeichnis vorhanden ist; falls nicht, bricht das Skript mit einer erklärenden Fehlermeldung ab.
- Nach `docker compose up -d` wartet das Skript bis zu 60 Sekunden (Intervall 2s) auf einen erfolgreichen HTTP-Request (`/`) auf `127.0.0.1:4999`.
- Schlägt der Health-Check fehl, sammelt das Skript automatisch folgende Diagnosedaten und gibt Hinweise aus:
  - `docker compose ps`
  - `docker logs --tail 200 website-website-1`

Dies hilft, wiederkehrende Probleme (fehlende Dateien, fehlerhafte Container-Starts, nginx-Fehlkonfiguration) schneller zu finden.

Empfohlene manuelle Prüfbefehle (bei Problemen):

```bash
# Status aller Container (zeigt Port-Mappings)
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Prüfen, ob Host auf 4999 lauscht
ss -ltnp | grep 4999 || true

# Direktes Request vom Host (verbose)
curl -v http://127.0.0.1:4999/ --max-time 10

# Logs des Website-Containers (letzte 200 Zeilen)
docker logs --tail 200 website-website-1

# Testen von innerhalb des Containers (falls curl nicht installiert, nutze wget)
docker exec -it website-website-1 curl -v http://127.0.0.1:4999/ || \
  docker exec -it website-website-1 wget -qO- http://127.0.0.1:4999/
```

Wenn du möchtest, passe ich das Timeout oder den Health-Endpoint (`/health`) an.

Beispiel Production:

```bash
cd Website
export INSTANCE_PARENT_DOMAIN=example.de
export INSTANCE_WILDCARD_CERT_FILE=/etc/nginx/certs/wildcard.example.de.crt
export INSTANCE_WILDCARD_KEY_FILE=/etc/nginx/certs/wildcard.example.de.key
./launch_prod.sh
```

## SEO & LLM-Optimierung

Die Website ist für Suchmaschinen und LLM-Scraper optimiert:

- **Meta-Tags & OpenGraph**: Jede Seite enthält sinnvolle `<meta name="description">`, OpenGraph- und Twitter-Tags sowie einen Canonical-Link. Die Startseite und wichtige Unterseiten haben eine eigene `meta_description`.
- **JSON-LD**: Die Startseite enthält strukturierte Daten (Schema.org WebSite/Organization) als JSON-LD.
- **Maschinenlesbare Endpunkte**:
    - `/health` — gibt `{ "status": "ok", "time": ... }` zurück (Status 200), geeignet für Health-Checks und Monitoring.
    - `/sitemap.xml` — maschinenlesbare Sitemap für Suchmaschinen, dynamisch generiert.
    - `/robots.txt` — erlaubt Crawling, verweist auf Sitemap, blockiert `/admin/` und Uploads.
- **Server-Side Rendering**: Alle wichtigen Inhalte sind serverseitig gerendert und ohne JavaScript zugänglich.

**Beispiel für Health-Check:**

```bash
curl -i http://127.0.0.1:4999/health
```

**Beispiel für Sitemap:**

```bash
curl -i http://127.0.0.1:4999/sitemap.xml
```

**robots.txt Beispiel:**

    User-agent: *
    Disallow: /admin/
    Disallow: /static/uploads/
    Allow: /
    Sitemap: /sitemap.xml

**Hinweis:**
- Die SEO-Meta-Tags können pro Seite in den Templates überschrieben werden (`meta_description`).
- Die Sitemap kann bei Bedarf um weitere Seiten ergänzt werden.

## Empfohlener Ablauf

1. sudo ./gitea.sh start
2. sudo ./nginx.sh apply
3. sudo ./gitea.sh status

## Erstinstallation (automatisiert)

Für eine neue Maschine kann die Erstinstallation in einem Schritt ausgeführt werden:

```bash
sudo ./setup-first-install.sh
```

Standardmäßig macht das Skript:

1. Startet den Stack über gitea.sh.
2. Wendet nginx.sh apply an.
3. Installiert den Hosts-Sync-systemd-Service.
4. Installiert den Stack-Autostart-systemd-Service.

Optionen:

- --skip-start
- --skip-nginx
- --skip-hosts-sync
- --skip-autostart

## Quick Verify

```bash
sudo ./gitea.sh status
sudo systemctl status invario-hosts-sync --no-pager
sudo systemctl status invario-stack-autostart --no-pager
```