# Key Service Server

Dieses Repo nutzt zwei zentrale Shell-Skripte:

- `gitea.sh`: Start/Stop/Status der Docker-Services (Gitea + Website)
- `nginx.sh`: Nginx Reverse Proxy, SSL-Zertifikate und Aktivierung/Deaktivierung der Sites

## Voraussetzungen

- Docker + Docker Compose Plugin
- Nginx
- OpenSSL
- Optional: UFW (wird automatisch fuer 80/443 konfiguriert, wenn aktiv)

## 1) Docker Services (`gitea.sh`)

Datei: [gitea.sh](gitea.sh)

### Befehle

- `sudo ./gitea.sh start`
	- Erstellt/aktualisiert Gitea Compose unter `/opt/gitea-server/docker-compose.yml`
	- Startet Gitea und Website Docker Services
	- Schreibt Runtime-Werte nach `/opt/gitea-server/runtime.env` fuer Nginx

- `sudo ./gitea.sh stop`
	- Stoppt Gitea und Website Docker Services

- `sudo ./gitea.sh restart`
	- Entspricht `stop` gefolgt von `start`

- `sudo ./gitea.sh status`
	- Zeigt laufende Container fuer Gitea/Website an

### Wichtige Ports

- Gitea intern: `127.0.0.1:3001` (fix)
- Gitea SSH: `2222`
- Website Upstream: `4999`

## 2) Nginx (`nginx.sh`)

Datei: [nginx.sh](nginx.sh)

### Befehle

- `sudo ./nginx.sh apply`
	- Liest Runtime-Werte aus `/opt/gitea-server/runtime.env`
	- Erstellt Nginx Site-Konfigurationen fuer:
		- `update.meine-domain` -> Gitea
		- `meine-domain` -> Website
	- Prueft Zertifikate im Ordner `/etc/nginx/certs`
	- Falls Zertifikate fehlen: erzeugt self-signed Zertifikate automatisch
	- Testet Nginx-Konfiguration und laedt Nginx neu

- `sudo ./nginx.sh disable`
- `sudo ./nginx.sh deactivate`
	- Deaktiviert die verwalteten Nginx Sites (`gitea`, `website`)
	- Testet und laedt Nginx neu

## Typischer Ablauf

1. Docker Services starten:

```bash
sudo ./gitea.sh start
```

2. Nginx konfigurieren/aktivieren:

```bash
sudo ./nginx.sh apply
```

3. Status pruefen:

```bash
sudo ./gitea.sh status
```

4. Nginx bei Bedarf deaktivieren:

```bash
sudo ./nginx.sh disable
```

## Nginx Templates

Die Nginx-Vorlagen liegen unter [nginx](nginx):

- [nginx/gitea.http.conf.template](nginx/gitea.http.conf.template)
- [nginx/gitea.https.conf.template](nginx/gitea.https.conf.template)
- [nginx/website.http.conf.template](nginx/website.http.conf.template)
- [nginx/website.https.conf.template](nginx/website.https.conf.template)

## Admin: Schul-Instanzen fuer Subdomains

Die Website hat jetzt eine Admin-Seite zum Starten von Inventarsystem-Instanzen pro Schule:

- Route: `/admin/instances`
- Admin-Menue: `Schul-Instanzen`
- Ziel-Repository (Standard): `https://github.com/AIIrondev/legendary-octo-garbanzo`

### Ablauf

1. Admin gibt Schulname (und optional Subdomain) ein.
2. Admin weist die Instanz einem konkreten Nutzer zu.
3. Admin wählt eine Version (Image-Tag) pro Nutzer/Instanz.
4. Admin kann das Bibliotheksmodul für die Instanz aktivieren/deaktivieren.
5. Backend ruft `provision_instance.sh` auf.
6. Skript klont/aktualisiert die Instanz unter dem Basisverzeichnis.
7. Skript startet die Instanz (`start.sh --no-cron`) und versucht eine Nginx-Site fuer die Subdomain anzulegen.
8. Status wird in MongoDB (`school_instances`) gespeichert und im Admin-Fenster angezeigt.

Hinweis: Die Zuweisung ist auf `eine Instanz pro Nutzer` begrenzt.

### Wichtige Environment-Variablen (Website)

- `INSTANCE_REPO_URL` (default: `https://github.com/AIIrondev/legendary-octo-garbanzo`)
- `INSTANCE_PARENT_DOMAIN` (default: `meine-domain`)
- `INSTANCE_BASE_DIR` (default: `/opt/inventarsystem-instances`)
- `INSTANCE_PROVISION_SCRIPT` (default: `Website/provision_instance.sh`)

### Berechtigungen

Das Provisioning-Skript fuehrt Docker- und Nginx-Operationen aus. Der Prozess, der die Website ausfuehrt, braucht daher:

- Zugriff auf `docker` (Docker Socket / Gruppe)
- Schreibrechte auf `/etc/nginx/sites-available` und `/etc/nginx/sites-enabled`
- Recht zum `nginx -t` und `nginx -s reload`

Wenn diese Rechte fehlen, wird die Instanz ggf. trotzdem gestartet, aber die Nginx-Verknuepfung muss manuell erfolgen.

### Nutzerfenster: Eigene Instanz verwalten

Eingeloggte Nutzer haben im Nutzerbereich jetzt den Punkt `Meine Instanz`.

- Route: `/my/instance`
- Funktion: Nur zugewiesene Instanz einsehen und nutzen (read-only)
- Zuordnung: ueber `owner_username`

## Admin: System-Tools

Neue Admin-Seite fuer Betriebsaufgaben:

- Route: `/admin/system`
- Funktionen:
	- Core-Services neu starten (`website`, `mongodb`)
	- Core-Logs als Datei herunterladen
	- Pro Instanz: Backup, Update, Restart
	- Pro Instanz: Logs als Datei herunterladen

## Betriebsmodi: Development und Production

Im Ordner `Website/` gibt es zwei Launcher-Skripte:

- `./launch_dev.sh`
	- setzt `INSTANCE_TLS_MODE=development`
	- erzeugt pro Subdomain self-signed Zertifikate (wenn moeglich)
	- setzt `SESSION_COOKIE_SECURE=0`

- `./launch_prod.sh`
	- setzt `INSTANCE_TLS_MODE=production`
	- nutzt Wildcard-Zertifikat ueber:
		- `INSTANCE_WILDCARD_CERT_FILE`
		- `INSTANCE_WILDCARD_KEY_FILE`
	- setzt `SESSION_COOKIE_SECURE=1`

Beispiel Production-Start mit eigener Domain:

```bash
cd Website
export INSTANCE_PARENT_DOMAIN=example.de
export INSTANCE_WILDCARD_CERT_FILE=/etc/nginx/certs/wildcard.example.de.crt
export INSTANCE_WILDCARD_KEY_FILE=/etc/nginx/certs/wildcard.example.de.key
./launch_prod.sh
```