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