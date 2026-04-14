FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       iproute2 \
       docker.io \
       curl \
       openssl \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN set -eu; \
        arch="$(dpkg --print-architecture)"; \
        case "$arch" in \
            amd64) compose_arch="x86_64" ;; \
            arm64) compose_arch="aarch64" ;; \
            *) echo "Unsupported architecture for compose plugin: $arch"; exit 1 ;; \
        esac; \
        curl -fsSL "https://download.docker.com/linux/static/stable/${compose_arch}/docker-27.1.1.tgz" \
            -o /tmp/docker.tgz; \
        tar -xzf /tmp/docker.tgz -C /tmp; \
        install -m 0755 /tmp/docker/docker /usr/local/bin/docker; \
        rm -rf /tmp/docker /tmp/docker.tgz; \
        mkdir -p /usr/libexec/docker/cli-plugins; \
        curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${compose_arch}" \
            -o /usr/libexec/docker/cli-plugins/docker-compose; \
        chmod +x /usr/libexec/docker/cli-plugins/docker-compose

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/provision_instance.sh

EXPOSE 4999

CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]
