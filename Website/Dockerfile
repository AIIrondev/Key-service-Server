FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

ARG NUITKA_JOBS=1
ARG NUITKA_LOW_MEMORY=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential patchelf \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir nuitka ordered-set zstandard

COPY . .

# Build a standalone binary with all required templates/static/data assets.
# Defaults are tuned for lower RAM pressure to avoid host crashes.
RUN set -eu; \
    EXTRA_FLAGS=""; \
    if [ "$NUITKA_LOW_MEMORY" = "1" ]; then \
        EXTRA_FLAGS="--low-memory --lto=no"; \
    fi; \
    python -m nuitka \
        --standalone \
        --follow-imports \
        --assume-yes-for-downloads \
        --jobs="$NUITKA_JOBS" \
        --remove-output \
        --include-data-dir=templates=templates \
        --include-data-dir=static=static \
        --include-data-dir=data=data \
        --output-dir=build \
        $EXTRA_FLAGS \
        main.py

FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/build/main.dist ./

EXPOSE 4999

CMD ["./main.bin"]
