#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONGO_DBPATH="${MONGO_DBPATH:-$SCRIPT_DIR/data/db}"
MONGO_LOGPATH="${MONGO_LOGPATH:-$SCRIPT_DIR/data/mongod.log}"

start_mongodb_if_needed() {
    if ! command -v mongod >/dev/null 2>&1; then
        echo "Error: mongod not found. Install MongoDB first."
        exit 1
    fi

    if pgrep -x mongod >/dev/null 2>&1; then
        echo "MongoDB already running."
        return
    fi

    mkdir -p "$MONGO_DBPATH"
    echo "Starting MongoDB with dbPath: $MONGO_DBPATH"
    mongod --dbpath "$MONGO_DBPATH" --bind_ip 127.0.0.1 --port 27017 --fork --logpath "$MONGO_LOGPATH"
}

start_mongodb_if_needed

