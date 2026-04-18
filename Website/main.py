from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, get_flashed_messages, session, send_file, after_this_request
import os
import json
import atexit
import calendar
import re
import subprocess
import hashlib
import shutil
import tarfile
import tempfile
import threading
from datetime import timedelta, datetime, date
from functools import wraps
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import bleach
from markupsafe import escape
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
import user as user_store

app = Flask(__name__)
app.secret_key = "ASDfhbsdfseiufhgildsrfrjg874368546987s6e8468f4s"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PREFERRED_URL_SCHEME"] = "https" if os.environ.get("SESSION_COOKIE_SECURE") == "1" else "http"


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; img-src 'self' data:; connect-src 'self';"
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVOICE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "invoices")
TEAM_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "team")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "Invario_Website")
INSTANCE_REPO_URL = os.environ.get("INSTANCE_REPO_URL", "https://github.com/AIIrondev/legendary-octo-garbanzo")
INSTANCE_PARENT_DOMAIN = os.environ.get("INSTANCE_PARENT_DOMAIN", "meine-domain")
INSTANCE_BASE_DIR = os.environ.get("INSTANCE_BASE_DIR", "/opt/inventarsystem-instances")
INSTANCE_TLS_MODE = os.environ.get("INSTANCE_TLS_MODE", "development")
INSTANCE_VERSION_OPTIONS = os.environ.get("INSTANCE_VERSION_OPTIONS", "latest,v0.3.1")
INSTANCE_WILDCARD_CERT_FILE = os.environ.get(
    "INSTANCE_WILDCARD_CERT_FILE",
    "/etc/nginx/certs/wildcard.meine-domain.crt",
)
INSTANCE_WILDCARD_KEY_FILE = os.environ.get(
    "INSTANCE_WILDCARD_KEY_FILE",
    "/etc/nginx/certs/wildcard.meine-domain.key",
)
INSTANCE_PROVISION_SCRIPT = os.environ.get(
    "INSTANCE_PROVISION_SCRIPT",
    os.path.abspath(os.path.join(BASE_DIR, "provision_instance.sh")),
)


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


MONGO_MAX_POOL_SIZE = max(_env_int("MONGO_MAX_POOL_SIZE", 12), 1)
MONGO_MIN_POOL_SIZE = max(_env_int("MONGO_MIN_POOL_SIZE", 0), 0)
MONGO_MAX_IDLE_MS = max(_env_int("MONGO_MAX_IDLE_MS", 60000), 1000)
MONGO_CONNECT_TIMEOUT_MS = max(_env_int("MONGO_CONNECT_TIMEOUT_MS", 1500), 500)
MONGO_SOCKET_TIMEOUT_MS = max(_env_int("MONGO_SOCKET_TIMEOUT_MS", 30000), 1000)
MONGO_WAIT_QUEUE_TIMEOUT_MS = max(_env_int("MONGO_WAIT_QUEUE_TIMEOUT_MS", 2000), 500)

_MONGO_CLIENT: MongoClient | None = None
_MONGO_LOCK = threading.Lock()


class _NoopMongoClientHandle:
    def close(self):
        # Backward-compatible no-op so existing finally blocks stay harmless.
        return None


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _is_allowed_invoice_filename(filename: str) -> bool:
    return bool(filename) and filename.lower().endswith(".pdf")


def _is_allowed_image_filename(filename: str) -> bool:
    if not filename:
        return False
    lowered = filename.lower()
    return lowered.endswith(".jpg") or lowered.endswith(".jpeg") or lowered.endswith(".png") or lowered.endswith(".webp")


def _save_invoice_pdf(file_obj, invoice_number: str) -> str | None:
    if not file_obj or not file_obj.filename:
        return None
    original_name = secure_filename(file_obj.filename)
    if not _is_allowed_invoice_filename(original_name):
        return None
    os.makedirs(INVOICE_UPLOAD_DIR, exist_ok=True)
    safe_invoice = secure_filename(invoice_number or "invoice")
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_invoice}_{original_name}"
    target = os.path.join(INVOICE_UPLOAD_DIR, unique_name)
    file_obj.save(target)
    return f"uploads/invoices/{unique_name}"


def _save_team_photo(file_obj, identifier: str) -> str | None:
    if not file_obj or not file_obj.filename:
        return None
    original_name = secure_filename(file_obj.filename)
    if not _is_allowed_image_filename(original_name):
        return None
    os.makedirs(TEAM_UPLOAD_DIR, exist_ok=True)
    extension = os.path.splitext(original_name)[1].lower() or ".jpg"
    safe_identifier = secure_filename(identifier or "member")
    unique_name = f"team_{safe_identifier}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{extension}"
    target = os.path.join(TEAM_UPLOAD_DIR, unique_name)
    file_obj.save(target)
    return f"uploads/team/{unique_name}"


def _get_mongo_client() -> MongoClient:
    global _MONGO_CLIENT
    if _MONGO_CLIENT is not None:
        return _MONGO_CLIENT

    with _MONGO_LOCK:
        if _MONGO_CLIENT is None:
            _MONGO_CLIENT = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=MONGO_CONNECT_TIMEOUT_MS,
                connectTimeoutMS=MONGO_CONNECT_TIMEOUT_MS,
                socketTimeoutMS=MONGO_SOCKET_TIMEOUT_MS,
                maxPoolSize=MONGO_MAX_POOL_SIZE,
                minPoolSize=MONGO_MIN_POOL_SIZE,
                maxIdleTimeMS=MONGO_MAX_IDLE_MS,
                waitQueueTimeoutMS=MONGO_WAIT_QUEUE_TIMEOUT_MS,
            )
    return _MONGO_CLIENT


@atexit.register
def _shutdown_mongo_client() -> None:
    global _MONGO_CLIENT
    client = _MONGO_CLIENT
    _MONGO_CLIENT = None
    if client is not None:
        client.close()


def _get_mongo_db():
    client = _get_mongo_client()
    return _NoopMongoClientHandle(), client[MONGO_DB_NAME]


def _normalize_user_doc(doc: dict | None) -> dict | None:
    if not doc:
        return None
    return {
        "username": doc.get("Username") or doc.get("username"),
        "display_name": doc.get("name") or doc.get("display_name") or doc.get("Username"),
        "is_admin": bool(doc.get("Admin") or doc.get("is_admin", False)),
        "created_at": doc.get("created_at"),
    }


def _get_collection(name: str):
    client, db = _get_mongo_db()
    return client, db[name]


def _list_users_for_admin() -> list:
    docs = user_store.get_all_users() or []
    users = []
    for doc in docs:
        normalized = _normalize_user_doc(doc)
        if normalized and normalized.get("username"):
            users.append(normalized)
    users.sort(key=lambda item: (item.get("is_admin", False), item.get("username", "")), reverse=True)
    return users


def _sanitize_text(text: str, max_length: int = 255) -> str:
    """Sanitize user text input: strip, limit length, and escape HTML."""
    text = (text or "").strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text


def _slugify_subdomain(value: str) -> str:
    cleaned = (value or "").strip().lower()
    cleaned = cleaned.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    cleaned = re.sub(r"[^a-z0-9-]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned[:63]


def _is_valid_subdomain(value: str) -> bool:
    if not value or len(value) < 3 or len(value) > 63:
        return False
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])", value))


def _parse_key_value_output(raw: str) -> dict:
    parsed = {}
    for line in (raw or "").splitlines():
        row = line.strip()
        if not row or "=" not in row:
            continue
        key, value = row.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _parse_instance_version_options() -> list[str]:
    values = []
    for item in (INSTANCE_VERSION_OPTIONS or "").split(","):
        token = _sanitize_text(item or "", 80)
        if token and token not in values:
            values.append(token)
    if not values:
        values = ["latest"]
    return values


def _list_school_instances() -> list:
    rows = []
    client = None
    try:
        client, col = _get_collection("school_instances")
        rows = list(col.find().sort([("updated_at", -1), ("created_at", -1)]))
    except PyMongoError:
        return []
    finally:
        if client:
            client.close()

    normalized = []
    for row in rows:
        normalized.append(
            {
                "id": str(row.get("_id") or ""),
                "school_name": _sanitize_text(row.get("school_name") or "", 120),
                "owner_username": _sanitize_text(row.get("owner_username") or "", 80),
                "subdomain": _sanitize_text(row.get("subdomain") or "", 63),
                "domain": _sanitize_text(row.get("domain") or "", 190),
                "https_port": int(row.get("https_port") or 0),
                "instance_dir": _sanitize_text(row.get("instance_dir") or "", 300),
                "app_image_tag": _sanitize_text(row.get("app_image_tag") or "latest", 80),
                "library_enabled": bool(row.get("library_enabled", False)),
                "status": _sanitize_text(row.get("status") or "Unbekannt", 40),
                "nginx_status": _sanitize_text(row.get("nginx_status") or "unbekannt", 80),
                "last_message": _sanitize_text(row.get("last_message") or "", 500),
                "updated_at": row.get("updated_at") or "",
            }
        )
    return normalized


def _list_available_instance_users() -> list:
    users = _list_users_for_admin()
    instances = _list_school_instances()
    assigned = {
        _sanitize_text(item.get("owner_username") or "", 80).lower()
        for item in instances
        if _sanitize_text(item.get("owner_username") or "", 80)
    }
    return [u for u in users if _sanitize_text(u.get("username") or "", 80).lower() not in assigned]


def _list_instances_grouped_by_owner() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in _list_school_instances():
        owner = _sanitize_text(item.get("owner_username") or "", 80)
        domain = _sanitize_text(item.get("domain") or "", 190)
        subdomain = _sanitize_text(item.get("subdomain") or "", 63)
        if not owner or not domain:
            continue
        grouped.setdefault(owner, []).append(
            {
                "domain": domain,
                "subdomain": subdomain,
                "status": _sanitize_text(item.get("status") or "", 40),
            }
        )
    return grouped


def _parse_iso_timestamp(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _build_instance_dashboard(instances: list[dict]) -> dict:
    total = len(instances)
    running = len([item for item in instances if _sanitize_text(item.get("status") or "", 40) == "Läuft"])
    error = len(
        [
            item
            for item in instances
            if _sanitize_text(item.get("status") or "", 40) == "Fehler"
            or _sanitize_text(item.get("nginx_status") or "", 80).lower() == "error"
        ]
    )
    library_on = len([item for item in instances if bool(item.get("library_enabled"))])
    assigned_users = len(
        {
            _sanitize_text(item.get("owner_username") or "", 80)
            for item in instances
            if _sanitize_text(item.get("owner_username") or "", 80)
        }
    )

    version_counts: dict[str, int] = {}
    owner_counts: dict[str, int] = {}
    for item in instances:
        version = _sanitize_text(item.get("app_image_tag") or "latest", 80) or "latest"
        owner = _sanitize_text(item.get("owner_username") or "Unzugewiesen", 80) or "Unzugewiesen"
        version_counts[version] = version_counts.get(version, 0) + 1
        owner_counts[owner] = owner_counts.get(owner, 0) + 1

    version_items = sorted(version_counts.items(), key=lambda row: row[1], reverse=True)
    owner_items = sorted(owner_counts.items(), key=lambda row: row[1], reverse=True)[:8]

    day_keys = []
    today = date.today()
    for back in range(6, -1, -1):
        day_keys.append((today - timedelta(days=back)).isoformat())
    updates_by_day = {day: 0 for day in day_keys}

    for item in instances:
        parsed = _parse_iso_timestamp(_sanitize_text(item.get("updated_at") or "", 40))
        if not parsed:
            continue
        day_key = parsed.date().isoformat()
        if day_key in updates_by_day:
            updates_by_day[day_key] += 1

    labels = [datetime.fromisoformat(day).strftime("%d.%m") for day in day_keys]
    values = [updates_by_day[day] for day in day_keys]

    return {
        "kpis": {
            "total": total,
            "running": running,
            "error": error,
            "library_on": library_on,
            "assigned_users": assigned_users,
        },
        "status": {
            "labels": ["Läuft", "Fehler", "Sonstige"],
            "values": [running, error, max(total - running - error, 0)],
        },
        "library": {
            "labels": ["Aktiv", "Inaktiv"],
            "values": [library_on, max(total - library_on, 0)],
        },
        "versions": {
            "labels": [item[0] for item in version_items],
            "values": [item[1] for item in version_items],
        },
        "owners": {
            "labels": [item[0] for item in owner_items],
            "values": [item[1] for item in owner_items],
        },
        "activity": {
            "labels": labels,
            "values": values,
        },
    }


def _parse_size_to_mib(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0

    match = re.match(r"^([0-9]*\.?[0-9]+)\s*([kmgt]?i?b)$", text.lower())
    if not match:
        return 0.0

    number = float(match.group(1))
    unit = match.group(2)
    factor_map = {
        "b": 1.0 / (1024.0 * 1024.0),
        "kib": 1.0 / 1024.0,
        "kb": 1.0 / 1024.0,
        "mib": 1.0,
        "mb": 1.0,
        "gib": 1024.0,
        "gb": 1024.0,
        "tib": 1024.0 * 1024.0,
        "tb": 1024.0 * 1024.0,
    }
    return number * factor_map.get(unit, 0.0)


def _read_meminfo_mib() -> tuple[float, float]:
    total_kib = 0.0
    available_kib = 0.0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for row in handle:
                if row.startswith("MemTotal:"):
                    total_kib = float(row.split()[1])
                elif row.startswith("MemAvailable:"):
                    available_kib = float(row.split()[1])
    except Exception:
        return 0.0, 0.0
    return total_kib / 1024.0, available_kib / 1024.0


def _collect_runtime_stats(instances: list[dict]) -> dict:
    ok, output = _run_command(
        ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
        timeout=120,
    )

    container_stats = {}
    total_used_mib = 0.0

    if ok:
        for row in (output or "").splitlines():
            line = row.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue

            name = parts[0].strip()
            cpu_raw = parts[1].strip().replace("%", "")
            mem_raw = parts[2].strip()
            used_raw = mem_raw.split("/")[0].strip() if "/" in mem_raw else mem_raw

            try:
                cpu_percent = float(cpu_raw) if cpu_raw else 0.0
            except ValueError:
                cpu_percent = 0.0

            mem_mib = _parse_size_to_mib(used_raw)
            total_used_mib += mem_mib
            container_stats[name] = {
                "cpu_percent": round(cpu_percent, 2),
                "mem_mib": round(mem_mib, 2),
                "mem_raw": mem_raw,
            }

    managed_prefixes = [f"{_sanitize_text(item.get('subdomain') or '', 63)}-" for item in instances if _sanitize_text(item.get('subdomain') or '', 63)]
    managed_prefixes.append("website-")

    managed_container_stats = {
        name: stats
        for name, stats in container_stats.items()
        if any(name.startswith(prefix) for prefix in managed_prefixes)
    }

    managed_used_mib = round(sum(item.get("mem_mib", 0.0) for item in managed_container_stats.values()), 2)

    per_instance = []
    for item in instances:
        subdomain = _sanitize_text(item.get("subdomain") or "", 63)
        domain = _sanitize_text(item.get("domain") or "", 190)
        if not subdomain:
            continue

        prefix = f"{subdomain}-"
        related = []
        for container_name, stats in container_stats.items():
            if container_name.startswith(prefix):
                related.append({"name": container_name, **stats})

        mem_sum = round(sum(entry.get("mem_mib", 0.0) for entry in related), 2)
        cpu_sum = round(sum(entry.get("cpu_percent", 0.0) for entry in related), 2)
        per_instance.append(
            {
                "subdomain": subdomain,
                "domain": domain,
                "status": _sanitize_text(item.get("status") or "Unbekannt", 40),
                "nginx_status": _sanitize_text(item.get("nginx_status") or "unbekannt", 80),
                "containers": related,
                "container_count": len(related),
                "mem_mib": mem_sum,
                "cpu_percent": cpu_sum,
            }
        )

    per_instance.sort(key=lambda row: row.get("mem_mib", 0.0), reverse=True)
    total_mem_mib, available_mem_mib = _read_meminfo_mib()
    used_mem_mib = max(total_mem_mib - available_mem_mib, 0.0)
    used_mem_pct = (used_mem_mib / total_mem_mib * 100.0) if total_mem_mib > 0 else 0.0

    return {
        "generated_at": _utc_now_iso(),
        "host": {
            "total_mem_mib": round(total_mem_mib, 2),
            "available_mem_mib": round(available_mem_mib, 2),
            "used_mem_mib": round(used_mem_mib, 2),
            "used_mem_pct": round(used_mem_pct, 2),
        },
        "docker": {
            "all_container_count": len(container_stats),
            "all_used_mem_mib": round(total_used_mib, 2),
            "managed_container_count": len(managed_container_stats),
            "managed_used_mem_mib": managed_used_mib,
        },
        "instances": per_instance,
    }


def _read_uptime_load() -> dict:
    uptime_seconds = 0.0
    load_1 = 0.0
    load_5 = 0.0
    load_15 = 0.0

    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            uptime_seconds = float((handle.read().strip().split() or ["0"])[0])
    except Exception:
        uptime_seconds = 0.0

    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as handle:
            parts = handle.read().strip().split()
            load_1 = float(parts[0])
            load_5 = float(parts[1])
            load_15 = float(parts[2])
    except Exception:
        pass

    return {
        "uptime_seconds": round(uptime_seconds, 1),
        "load_1": round(load_1, 2),
        "load_5": round(load_5, 2),
        "load_15": round(load_15, 2),
    }


def _read_disk_usage(path: str) -> dict:
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return {"path": path, "total_gib": 0.0, "used_gib": 0.0, "free_gib": 0.0, "used_pct": 0.0}

    total_gib = usage.total / (1024.0 ** 3)
    used_gib = usage.used / (1024.0 ** 3)
    free_gib = usage.free / (1024.0 ** 3)
    used_pct = (used_gib / total_gib * 100.0) if total_gib > 0 else 0.0
    return {
        "path": path,
        "total_gib": round(total_gib, 2),
        "used_gib": round(used_gib, 2),
        "free_gib": round(free_gib, 2),
        "used_pct": round(used_pct, 2),
    }


def _collect_ops_counts() -> dict:
    appointments_pending = 0
    tickets_open = 0
    users_total = 0

    client = None
    try:
        client, col = _get_collection("appointments")
        appointments_pending = col.count_documents({"status": "Angefragt"})
    except PyMongoError:
        appointments_pending = 0
    finally:
        if client:
            client.close()

    client = None
    try:
        client, col = _get_collection("support_tickets")
        tickets_open = col.count_documents({"status": {"$in": ["Offen", "In Bearbeitung"]}})
    except PyMongoError:
        tickets_open = 0
    finally:
        if client:
            client.close()

    try:
        users_total = len(_list_users_for_admin())
    except Exception:
        users_total = 0

    return {
        "appointments_pending": appointments_pending,
        "tickets_open": tickets_open,
        "users_total": users_total,
    }


def _build_server_management_snapshot(instances: list[dict]) -> dict:
    runtime = _collect_runtime_stats(instances)
    root_disk = _read_disk_usage("/")
    instance_disk = _read_disk_usage(INSTANCE_BASE_DIR)
    ops_counts = _collect_ops_counts()
    uptime_load = _read_uptime_load()

    return {
        "generated_at": _utc_now_iso(),
        "runtime": runtime,
        "root_disk": root_disk,
        "instance_disk": instance_disk,
        "ops": ops_counts,
        "system": uptime_load,
    }


def _upsert_school_instance(data: dict) -> None:
    subdomain = _sanitize_text(data.get("subdomain") or "", 63)
    if not subdomain:
        return

    client = None
    try:
        client, col = _get_collection("school_instances")
        existing = col.find_one({"subdomain": subdomain}) or {}

        def _pick_text(field: str, max_len: int, fallback: str = "") -> str:
            if field in data:
                raw = data.get(field)
                if raw is not None and (not isinstance(raw, str) or raw.strip()):
                    return _sanitize_text(raw, max_len)
            return _sanitize_text(existing.get(field) or fallback, max_len)

        def _pick_int(field: str, fallback: int = 0) -> int:
            if field in data:
                raw = data.get(field)
                if raw not in (None, ""):
                    try:
                        return int(raw)
                    except (TypeError, ValueError):
                        pass
            try:
                return int(existing.get(field) or fallback)
            except (TypeError, ValueError):
                return fallback

        if "library_enabled" in data:
            library_enabled = bool(data.get("library_enabled", False))
        else:
            library_enabled = bool(existing.get("library_enabled", False))

        payload = {
            "school_name": _pick_text("school_name", 120),
            "owner_username": _pick_text("owner_username", 80),
            "subdomain": subdomain,
            "domain": _pick_text("domain", 190),
            "https_port": _pick_int("https_port", 0),
            "instance_dir": _pick_text("instance_dir", 300),
            "app_image_tag": _pick_text("app_image_tag", 80, "latest") or "latest",
            "library_enabled": library_enabled,
            "status": _pick_text("status", 40, "Unbekannt") or "Unbekannt",
            "nginx_status": _pick_text("nginx_status", 80, "unbekannt") or "unbekannt",
            "last_message": _pick_text("last_message", 500),
            "updated_at": _utc_now_iso(),
        }

        col.update_one(
            {"subdomain": subdomain},
            {"$set": payload, "$setOnInsert": {"created_at": _utc_now_iso()}},
            upsert=True,
        )
    except PyMongoError:
        return
    finally:
        if client:
            client.close()


def _run_instance_provision(
    action: str,
    school_name: str,
    subdomain: str,
    app_image_tag: str = "latest",
    library_enabled: bool = False,
) -> tuple[bool, str, dict]:
    script_path = (INSTANCE_PROVISION_SCRIPT or "").strip()
    if not script_path:
        return False, "INSTANCE_PROVISION_SCRIPT ist nicht gesetzt.", {}

    if not os.path.isfile(script_path):
        return False, f"Provisioning-Skript nicht gefunden: {script_path}", {}

    if not os.access(script_path, os.X_OK):
        return False, f"Provisioning-Skript ist nicht ausführbar: {script_path}", {}

    command = [
        script_path,
        "--action",
        action,
        "--repo",
        INSTANCE_REPO_URL,
        "--base-dir",
        INSTANCE_BASE_DIR,
        "--domain",
        INSTANCE_PARENT_DOMAIN,
        "--tls-mode",
        INSTANCE_TLS_MODE,
        "--wildcard-cert-file",
        INSTANCE_WILDCARD_CERT_FILE,
        "--wildcard-key-file",
        INSTANCE_WILDCARD_KEY_FILE,
        "--app-image-tag",
        _sanitize_text(app_image_tag or "latest", 80),
        "--library-enabled",
        "1" if library_enabled else "0",
        "--school-name",
        school_name,
        "--subdomain",
        subdomain,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            env={**os.environ, "LC_ALL": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired:
        return False, "Provisioning-Zeitlimit erreicht (15 Minuten).", {}
    except Exception as exc:
        return False, f"Provisioning konnte nicht gestartet werden: {exc}", {}

    output = _parse_key_value_output(result.stdout)
    message = output.get("MESSAGE") or output.get("ERROR") or (result.stderr or "").strip()

    if result.returncode != 0:
        if not message:
            message = "Provisioning fehlgeschlagen. Details im Server-Log prüfen."
        return False, message, output

    return True, message or "Instanz erfolgreich gestartet.", output


def _instance_dir_path(subdomain: str) -> str | None:
    key = _sanitize_text(subdomain or "", 63)
    if not _is_valid_subdomain(key):
        return None

    target = os.path.abspath(os.path.join(INSTANCE_BASE_DIR, key))
    base_abs = os.path.abspath(INSTANCE_BASE_DIR)
    if not target.startswith(base_abs + os.sep):
        return None
    return target


def _resolve_instance_dir(subdomain: str) -> str | None:
    key = _sanitize_text(subdomain or "", 63)
    if not _is_valid_subdomain(key):
        return None

    target = os.path.abspath(os.path.join(INSTANCE_BASE_DIR, key))
    base_abs = os.path.abspath(INSTANCE_BASE_DIR)
    if not target.startswith(base_abs + os.sep):
        return None
    if not os.path.isdir(target):
        return None
    return target


def _run_command(command: list[str], cwd: str | None = None, timeout: int = 900) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "LC_ALL": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired:
        return False, "Befehl hat das Zeitlimit erreicht."
    except Exception as exc:
        return False, f"Befehl konnte nicht ausgeführt werden: {exc}"

    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if result.returncode != 0:
        return False, output or "Befehl ist fehlgeschlagen."
    return True, output or "OK"


def _instance_compose_file(instance_dir: str) -> str | None:
    preferred = os.path.join(instance_dir, "docker-compose-multitenant.yml")
    fallback = os.path.join(instance_dir, "docker-compose.yml")

    if os.path.isfile(preferred):
        return preferred
    if os.path.isfile(fallback):
        return fallback
    return None


def _instance_compose_cmd(instance_dir: str, args: list[str]) -> list[str] | None:
    compose_file = _instance_compose_file(instance_dir)
    if not compose_file:
        return None

    cmd = ["docker", "compose", "-f", compose_file]
    env_file = os.path.join(instance_dir, ".docker-build.env")
    if os.path.isfile(env_file):
        cmd.extend(["--env-file", ".docker-build.env"])
    cmd.extend(args)
    return cmd


def _collect_command_candidates(base_binaries: list[str], args: list[str]) -> list[list[str]]:
    candidates: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    has_sudo = shutil.which("sudo") is not None

    for binary in base_binaries:
        resolved = ""
        if "/" in binary:
            if os.path.isfile(binary) and os.access(binary, os.X_OK):
                resolved = binary
        else:
            found = shutil.which(binary)
            if found:
                resolved = found

        if not resolved:
            continue

        regular = tuple([resolved, *args])
        if regular not in seen:
            candidates.append(list(regular))
            seen.add(regular)

        if has_sudo:
            privileged = tuple(["sudo", resolved, *args])
            if privileged not in seen:
                candidates.append(list(privileged))
                seen.add(privileged)

    return candidates


def _reload_host_nginx() -> tuple[bool, str]:
    test_candidates = _collect_command_candidates(
        ["nginx", "/usr/sbin/nginx", "/usr/bin/nginx"],
        ["-t"],
    )
    if test_candidates:
        test_errors: list[str] = []
        test_ok = False
        for command in test_candidates:
            ok, output = _run_command(command, timeout=60)
            if ok:
                test_ok = True
                break
            test_errors.append(f"{' '.join(command)} -> {_tail_output(output, 3)}")
        if not test_ok:
            details = " | ".join(test_errors[-2:]) if test_errors else "Kein Detail vorhanden."
            return False, f"Nginx-Konfigurationstest fehlgeschlagen. {details}"

    reload_candidates: list[list[str]] = []
    reload_candidates.extend(
        _collect_command_candidates(
            ["nginx", "/usr/sbin/nginx", "/usr/bin/nginx"],
            ["-s", "reload"],
        )
    )
    reload_candidates.extend(_collect_command_candidates(["systemctl"], ["reload", "nginx"]))

    if not reload_candidates:
        return False, "Kein Nginx-Reload-Befehl verfügbar (nginx/systemctl nicht gefunden)."

    reload_errors: list[str] = []
    for command in reload_candidates:
        ok, output = _run_command(command, timeout=60)
        if ok:
            return True, f"Nginx neu geladen via: {' '.join(command)}"
        reload_errors.append(f"{' '.join(command)} -> {_tail_output(output, 3)}")

    details = " | ".join(reload_errors[-2:]) if reload_errors else "Kein Detail vorhanden."
    return False, f"Nginx-Reload fehlgeschlagen. {details}"


def _host_reload_hint() -> str:
    return "Bitte auf dem Host ausführen: sudo nginx -t && sudo systemctl reload nginx"


def _promote_manual_nginx_status(reload_message: str) -> int:
    client = None
    try:
        client, col = _get_collection("school_instances")
        result = col.update_many(
            {"nginx_status": "manual_required"},
            {
                "$set": {
                    "nginx_status": "ok",
                    "last_message": _sanitize_text(reload_message, 500),
                    "updated_at": _utc_now_iso(),
                }
            },
        )
        return int(result.modified_count or 0)
    except PyMongoError:
        return 0
    finally:
        if client:
            client.close()


def _tail_output(text: str, lines: int = 24) -> str:
    rows = [line for line in (text or "").splitlines() if line.strip()]
    if not rows:
        return "Keine Ausgabe"
    return "\n".join(rows[-lines:])


def _collect_core_logs() -> tuple[bool, str]:
    compose_file = os.path.join(BASE_DIR, "docker-compose.yml")
    command = [
        "docker",
        "compose",
        "-f",
        compose_file,
        "logs",
        "--no-color",
        "--tail",
        "500",
        "website",
        "mongodb",
    ]
    return _run_command(command, cwd=BASE_DIR, timeout=180)


def _truncate_log_blob(text: str, max_lines: int = 220, max_chars: int = 32000) -> str:
    rows = (text or "").splitlines()
    if len(rows) > max_lines:
        rows = rows[-max_lines:]
    clipped = "\n".join(rows).strip()
    if len(clipped) > max_chars:
        clipped = clipped[-max_chars:]
    return clipped or "Keine Ausgabe"


def _run_first_success(candidates: list[list[str]], cwd: str | None = None, timeout: int = 120) -> tuple[bool, str, str]:
    if not candidates:
        return False, "Kein Befehl verfügbar.", ""

    failures: list[str] = []
    for command in candidates:
        ok, output = _run_command(command, cwd=cwd, timeout=timeout)
        if ok:
            return True, output, " ".join(command)
        failures.append(f"{' '.join(command)} -> {_tail_output(output, 3)}")

    return False, " | ".join(failures[-2:]) if failures else "Kein Detail vorhanden.", ""


def _collect_core_live_logs(lines: int = 220) -> dict:
    compose_file = os.path.join(BASE_DIR, "docker-compose.yml")
    command = [
        "docker",
        "compose",
        "-f",
        compose_file,
        "logs",
        "--no-color",
        "--tail",
        str(max(lines, 20)),
        "website",
        "mongodb",
    ]
    ok, output = _run_command(command, cwd=BASE_DIR, timeout=180)
    return {
        "ok": ok,
        "label": "Docker Compose (website, mongodb)",
        "logs": _truncate_log_blob(output),
    }


def _collect_systemd_service_snapshot(service_name: str, lines: int = 160) -> dict:
    status_ok, status_out, status_cmd = _run_first_success(
        _collect_command_candidates(["systemctl"], ["is-active", service_name]),
        timeout=60,
    )
    status = (status_out or "").strip().splitlines()[-1] if status_ok else "unavailable"

    logs_ok, logs_out, logs_cmd = _run_first_success(
        _collect_command_candidates(
            ["journalctl"],
            ["-u", service_name, "--no-pager", "-n", str(max(lines, 40))],
        ),
        timeout=120,
    )

    if logs_ok:
        logs_text = _truncate_log_blob(logs_out)
    else:
        logs_text = _truncate_log_blob(f"Service-Logs konnten nicht geladen werden.\n{logs_out}")

    return {
        "service": service_name,
        "status": status,
        "status_ok": status_ok,
        "status_command": status_cmd,
        "logs_ok": logs_ok,
        "logs_command": logs_cmd,
        "logs": logs_text,
    }


def _collect_homepage_service_logs() -> dict:
    services = [
        "invario-hosts-sync.service",
        "invario-stack-autostart.service",
        "nginx.service",
    ]
    snapshots = [_collect_systemd_service_snapshot(service) for service in services]
    return {
        "generated_at": _utc_now_iso(),
        "core": _collect_core_live_logs(),
        "services": snapshots,
    }


def _collect_instance_logs(subdomain: str) -> tuple[bool, str]:
    instance_dir = _resolve_instance_dir(subdomain)
    if not instance_dir:
        return False, "Instanzverzeichnis nicht gefunden."

    command = _instance_compose_cmd(
        instance_dir,
        ["logs", "--no-color", "--tail", "500"],
    )
    if not command:
        return False, "Compose-Datei der Instanz wurde nicht gefunden."

    return _run_command(command, cwd=instance_dir, timeout=180)


SLIM_BACKUP_EXCLUDE_DIRS = {
    ".git",
    ".github",
    "logs",
    "certs",
    "test-data",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
    "tmp",
    "temp",
}

SLIM_BACKUP_EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
}

SLIM_BACKUP_EXCLUDE_SUFFIXES = (
    ".log",
    ".tmp",
    ".cache",
    ".pid",
)


def _is_excluded_from_slim_backup(rel_path: str, is_dir: bool) -> bool:
    parts = [p for p in rel_path.split(os.sep) if p and p != "."]
    if not parts:
        return False

    if any(part in SLIM_BACKUP_EXCLUDE_DIRS for part in parts):
        return True

    name = parts[-1]
    if not is_dir and name in SLIM_BACKUP_EXCLUDE_FILES:
        return True

    if not is_dir and name.lower().endswith(SLIM_BACKUP_EXCLUDE_SUFFIXES):
        return True

    return False


def _build_instance_backup_archive(subdomain: str) -> tuple[bool, str, str | None]:
    instance_dir = _resolve_instance_dir(subdomain)
    if not instance_dir:
        return False, "Instanzverzeichnis nicht gefunden.", None

    safe_name = _slugify_subdomain(subdomain)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    archive_path = os.path.join(tempfile.gettempdir(), f"instance-backup-{safe_name}-{stamp}.tar.gz")

    try:
        with tarfile.open(archive_path, "w:gz") as tf:
            for root, dirs, files in os.walk(instance_dir):
                rel_root = os.path.relpath(root, instance_dir)
                if rel_root == ".":
                    rel_root = ""

                kept_dirs = []
                for dirname in dirs:
                    rel_dir = os.path.join(rel_root, dirname) if rel_root else dirname
                    if _is_excluded_from_slim_backup(rel_dir, is_dir=True):
                        continue
                    kept_dirs.append(dirname)
                dirs[:] = kept_dirs

                for filename in files:
                    rel_file = os.path.join(rel_root, filename) if rel_root else filename
                    if _is_excluded_from_slim_backup(rel_file, is_dir=False):
                        continue
                    full_path = os.path.join(root, filename)
                    tf.add(full_path, arcname=rel_file)
    except Exception as exc:
        return False, f"Backup-Archiv konnte nicht erstellt werden: {exc}", None

    filename = f"instance-{safe_name}-slim-backup-{stamp}.tar.gz"
    return True, filename, archive_path


def _safe_extract_tar_archive(archive_path: str, target_dir: str) -> tuple[bool, str]:
    target_abs = os.path.abspath(target_dir)

    try:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                member_path = os.path.abspath(os.path.join(target_abs, member.name))
                if not member_path.startswith(target_abs + os.sep) and member_path != target_abs:
                    return False, "Unsicherer Pfad im Backup-Archiv erkannt."
            tf.extractall(path=target_abs)
    except Exception as exc:
        return False, f"Backup konnte nicht entpackt werden: {exc}"

    return True, "Backup erfolgreich entpackt."


def _set_instance_library_enabled(instance_dir: str, enabled: bool) -> tuple[bool, str]:
    config_path = os.path.join(instance_dir, "config.json")
    if not os.path.isfile(config_path):
        return False, "config.json nicht gefunden."

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except Exception as exc:
        return False, f"config.json konnte nicht gelesen werden: {exc}"

    modules = config.get("modules")
    if not isinstance(modules, dict):
        modules = {}
        config["modules"] = modules

    library = modules.get("library")
    if not isinstance(library, dict):
        library = {}
        modules["library"] = library

    library["enabled"] = bool(enabled)

    try:
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except Exception as exc:
        return False, f"config.json konnte nicht geschrieben werden: {exc}"

    return True, "Bibliothekseinstellung gespeichert."


def _restart_instance_stack(instance_dir: str) -> tuple[bool, str]:
    restart_cmd = _instance_compose_cmd(instance_dir, ["restart", "app", "nginx", "mongodb", "redis"])
    if not restart_cmd:
        return False, "Compose-Datei der Instanz wurde nicht gefunden."

    up_cmd = _instance_compose_cmd(instance_dir, ["up", "-d", "--remove-orphans"])
    if not up_cmd:
        return False, "Compose-Datei der Instanz wurde nicht gefunden."

    # restart may fail for stopped services; ensure desired state with up -d afterwards.
    _run_command(restart_cmd, cwd=instance_dir, timeout=420)

    ok, output = _run_command(up_cmd, cwd=instance_dir, timeout=900)
    if ok:
        return True, output

    # Missing app image is a common restart failure after tag changes.
    if "local app image not found" in (output or "").lower() and os.path.isfile(os.path.join(instance_dir, "update.sh")):
        upd_ok, upd_out = _run_command(["bash", "./update.sh"], cwd=instance_dir, timeout=2400)
        if upd_ok:
            ok2, out2 = _run_command(up_cmd, cwd=instance_dir, timeout=900)
            if ok2:
                return True, f"{upd_out}\n{out2}".strip()
            return False, out2
        return False, upd_out

    return False, output


def _delete_instance_stack(subdomain: str) -> tuple[bool, str]:
    target_dir = _instance_dir_path(subdomain)
    if not target_dir:
        return False, "Ungültige Subdomain für Löschung."

    details: list[str] = []

    if os.path.isdir(target_dir):
        compose_file = _instance_compose_file(target_dir)
        if compose_file:
            down_cmd = _instance_compose_cmd(
                target_dir,
                ["down", "--remove-orphans", "--volumes", "--timeout", "40"],
            )
            if not down_cmd:
                return False, "Compose-Datei der Instanz wurde nicht gefunden."
            down_ok, down_out = _run_command(down_cmd, cwd=target_dir, timeout=900)
            if not down_ok:
                return False, f"Docker-Stack konnte nicht gestoppt werden.\n{_tail_output(down_out, 12)}"
            details.append("Docker-Stack gestoppt und Volumes entfernt.")

        try:
            shutil.rmtree(target_dir)
            details.append("Instanzverzeichnis gelöscht.")
        except Exception as exc:
            return False, f"Instanzverzeichnis konnte nicht gelöscht werden: {exc}"
    else:
        details.append("Instanzverzeichnis war bereits entfernt.")

    nginx_sites_available = "/etc/nginx/sites-available"
    nginx_sites_enabled = "/etc/nginx/sites-enabled"
    site_name = f"inventarsystem-{subdomain}.conf"
    avail_file = os.path.join(nginx_sites_available, site_name)
    enabled_file = os.path.join(nginx_sites_enabled, site_name)

    removed_nginx_file = False
    for path in (enabled_file, avail_file):
        try:
            if os.path.lexists(path):
                os.remove(path)
                removed_nginx_file = True
        except Exception:
            continue

    if removed_nginx_file:
        if os.path.isfile("/usr/sbin/nginx") or os.path.isfile("/usr/bin/nginx"):
            test_ok, _ = _run_command(["nginx", "-t"], timeout=60)
            if test_ok:
                _run_command(["nginx", "-s", "reload"], timeout=60)
        details.append("Nginx-Site entfernt.")

    return True, " ".join(details) if details else "Instanz gelöscht."


def _delete_school_instance(subdomain: str) -> bool:
    key = _sanitize_text(subdomain or "", 63)
    if not key:
        return False

    client = None
    try:
        client, col = _get_collection("school_instances")
        result = col.delete_one({"subdomain": key})
        return result.deleted_count > 0
    except PyMongoError:
        return False
    finally:
        if client:
            client.close()


def _instance_db_name(instance_dir: str) -> str:
    config_path = os.path.join(instance_dir, "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            cfg = json.load(handle)
        value = ((cfg or {}).get("mongodb") or {}).get("db")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    return "Inventarsystem"


def _create_instance_admin_user(
    subdomain: str,
    username: str,
    password: str,
    first_name: str,
    last_name: str,
) -> tuple[bool, str]:
    instance_dir = _resolve_instance_dir(subdomain)
    if not instance_dir:
        return False, "Instanzverzeichnis nicht gefunden."

    user_name = _sanitize_text(username, 80)
    pwd = (password or "").strip()
    first = _sanitize_text(first_name or "Admin", 80) or "Admin"
    last = _sanitize_text(last_name or "User", 80) or "User"

    if not _validate_username(user_name):
        return False, "Ungültiger Benutzername für Instanz-Admin."
    if len(pwd) < 8:
        return False, "Passwort muss mindestens 8 Zeichen haben."

    pwd_hash = hashlib.sha512(pwd.encode("utf-8")).hexdigest()
    db_name = _instance_db_name(instance_dir)

    js_user = json.dumps(user_name)
    js_hash = json.dumps(pwd_hash)
    js_first = json.dumps(first)
    js_last = json.dumps(last)

    eval_script = (
        "const username=" + js_user + ";"
        "const hash=" + js_hash + ";"
        "const first=" + js_first + ";"
        "const last=" + js_last + ";"
        "const existing=db.users.findOne({Username:username});"
        "if(existing){"
        "db.users.updateOne({Username:username},{$set:{Password:hash,Admin:true,name:first,last_name:last,updated_at:new Date().toISOString()}});"
        "print('UPDATED');"
        "}else{"
        "db.users.insertOne({Username:username,Password:hash,Admin:true,active_ausleihung:null,name:first,last_name:last,favorites:[]});"
        "print('CREATED');"
        "}"
    )

    up_cmd = _instance_compose_cmd(instance_dir, ["up", "-d", "mongodb"])
    if not up_cmd:
        return False, "Compose-Datei der Instanz wurde nicht gefunden."

    up_ok, up_out = _run_command(up_cmd, cwd=instance_dir, timeout=180)
    if not up_ok:
        return False, f"MongoDB der Instanz konnte nicht gestartet werden: {_tail_output(up_out, 10)}"

    exec_cmd = _instance_compose_cmd(
        instance_dir,
        [
            "exec",
            "-T",
            "mongodb",
            "mongosh",
            "--quiet",
            "--eval",
            eval_script,
            db_name,
        ],
    )
    if not exec_cmd:
        return False, "Compose-Datei der Instanz wurde nicht gefunden."

    ok, output = _run_command(exec_cmd, cwd=instance_dir, timeout=240)

    if not ok:
        return False, f"Instanz-Admin konnte nicht angelegt werden: {_tail_output(output, 12)}"

    state = "aktualisiert" if "UPDATED" in output else "erstellt"
    return True, f"Instanz-Admin '{user_name}' wurde {state}."


def _get_school_instance_by_subdomain(subdomain: str) -> dict | None:
    key = _sanitize_text(subdomain or "", 63)
    if not key:
        return None

    client = None
    try:
        client, col = _get_collection("school_instances")
        return col.find_one({"subdomain": key})
    except PyMongoError:
        return None
    finally:
        if client:
            client.close()


def _get_instance_for_user(username: str, display_name: str) -> dict | None:
    uname = _sanitize_text(username or "", 80)
    if not uname:
        return None

    client = None
    try:
        client, col = _get_collection("school_instances")
        return col.find_one({"owner_username": uname}, sort=[("updated_at", -1), ("created_at", -1)])
    except PyMongoError:
        return None
    finally:
        if client:
            client.close()


def _with_public_id(doc: dict | None) -> dict | None:
    if not doc:
        return doc
    if not doc.get("id") and doc.get("_id") is not None:
        doc["id"] = str(doc.get("_id"))
    return doc


def _appointment_query_from_id(appointment_id: str) -> dict | None:
    lookup = (appointment_id or "").strip()
    if not lookup:
        return None
    if lookup.startswith("a-"):
        return {"id": lookup}
    try:
        return {"_id": ObjectId(lookup)}
    except Exception:
        return {"id": lookup}


def _post_query_from_id(post_id: str) -> dict | None:
    lookup = (post_id or "").strip()
    if not lookup:
        return None
    if lookup.startswith("p-"):
        return {"id": lookup}
    try:
        return {"_id": ObjectId(lookup)}
    except Exception:
        return {"id": lookup}


def _get_blocked_days() -> list:
    client = None
    entries = []
    try:
        client, col = _get_collection("blocked_days")
        entries = list(col.find({}, {"_id": 0}).sort("date", 1))
    except PyMongoError:
        return []
    finally:
        if client:
            client.close()

    normalized = []
    for item in entries:
        day = (item.get("date") or "").strip()
        if not day:
            continue
        normalized.append(
            {
                "date": day,
                "reason": (item.get("reason") or "").strip()[:200],
                "blocked_by": (item.get("blocked_by") or "").strip()[:80],
                "created_at": item.get("created_at") or "",
            }
        )
    normalized.sort(key=lambda value: value.get("date", ""))
    return normalized


def _get_blocked_day_map() -> dict:
    blocked = {}
    for item in _get_blocked_days():
        blocked[item.get("date", "")] = item
    return blocked


def _sanitize_html(html_content: str, max_length: int = 50000) -> str:
    """Sanitize HTML content: allow safe tags only."""
    if not html_content:
        return ""
    html_content = html_content[:max_length]
    allowed_tags = ["p", "br", "strong", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "blockquote", "code", "pre"]
    allowed_attrs = {"a": ["href", "title"]}
    return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)


def _get_team_members() -> list:
    members = []
    client = None
    try:
        client, col = _get_collection("team_members")
        members = list(col.find().sort([("sort_order", 1), ("created_at", 1)]))
    except PyMongoError:
        return []
    finally:
        if client:
            client.close()

    normalized = []
    for member in members:
        public_id = str(member.get("_id") or "")
        sort_raw = member.get("sort_order", 999)
        try:
            sort_order = int(sort_raw)
        except (TypeError, ValueError):
            sort_order = 999
        normalized.append(
            {
                "id": public_id,
                "sort_order": sort_order,
                "name": _sanitize_text(member.get("name") or "", 120),
                "role": _sanitize_text(member.get("role") or "", 120),
                "work": _sanitize_text(member.get("work") or "", 220),
                "bio": _sanitize_text(member.get("bio") or "", 500),
                "photo": _sanitize_text(member.get("photo") or "", 255),
            }
        )

    normalized.sort(key=lambda value: (value.get("sort_order", 999), value.get("name", "")))
    return normalized


def _validate_username(username: str) -> bool:
    """Validate username format: alphanumeric, underscore, dash, 3-30 chars."""
    if not username or not isinstance(username, str):
        return False
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return False
    return all(c.isalnum() or c in "_-" for c in username)


def _validate_email(email: str) -> bool:
    """Simple email validation for registration input."""
    value = (email or "").strip()
    if len(value) < 5 or len(value) > 254:
        return False
    if "@" not in value or value.count("@") != 1:
        return False
    local, domain = value.split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    return True


def _find_user(username: str):
    username_key = (username or "").strip()
    if not username_key:
        return None

    try:
        # First try an exact lookup using the original username.
        raw_user = user_store.get_user(username_key)
        normalized = _normalize_user_doc(raw_user)
        if normalized:
            return normalized

        # Fallback: case-insensitive lookup to avoid role-check failures
        # when session username casing differs from stored Username casing.
        all_users = user_store.get_all_users() or []
        for entry in all_users:
            candidate = (entry.get("Username") or entry.get("username") or "").strip()
            if candidate.lower() == username_key.lower():
                return _normalize_user_doc(entry)

        return None
    except Exception:
        return None


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            flash("Bitte zuerst einloggen.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            flash("Bitte zuerst einloggen.", "error")
            return redirect(url_for("login"))
        
        current_user = _find_user(session.get("username"))
        if not current_user or not current_user.get("is_admin", False):
            flash("Zugriff verweigert. Admin-Rechte erforderlich.", "error")
            return redirect(url_for("default"))
        
        return view_func(*args, **kwargs)

    return wrapped


"""-----------------------------------------------------------------------------------------------------------------"""

@app.route("/", methods=["GET", "POST"])
def default():
    return render_template("main.html")


@app.route('/dienstleistungen')
def dienstleistungen():
    return render_template("dienstleistungen.html")


@app.route('/projekte')
def projekte():
    return render_template("projekte.html")


@app.route('/inventarsystem')
def inventarsystem():
    return render_template("inventarsystem.html")


@app.route('/team')
def team():
    team_members = _get_team_members()
    return render_template("team.html", team_members=team_members)


@app.route('/kontakt')
def kontakt():
    return render_template("kontakt.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('default'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or request.form.get('username') or "").strip()
        password = data.get("password") or request.form.get('password') or ""

        if not username or not password:
            if request.is_json:
                return jsonify({"error": "Missing login data"}), 400
            flash('Bitte Benutzername und Passwort eingeben.', 'error')
            return redirect(url_for('login'))

        try:
            stored_user_raw = user_store.check_nm_pwd(username, password)
        except Exception:
            stored_user_raw = None

        stored_user = _normalize_user_doc(stored_user_raw)

        if stored_user:
            session['username'] = stored_user.get("username")
            session['display_name'] = stored_user.get("display_name") or stored_user.get("username")
            session['is_admin'] = stored_user.get("is_admin", False)

            if request.is_json:
                return jsonify({"status": "ok"}), 200

            return redirect(url_for('default'))

        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        flash('Login fehlgeschlagen. Bitte prüfen Sie Ihre Eingaben.', 'error')
        get_flashed_messages()

    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        school_name = (request.form.get("school_name") or "").strip()
        contact_person = (request.form.get("contact_person") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password_repeat = request.form.get("password_repeat") or ""

        if not username or not school_name or not contact_person or not email or not password or not password_repeat:
            flash("Bitte alle Felder ausfüllen.", "error")
            return redirect(url_for("register"))

        if not _validate_username(username):
            flash("Benutzername muss 3-30 Zeichen lang sein und nur Buchstaben, Zahlen, - und _ enthalten.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Das Passwort muss mindestens 8 Zeichen haben.", "error")
            return redirect(url_for("register"))

        if password != password_repeat:
            flash("Die Passwörter stimmen nicht überein.", "error")
            return redirect(url_for("register"))

        if _find_user(username):
            flash("Benutzername bereits vergeben.", "error")
            return redirect(url_for("register"))

        if not _validate_email(email):
            flash("Bitte eine gültige E-Mail-Adresse angeben.", "error")
            return redirect(url_for("register"))

        school_name = _sanitize_text(school_name, 120)
        contact_person = _sanitize_text(contact_person, 120)
        email = _sanitize_text(email, 254)

        try:
            existing_users = user_store.get_all_users() or []
            is_first_user = len(existing_users) == 0
            if not user_store.add_user(username, password, school_name, contact_person, email):
                flash("Benutzer konnte nicht erstellt werden.", "error")
                return redirect(url_for("register"))

            if is_first_user:
                user_store.make_admin(username)
        except Exception:
            flash("MongoDB ist derzeit nicht erreichbar.", "error")
            return redirect(url_for("register"))

        flash("Schulregistrierung erfolgreich. Bitte jetzt einloggen.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/appointments', methods=['GET'])
def appointments():
    software_packages = [
        {
            "slug": "normal",
            "name": "Normal",
            "headline": "Stabiler Einstieg für den Schulalltag",
            "features": [
                "Inventarverwaltung mit Rollenrechten",
                "Basis-Support und Ticketing",
                "Schulweite Übersichten",
            ],
        },
        {
            "slug": "pro",
            "name": "Pro",
            "headline": "Für Schulen mit erweitertem Bedarf",
            "features": [
                "Erweiterte Instanzverwaltung",
                "Detailberichte und Admin-Insights",
                "Priorisierter Support",
            ],
        },
        {
            "slug": "buecherei",
            "name": "Bücherei",
            "headline": "Optimiert für Bibliothek und Medien",
            "features": [
                "Ausleih- und Rückgabeprozesse",
                "Bestandsübersichten für Medien",
                "Transparente Historie pro Medium",
            ],
        },
    ]

    return render_template(
        "appointments.html",
        software_packages=software_packages,
    )


@app.route('/appointments/book-option', methods=['POST'])
@login_required
def book_option_package():
    package_raw = _sanitize_text(request.form.get("package") or "", 40).lower()
    package_map = {
        "normal": "Normal",
        "pro": "Pro",
        "buecherei": "Bücherei",
    }
    selected_package = package_map.get(package_raw)
    if not selected_package:
        flash("Ungültige Buchungsoption ausgewählt.", "error")
        return redirect(url_for("appointments"))

    message = (
        f"Ich möchte das Paket {selected_package} buchen. "
        "Bitte kontaktieren Sie mich für die nächsten Schritte."
    )

    client = None
    try:
        client, col = _get_collection("chat_messages")
        col.insert_one(
            {
                "username": session.get("username"),
                "sender": session.get("display_name") or session.get("username"),
                "sender_role": "user",
                "message": message,
                "created_at": _utc_now_iso(),
            }
        )
    except PyMongoError:
        flash("Buchungsanfrage konnte nicht gesendet werden.", "error")
        return redirect(url_for("appointments"))
    finally:
        if client:
            client.close()

    flash(f"Buchungsanfrage für Paket {selected_package} wurde an den Admin gesendet.", "success")
    return redirect(url_for("user_chat"))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    all_appointments = []
    client = None
    try:
        client, col = _get_collection("appointments")
        all_appointments = list(col.find().sort([("date", -1), ("time", -1)]))
        for item in all_appointments:
            _with_public_id(item)
    except PyMongoError:
        flash("Buchungsanfragen konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    blocked_days = _get_blocked_days()
    
    status_counts = {
        "Angefragt": len([a for a in all_appointments if a.get("status") == "Angefragt"]),
        "Bestaetigt": len([a for a in all_appointments if a.get("status") == "Bestaetigt"]),
        "Abgelehnt": len([a for a in all_appointments if a.get("status") == "Abgelehnt"]),
    }
    
    total_posts = 0
    client = None
    try:
        client, col = _get_collection("posts")
        total_posts = col.count_documents({})
    except PyMongoError:
        total_posts = 0
    finally:
        if client:
            client.close()
    
    return render_template(
        "admin_dashboard.html",
        appointments=all_appointments,
        blocked_days=blocked_days,
        status_counts=status_counts,
        total_posts=total_posts,
    )


@app.route('/admin/instances', methods=['GET', 'POST'])
@admin_required
def admin_instances():
    version_options = _parse_instance_version_options()
    available_users = _list_available_instance_users()

    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "create", 20).lower()
        posted_subdomain = _sanitize_text(request.form.get("subdomain") or "", 120)
        school_name = _sanitize_text(request.form.get("school_name") or "", 120)
        raw_subdomain = _sanitize_text(request.form.get("subdomain") or "", 120)
        owner_username = _sanitize_text(request.form.get("owner_username") or "", 80)
        app_image_tag = _sanitize_text(request.form.get("app_image_tag") or "latest", 80)
        library_enabled = (request.form.get("library_enabled") or "").strip().lower() in {"1", "on", "true", "yes"}
        subdomain = _slugify_subdomain(posted_subdomain or raw_subdomain or school_name)

        if action == "reload_nginx":
            reload_ok, reload_message = _reload_host_nginx()
            if not reload_ok:
                lowered = (reload_message or "").lower()
                if "nicht gefunden" in lowered or "not found" in lowered or "kein nginx-reload-befehl" in lowered:
                    flash("Host-Nginx kann aus dem Website-Container nicht direkt neu geladen werden.", "error")
                    flash(_host_reload_hint(), "info")
                    flash("Nach erfolgreichem Host-Reload bitte 'Reload auf Host bestätigt' ausführen.", "info")
                else:
                    flash(reload_message or "Nginx-Reload fehlgeschlagen.", "error")
                return redirect(url_for("admin_instances"))

            updated_rows = _promote_manual_nginx_status(
                "Nginx erfolgreich neu geladen (Admin-Aktion)."
            )
            flash("Nginx wurde erfolgreich neu geladen.", "success")
            if updated_rows > 0:
                flash(f"{updated_rows} Instanz(en) von manual_required auf ok gesetzt.", "info")
            else:
                flash("Keine Instanz mit nginx_status=manual_required gefunden.", "info")
            if reload_message:
                flash(reload_message, "info")
            return redirect(url_for("admin_instances"))

        if action == "confirm_nginx_reload":
            updated_rows = _promote_manual_nginx_status(
                "Host-Nginx manuell neu geladen und in Admin bestätigt."
            )
            if updated_rows > 0:
                flash(f"{updated_rows} Instanz(en) von manual_required auf ok gesetzt.", "success")
            else:
                flash("Keine Instanz mit nginx_status=manual_required gefunden.", "info")
            return redirect(url_for("admin_instances"))

        if action == "delete":
            if not _is_valid_subdomain(subdomain):
                flash("Ungültige Subdomain für Löschung.", "error")
                return redirect(url_for("admin_instances"))

            existing_record = _get_school_instance_by_subdomain(subdomain)
            target_dir = _instance_dir_path(subdomain)
            dir_exists = bool(target_dir and os.path.isdir(target_dir))
            if not existing_record and not dir_exists:
                flash("Instanz nicht gefunden.", "error")
                return redirect(url_for("admin_instances"))

            delete_ok, delete_message = _delete_instance_stack(subdomain)
            if not delete_ok:
                flash(delete_message or "Instanz konnte nicht gelöscht werden.", "error")
                return redirect(url_for("admin_instances"))

            if existing_record and not _delete_school_instance(subdomain):
                flash(
                    "Instanz wurde technisch gelöscht, aber der Datenbankeintrag konnte nicht entfernt werden.",
                    "error",
                )
                return redirect(url_for("admin_instances"))

            flash(f"Instanz {subdomain} wurde gelöscht.", "success")
            if delete_message:
                flash(delete_message, "info")
            return redirect(url_for("admin_instances"))

        if action == "toggle_library":
            target = _get_school_instance_by_subdomain(subdomain)
            if not target:
                flash("Instanz nicht gefunden.", "error")
                return redirect(url_for("admin_instances"))

            instance_dir = _resolve_instance_dir(subdomain)
            if not instance_dir:
                flash("Instanzverzeichnis nicht gefunden.", "error")
                return redirect(url_for("admin_instances"))

            target_enabled = (request.form.get("library_enabled") or "").strip().lower() in {"1", "on", "true", "yes"}
            ok, message = _set_instance_library_enabled(instance_dir, target_enabled)
            if not ok:
                _upsert_school_instance(
                    {
                        "subdomain": subdomain,
                        "status": "Fehler",
                        "nginx_status": "error",
                        "last_message": message,
                    }
                )
                flash(message, "error")
                return redirect(url_for("admin_instances"))

            restart_ok, restart_output = _restart_instance_stack(instance_dir)
            client = None
            try:
                client, col = _get_collection("school_instances")
                col.update_one(
                    {"subdomain": subdomain},
                    {
                        "$set": {
                            "school_name": target.get("school_name") or "",
                            "owner_username": target.get("owner_username") or "",
                            "subdomain": subdomain,
                            "domain": target.get("domain") or f"{subdomain}.{INSTANCE_PARENT_DOMAIN}",
                            "https_port": int(target.get("https_port") or 0),
                            "instance_dir": instance_dir,
                            "app_image_tag": target.get("app_image_tag") or "latest",
                            "library_enabled": target_enabled,
                            "status": "Läuft" if restart_ok else "Fehler",
                            "nginx_status": "ok" if restart_ok else "error",
                            "last_message": "Bibliothek aktiviert/deaktiviert und Instanz neu gestartet." if restart_ok else _tail_output(restart_output, 18),
                            "updated_at": _utc_now_iso(),
                        },
                        "$setOnInsert": {"created_at": _utc_now_iso()},
                    },
                    upsert=True,
                )
            except PyMongoError:
                pass
            finally:
                if client:
                    client.close()

            if restart_ok:
                flash(f"Bibliothek wurde {'aktiviert' if target_enabled else 'deaktiviert'} und die Instanz neu gestartet.", "success")
                if restart_output:
                    flash(_tail_output(restart_output, 12), "info")
            else:
                flash(f"Bibliothek wurde gespeichert, aber der Neustart ist fehlgeschlagen.\n{_tail_output(restart_output, 18)}", "error")
            return redirect(url_for("admin_instances"))

        if action not in {"create", "start"}:
            flash("Ungültige Aktion für Instanzverwaltung.", "error")
            return redirect(url_for("admin_instances"))

        if not available_users:
            flash("Keine freien Nutzer verfügbar. Bitte zuerst einen neuen Nutzer anlegen oder eine bestehende Instanz löschen.", "error")
            return redirect(url_for("admin_instances"))

        if not school_name:
            flash("Bitte einen Schulnamen angeben.", "error")
            return redirect(url_for("admin_instances"))

        if not owner_username:
            flash("Bitte einen Nutzer zuweisen.", "error")
            return redirect(url_for("admin_instances"))

        owner_doc = _find_user(owner_username)
        if not owner_doc:
            flash("Ausgewählter Nutzer wurde nicht gefunden.", "error")
            return redirect(url_for("admin_instances"))

        if not school_name:
            school_name = _sanitize_text(owner_doc.get("display_name") or owner_username, 120)

        if app_image_tag not in version_options:
            flash("Ungültige Version ausgewählt.", "error")
            return redirect(url_for("admin_instances"))

        existing_for_owner = _get_instance_for_user(owner_username, "")
        if existing_for_owner:
            existing_sub = _sanitize_text(existing_for_owner.get("subdomain") or "", 63)
            if existing_sub and existing_sub != subdomain:
                flash(
                    f"Nutzer {owner_username} ist bereits der Instanz {existing_sub} zugewiesen. "
                    "Bitte erst diese Zuweisung ändern.",
                    "error",
                )
                return redirect(url_for("admin_instances"))

        if not _is_valid_subdomain(subdomain):
            flash("Ungültige Subdomain. Erlaubt sind a-z, 0-9 und Bindestriche (3-63 Zeichen).", "error")
            return redirect(url_for("admin_instances"))

        success, message, details = _run_instance_provision(
            action,
            school_name,
            subdomain,
            app_image_tag=app_image_tag,
            library_enabled=library_enabled,
        )

        instance_data = {
            "school_name": school_name,
            "owner_username": owner_username,
            "subdomain": details.get("SUBDOMAIN") or subdomain,
            "domain": details.get("DOMAIN") or f"{subdomain}.{INSTANCE_PARENT_DOMAIN}",
            "https_port": int((details.get("HTTPS_PORT") or "0") or 0),
            "instance_dir": details.get("INSTANCE_DIR") or os.path.join(INSTANCE_BASE_DIR, subdomain),
            "app_image_tag": details.get("APP_IMAGE_TAG") or app_image_tag,
            "library_enabled": library_enabled if details.get("LIBRARY_ENABLED") is None else details.get("LIBRARY_ENABLED") == "1",
            "status": "Läuft" if success else "Fehler",
            "nginx_status": details.get("NGINX_STATUS") or ("ok" if success else "error"),
            "last_message": message,
        }
        _upsert_school_instance(instance_data)

        if success:
            flash(f"Instanz gestartet: {instance_data['domain']}", "success")
            if message:
                flash(message, "info")
        else:
            flash(message or "Instanz konnte nicht gestartet werden.", "error")

        return redirect(url_for("admin_instances"))

    instances = _list_school_instances()
    instance_dashboard = _build_instance_dashboard(instances)
    return render_template(
        "admin_instances.html",
        instances=instances,
        users=_list_users_for_admin(),
        available_users=available_users,
        instance_dashboard=instance_dashboard,
        version_options=version_options,
        instance_repo_url=INSTANCE_REPO_URL,
        parent_domain=INSTANCE_PARENT_DOMAIN,
        base_dir=INSTANCE_BASE_DIR,
        provision_script=INSTANCE_PROVISION_SCRIPT,
    )


@app.route('/admin/instances/stats')
@admin_required
def admin_instances_stats():
    instances = _list_school_instances()
    return jsonify(_collect_runtime_stats(instances))


@app.route('/admin/system', methods=['GET', 'POST'])
@admin_required
def admin_system_tools():
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "", 40)
        subdomain = _sanitize_text(request.form.get("subdomain") or "", 63)

        if action == "restart_core":
            compose_file = os.path.join(BASE_DIR, "docker-compose.yml")
            ok, output = _run_command(
                ["docker", "compose", "-f", compose_file, "restart", "website", "mongodb"],
                cwd=BASE_DIR,
                timeout=180,
            )
            flash("Core-Services wurden neugestartet." if ok else f"Core-Restart fehlgeschlagen:\n{_tail_output(output, 10)}", "success" if ok else "error")
            return redirect(url_for("admin_system_tools"))

        if action in {"backup_instance", "update_instance", "restart_instance"}:
            instance_dir = _resolve_instance_dir(subdomain)
            if not instance_dir:
                flash("Instanz nicht gefunden oder ungültige Subdomain.", "error")
                return redirect(url_for("admin_system_tools"))

            if action == "backup_instance":
                command = ["bash", "./backup.sh", "--mode", "auto"]
                timeout = 1800
                title = f"Backup für {subdomain}"
            elif action == "update_instance":
                command = ["bash", "./update.sh"]
                timeout = 2400
                title = f"Update für {subdomain}"
            else:
                title = f"Restart für {subdomain}"
                ok, output = _restart_instance_stack(instance_dir)
                if ok:
                    flash(f"{title} erfolgreich.\n{_tail_output(output, 12)}", "success")
                    _upsert_school_instance(
                        {
                            "subdomain": subdomain,
                            "status": "Läuft",
                            "nginx_status": "ok",
                            "last_message": "Instanz über System-Tools neu gestartet.",
                        }
                    )
                else:
                    flash(f"{title} fehlgeschlagen.\n{_tail_output(output, 18)}", "error")
                    _upsert_school_instance(
                        {
                            "subdomain": subdomain,
                            "status": "Fehler",
                            "nginx_status": "error",
                            "last_message": _sanitize_text(_tail_output(output, 6), 500),
                        }
                    )
                return redirect(url_for("admin_system_tools"))

            ok, output = _run_command(command, cwd=instance_dir, timeout=timeout)
            if ok:
                flash(f"{title} erfolgreich.\n{_tail_output(output, 12)}", "success")
            else:
                flash(f"{title} fehlgeschlagen.\n{_tail_output(output, 18)}", "error")
            return redirect(url_for("admin_system_tools"))

        if action == "create_instance_admin":
            username = _sanitize_text(request.form.get("admin_username") or "", 80)
            password = (request.form.get("admin_password") or "").strip()
            first_name = _sanitize_text(request.form.get("admin_first_name") or "Admin", 80)
            last_name = _sanitize_text(request.form.get("admin_last_name") or "User", 80)

            ok, msg = _create_instance_admin_user(subdomain, username, password, first_name, last_name)
            flash(msg, "success" if ok else "error")
            return redirect(url_for("admin_system_tools"))

        flash("Unbekannte System-Aktion.", "error")
        return redirect(url_for("admin_system_tools"))

    instances = _list_school_instances()
    system_snapshot = _build_server_management_snapshot(instances)
    return render_template("admin_system.html", instances=instances, system_snapshot=system_snapshot)


@app.route('/admin/system/stats')
@admin_required
def admin_system_stats():
    instances = _list_school_instances()
    return jsonify(_build_server_management_snapshot(instances))


@app.route('/admin/system/logs/live')
@admin_required
def admin_system_live_logs():
    return jsonify(_collect_homepage_service_logs())


@app.route('/admin/system/logs/core')
@admin_required
def admin_download_core_logs():
    ok, output = _collect_core_logs()
    if not ok:
        flash(f"Core-Logs konnten nicht geladen werden.\n{_tail_output(output, 14)}", "error")
        return redirect(url_for("admin_system_tools"))

    filename = f"core-logs-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.log"
    return send_file(
        BytesIO(output.encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name=filename,
    )


@app.route('/admin/system/logs/instance/<subdomain>')
@admin_required
def admin_download_instance_logs(subdomain):
    ok, output = _collect_instance_logs(subdomain)
    if not ok:
        flash(f"Instanz-Logs konnten nicht geladen werden.\n{_tail_output(output, 14)}", "error")
        return redirect(url_for("admin_system_tools"))

    safe_name = _slugify_subdomain(subdomain)
    filename = f"instance-{safe_name}-logs-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.log"
    return send_file(
        BytesIO(output.encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name=filename,
    )


@app.route('/admin/system/backup/export/<subdomain>')
@admin_required
def admin_export_instance_backup(subdomain):
    ok, filename, archive_path = _build_instance_backup_archive(subdomain)
    if not ok or not archive_path:
        flash(filename or "Backup-Export fehlgeschlagen.", "error")
        return redirect(url_for("admin_system_tools"))

    @after_this_request
    def _cleanup_archive(response):
        try:
            os.remove(archive_path)
        except OSError:
            pass
        return response

    return send_file(
        archive_path,
        mimetype="application/gzip",
        as_attachment=True,
        download_name=filename,
    )


@app.route('/admin/system/backup/import/<subdomain>', methods=['POST'])
@admin_required
def admin_import_instance_backup(subdomain):
    instance_dir = _resolve_instance_dir(subdomain)
    if not instance_dir:
        flash("Instanzverzeichnis nicht gefunden.", "error")
        return redirect(url_for("admin_system_tools"))

    upload = request.files.get("backup_file")
    if not upload or not upload.filename:
        flash("Bitte eine Backup-Datei auswählen.", "error")
        return redirect(url_for("admin_system_tools"))

    filename = secure_filename(upload.filename)
    if not (filename.endswith(".tar.gz") or filename.endswith(".tgz")):
        flash("Nur .tar.gz oder .tgz Backups sind erlaubt.", "error")
        return redirect(url_for("admin_system_tools"))

    fd, temp_path = tempfile.mkstemp(prefix="instance-restore-", suffix=".tar.gz")
    os.close(fd)
    try:
        upload.save(temp_path)
        ok, message = _safe_extract_tar_archive(temp_path, instance_dir)
        if not ok:
            flash(message, "error")
            return redirect(url_for("admin_system_tools"))

        restart_ok, restart_output = _restart_instance_stack(instance_dir)
        if restart_ok:
            flash(f"Backup für {subdomain} erfolgreich eingespielt und Instanz neu gestartet.", "success")
            if restart_output:
                flash(_tail_output(restart_output, 10), "info")
        else:
            flash(f"Backup eingespielt, aber Neustart fehlgeschlagen:\n{_tail_output(restart_output, 14)}", "error")
    except Exception as exc:
        flash(f"Backup konnte nicht eingespielt werden: {exc}", "error")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    return redirect(url_for("admin_system_tools"))


@app.route('/admin/appointments/block-day', methods=['POST'])
@admin_required
def admin_block_day():
    action = _sanitize_text(request.form.get("action") or "", 30)
    block_date = (request.form.get("block_date") or "").strip()
    reason = _sanitize_text(request.form.get("reason") or "", 200)

    client = None
    try:
        client, col = _get_collection("blocked_days")

        if action == "add":
            try:
                date.fromisoformat(block_date)
            except ValueError:
                flash("Bitte ein gültiges Datum zum Sperren wählen.", "error")
                return redirect(url_for("admin_dashboard"))

            if col.find_one({"date": block_date}):
                flash("Der Tag ist bereits gesperrt.", "error")
                return redirect(url_for("admin_dashboard"))

            col.insert_one(
                {
                    "date": block_date,
                    "reason": reason,
                    "blocked_by": session.get("username") or "admin",
                    "created_at": _utc_now_iso(),
                }
            )
            flash("Tag im Kalender gesperrt.", "success")
        elif action == "remove":
            result = col.delete_one({"date": block_date})
            if not result.deleted_count:
                flash("Sperrtag nicht gefunden.", "error")
                return redirect(url_for("admin_dashboard"))
            flash("Sperrtag entfernt.", "success")
        else:
            flash("Ungültige Aktion für Kalendersperre.", "error")
            return redirect(url_for("admin_dashboard"))
    except PyMongoError:
        flash("Kalendersperre konnte nicht gespeichert werden.", "error")
    finally:
        if client:
            client.close()

    return redirect(url_for("admin_dashboard"))


@app.route('/admin/appointment/<appointment_id>', methods=['POST'])
@admin_required
def update_appointment(appointment_id):
    action = request.form.get("action", "").strip()
    response_text = _sanitize_text(request.form.get("response") or "", 5000)
    
    if action not in ["confirm", "reject"]:
        flash("Ungültige Aktion.", "error")
        return redirect(url_for("admin_dashboard"))
    
    query = _appointment_query_from_id(appointment_id)
    if not query:
        flash("Buchung nicht gefunden.", "error")
        return redirect(url_for("admin_dashboard"))

    new_status = "Bestaetigt" if action == "confirm" else "Abgelehnt"

    client = None
    try:
        client, col = _get_collection("appointments")
        result = col.update_one(
            query,
            {
                "$set": {
                    "status": new_status,
                    "response": response_text,
                    "responded_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "responded_by": session.get("username"),
                }
            },
        )
        if result.matched_count == 0:
            flash("Buchung nicht gefunden.", "error")
            return redirect(url_for("admin_dashboard"))
    except PyMongoError:
        flash("Buchung konnte nicht aktualisiert werden.", "error")
        return redirect(url_for("admin_dashboard"))
    finally:
        if client:
            client.close()

    flash(f"Buchung wurde {('bestaetigt' if action == 'confirm' else 'abgelehnt')}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route('/admin/blog', methods=['GET', 'POST'])
@admin_required
def admin_blog():
    if request.method == 'POST':
        action = request.form.get("action", "").strip()
        
        if action == "create":
            title = _sanitize_text(request.form.get("title") or "", 200)
            content = _sanitize_html(request.form.get("content") or "", 50000)
            excerpt = _sanitize_text(request.form.get("excerpt") or "", 500)
            
            if not title or not content:
                flash("Bitte Titel und inhalt ausfüllen.", "error")
                return redirect(url_for("admin_blog"))
            client = None
            try:
                client, col = _get_collection("posts")
                col.insert_one(
                    {
                        "id": f"p-{int(datetime.utcnow().timestamp() * 1000)}",
                        "title": title,
                        "excerpt": excerpt or (content[:150] + "...") if len(content) > 150 else content,
                        "content": content,
                        "author": session.get("username"),
                        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                        "published": True,
                    }
                )
            except PyMongoError:
                flash("Beitrag konnte nicht gespeichert werden.", "error")
                return redirect(url_for("admin_blog"))
            finally:
                if client:
                    client.close()

            flash("Beitrag veroeffentlicht.", "success")
            return redirect(url_for("admin_blog"))
        
        elif action == "delete":
            post_id = (request.form.get("post_id") or "").strip()
            query = _post_query_from_id(post_id)
            if not query:
                flash("Ungültige Beitrag-ID.", "error")
                return redirect(url_for("admin_blog"))
            client = None
            try:
                client, col = _get_collection("posts")
                result = col.delete_one(query)
            except PyMongoError:
                flash("Beitrag konnte nicht gelöscht werden.", "error")
                return redirect(url_for("admin_blog"))
            finally:
                if client:
                    client.close()

            if not result.deleted_count:
                flash("Beitrag nicht gefunden.", "error")
                return redirect(url_for("admin_blog"))

            flash("Beitrag gelöscht.", "success")
            return redirect(url_for("admin_blog"))

    posts = []
    client = None
    try:
        client, col = _get_collection("posts")
        posts = list(col.find().sort("created_at", -1))
        for item in posts:
            _with_public_id(item)
    except PyMongoError:
        flash("Blogbeitraege konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    return render_template("admin_blog.html", posts=posts)


@app.route('/blog')
def blog():
    posts = []
    client = None
    try:
        client, col = _get_collection("posts")
        posts = list(col.find({"published": True}).sort("created_at", -1))
        for item in posts:
            _with_public_id(item)
    except PyMongoError:
        posts = []
    finally:
        if client:
            client.close()

    return render_template("blog.html", posts=posts)


@app.route('/blog/<post_id>')
def blog_post(post_id):
    query = _post_query_from_id(post_id)
    if not query:
        flash("Ungültige Beitrag-ID.", "error")
        return redirect(url_for("blog"))
    client = None
    post = None
    try:
        client, col = _get_collection("posts")
        post = col.find_one(query)
        _with_public_id(post)
    except PyMongoError:
        post = None
    finally:
        if client:
            client.close()

    if not post:
        flash("Beitrag nicht gefunden.", "error")
        return redirect(url_for("blog"))
    
    return render_template("blog_post.html", post=post)


@app.route('/my/invoices')
@login_required
def my_invoices():
    invoices = []
    client = None
    try:
        client, col = _get_collection("invoices")
        invoices = list(col.find({"username": session.get("username")}, {"_id": 0}).sort("created_at", -1))
    except PyMongoError:
        flash("Rechnungen konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()
    return render_template("my_invoices.html", invoices=invoices)


@app.route('/my/instance', methods=['GET', 'POST'])
@login_required
def my_instance_management():
    username = _sanitize_text(session.get("username") or "", 80)
    display_name = _sanitize_text(session.get("display_name") or username, 120)

    current_instance = _get_instance_for_user(username, display_name)
    current_subdomain = _sanitize_text((current_instance or {}).get("subdomain") or "", 63)
    suggested_subdomain = _slugify_subdomain(display_name or username)

    if request.method == 'POST':
        flash("Nutzer können Instanzen nicht selbst erstellen oder ändern. Bitte den Administrator kontaktieren.", "error")
        return redirect(url_for("my_instance_management"))

    instance_doc = _get_instance_for_user(username, display_name)
    instance_view = None
    if instance_doc:
        instance_view = {
            "school_name": _sanitize_text(instance_doc.get("school_name") or display_name, 120),
            "owner_username": _sanitize_text(instance_doc.get("owner_username") or "", 80),
            "subdomain": _sanitize_text(instance_doc.get("subdomain") or "", 63),
            "domain": _sanitize_text(instance_doc.get("domain") or "", 190),
            "https_port": int(instance_doc.get("https_port") or 0),
            "status": _sanitize_text(instance_doc.get("status") or "Unbekannt", 40),
            "nginx_status": _sanitize_text(instance_doc.get("nginx_status") or "unbekannt", 80),
            "last_message": _sanitize_text(instance_doc.get("last_message") or "", 500),
            "updated_at": instance_doc.get("updated_at") or "",
        }

    return render_template(
        "my_instance.html",
        instance=instance_view,
        suggested_subdomain=suggested_subdomain,
        parent_domain=INSTANCE_PARENT_DOMAIN,
        default_school_name=display_name,
    )


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def user_chat():
    client = None
    if request.method == 'POST':
        message = _sanitize_text(request.form.get("message") or "", 3000)
        if not message:
            flash("Bitte eine Nachricht eingeben.", "error")
            return redirect(url_for("user_chat"))
        try:
            client, col = _get_collection("chat_messages")
            col.insert_one(
                {
                    "username": session.get("username"),
                    "sender": session.get("display_name"),
                    "sender_role": "user",
                    "message": message,
                    "created_at": _utc_now_iso(),
                }
            )
            flash("Nachricht gesendet.", "success")
        except PyMongoError:
            flash("Nachricht konnte nicht gesendet werden.", "error")
        finally:
            if client:
                client.close()
        return redirect(url_for("user_chat"))

    messages = []
    try:
        client, col = _get_collection("chat_messages")
        messages = list(col.find({"username": session.get("username")}, {"_id": 0}).sort("created_at", 1))
    except PyMongoError:
        flash("Chat konnte nicht geladen werden.", "error")
    finally:
        if client:
            client.close()
    return render_template("chat.html", messages=messages)


@app.route('/tickets', methods=['GET', 'POST'])
@login_required
def user_tickets():
    client = None
    if request.method == 'POST':
        title = _sanitize_text(request.form.get("title") or "", 200)
        description = _sanitize_text(request.form.get("description") or "", 5000)
        priority = _sanitize_text(request.form.get("priority") or "Normal", 30)
        if not title or not description:
            flash("Bitte Titel und Beschreibung ausfüllen.", "error")
            return redirect(url_for("user_tickets"))
        try:
            client, col = _get_collection("support_tickets")
            col.insert_one(
                {
                    "username": session.get("username"),
                    "display_name": session.get("display_name"),
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "status": "Offen",
                    "admin_response": "",
                    "created_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                }
            )
            flash("Support-Ticket erstellt.", "success")
        except PyMongoError:
            flash("Support-Ticket konnte nicht erstellt werden.", "error")
        finally:
            if client:
                client.close()
        return redirect(url_for("user_tickets"))

    tickets = []
    try:
        client, col = _get_collection("support_tickets")
        tickets = list(col.find({"username": session.get("username")}).sort("created_at", -1))
        for ticket in tickets:
            ticket["id"] = str(ticket.get("_id"))
    except PyMongoError:
        flash("Tickets konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    return render_template("tickets.html", tickets=tickets)


@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "", 50)
        username = _sanitize_text(request.form.get("username") or "", 80)

        if not username:
            flash("Bitte Benutzername angeben.", "error")
            return redirect(url_for("admin_users"))

        if action == "make_admin":
            user_store.make_admin(username)
            flash("Benutzer zum Admin gemacht.", "success")
        elif action == "remove_admin":
            user_store.remove_admin(username)
            flash("Admin-Rechte entfernt.", "success")
        elif action == "delete_user":
            if username == session.get("username"):
                flash("Sie können Ihr eigenes Konto nicht löschen.", "error")
                return redirect(url_for("admin_users"))
            user_store.delete_user(username)
            flash("Benutzer gelöscht.", "success")
        else:
            flash("Ungültige Aktion.", "error")
        return redirect(url_for("admin_users"))

    users = _list_users_for_admin()
    instances_by_owner = _list_instances_grouped_by_owner()
    return render_template("admin_users.html", users=users, instances_by_owner=instances_by_owner)


@app.route('/admin/team', methods=['GET', 'POST'])
@admin_required
def admin_team():
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "upsert", 20)
        member_id = _sanitize_text(request.form.get("member_id") or "", 64)

        client = None
        try:
            client, col = _get_collection("team_members")

            if action == "delete":
                try:
                    result = col.delete_one({"_id": ObjectId(member_id)})
                except Exception:
                    flash("Ungültige Team-ID.", "error")
                    return redirect(url_for("admin_team"))
                if result.deleted_count:
                    flash("Teammitglied entfernt.", "success")
                else:
                    flash("Teammitglied nicht gefunden.", "error")
                return redirect(url_for("admin_team"))

            name = _sanitize_text(request.form.get("name") or "", 120)
            role = _sanitize_text(request.form.get("role") or "", 120)
            work = _sanitize_text(request.form.get("work") or "", 220)
            bio = _sanitize_text(request.form.get("bio") or "", 500)
            sort_raw = _sanitize_text(request.form.get("sort_order") or "999", 10)

            try:
                sort_order = int(sort_raw)
            except ValueError:
                sort_order = 999
            sort_order = max(1, min(sort_order, 999))

            if not name or not role or not work:
                flash("Bitte Name, Rolle und Arbeit ausfüllen.", "error")
                return redirect(url_for("admin_team"))

            current = None
            if member_id:
                try:
                    current = col.find_one({"_id": ObjectId(member_id)})
                except Exception:
                    flash("Ungültige Team-ID.", "error")
                    return redirect(url_for("admin_team"))

            photo_identifier = member_id or name[:20]
            photo_path = _save_team_photo(request.files.get("photo"), photo_identifier)

            if request.files.get("photo") and request.files.get("photo").filename and not photo_path:
                flash("Foto muss JPG, JPEG, PNG oder WEBP sein.", "error")
                return redirect(url_for("admin_team"))

            if not photo_path:
                photo_path = (current or {}).get("photo", "")

            if action == "create":
                if not photo_path:
                    flash("Bitte ein Foto für das neue Teammitglied hochladen.", "error")
                    return redirect(url_for("admin_team"))
                col.insert_one(
                    {
                        "name": name,
                        "role": role,
                        "work": work,
                        "bio": bio,
                        "photo": photo_path,
                        "sort_order": sort_order,
                        "created_by": session.get("username") or "admin",
                        "created_at": _utc_now_iso(),
                        "updated_at": _utc_now_iso(),
                    }
                )
                flash("Teammitglied hinzugefuegt.", "success")
            elif action == "update":
                if not member_id:
                    flash("Team-ID fehlt.", "error")
                    return redirect(url_for("admin_team"))
                try:
                    result = col.update_one(
                        {"_id": ObjectId(member_id)},
                        {
                            "$set": {
                                "name": name,
                                "role": role,
                                "work": work,
                                "bio": bio,
                                "photo": photo_path,
                                "sort_order": sort_order,
                                "updated_by": session.get("username") or "admin",
                                "updated_at": _utc_now_iso(),
                            }
                        },
                    )
                except Exception:
                    flash("Ungültige Team-ID.", "error")
                    return redirect(url_for("admin_team"))
                if result.matched_count == 0:
                    flash("Teammitglied nicht gefunden.", "error")
                    return redirect(url_for("admin_team"))
                flash("Teammitglied aktualisiert.", "success")
            else:
                flash("Ungültige Aktion.", "error")
                return redirect(url_for("admin_team"))
        except PyMongoError:
            flash("Teamdaten konnten nicht gespeichert werden.", "error")
        finally:
            if client:
                client.close()

        return redirect(url_for("admin_team"))

    team_members = _get_team_members()
    return render_template("admin_team.html", team_members=team_members)


@app.route('/admin/chats', methods=['GET', 'POST'])
@admin_required
def admin_chats():
    client = None
    selected_user = _sanitize_text(request.args.get("username") or request.form.get("username") or "", 80)

    if request.method == 'POST':
        message = _sanitize_text(request.form.get("message") or "", 3000)
        if not selected_user or not message:
            flash("Bitte Empfaenger und Nachricht angeben.", "error")
            return redirect(url_for("admin_chats"))
        try:
            client, col = _get_collection("chat_messages")
            col.insert_one(
                {
                    "username": selected_user,
                    "sender": session.get("display_name") or session.get("username"),
                    "sender_role": "admin",
                    "message": message,
                    "created_at": _utc_now_iso(),
                }
            )
            flash("Antwort gesendet.", "success")
        except PyMongoError:
            flash("Antwort konnte nicht gesendet werden.", "error")
        finally:
            if client:
                client.close()
        return redirect(url_for("admin_chats", username=selected_user))

    conversations = []
    messages = []
    try:
        client, col = _get_collection("chat_messages")
        conversations = sorted(col.distinct("username"))
        if selected_user:
            messages = list(col.find({"username": selected_user}, {"_id": 0}).sort("created_at", 1))
    except PyMongoError:
        flash("Admin-Chat konnte nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    return render_template(
        "admin_chats.html",
        conversations=conversations,
        selected_user=selected_user,
        messages=messages,
    )


@app.route('/admin/tickets', methods=['GET', 'POST'])
@admin_required
def admin_tickets():
    client = None
    if request.method == 'POST':
        ticket_id = _sanitize_text(request.form.get("ticket_id") or "", 64)
        status = _sanitize_text(request.form.get("status") or "", 40)
        admin_response = _sanitize_text(request.form.get("admin_response") or "", 5000)
        if not ticket_id:
            flash("Ticket-ID fehlt.", "error")
            return redirect(url_for("admin_tickets"))

        try:
            client, col = _get_collection("support_tickets")
            col.update_one(
                {"_id": ObjectId(ticket_id)},
                {
                    "$set": {
                        "status": status or "In Bearbeitung",
                        "admin_response": admin_response,
                        "updated_at": _utc_now_iso(),
                    }
                },
            )
            flash("Ticket aktualisiert.", "success")
        except Exception:
            flash("Ticket konnte nicht aktualisiert werden.", "error")
        finally:
            if client:
                client.close()
        return redirect(url_for("admin_tickets"))

    tickets = []
    try:
        client, col = _get_collection("support_tickets")
        tickets = list(col.find().sort("created_at", -1))
        for ticket in tickets:
            ticket["id"] = str(ticket.get("_id"))
    except PyMongoError:
        flash("Support-Tickets konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    return render_template("admin_tickets.html", tickets=tickets)


@app.route('/admin/invoices', methods=['GET', 'POST'])
@admin_required
def admin_invoices():
    client = None
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "", 50)
        invoice_id = _sanitize_text(request.form.get("invoice_id") or "", 64)

        try:
            client, col = _get_collection("invoices")

            if action == "create":
                username = _sanitize_text(request.form.get("username") or "", 80)
                invoice_number = _sanitize_text(request.form.get("invoice_number") or "", 120)
                period = _sanitize_text(request.form.get("period") or "", 20)
                due_date = _sanitize_text(request.form.get("due_date") or "", 20)
                status = _sanitize_text(request.form.get("status") or "Offen", 40)
                amount_text = _sanitize_text(request.form.get("amount_eur") or "0", 20)
                normalized_invoice_number = invoice_number or f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                pdf_path = _save_invoice_pdf(request.files.get("invoice_pdf"), normalized_invoice_number)

                try:
                    amount = float(amount_text)
                except ValueError:
                    amount = 0.0

                if not username or not period:
                    flash("Bitte Benutzername und Zeitraum angeben.", "error")
                    return redirect(url_for("admin_invoices"))

                col.insert_one(
                    {
                        "username": username,
                        "invoice_number": normalized_invoice_number,
                        "period": period,
                        "amount_eur": amount,
                        "status": status,
                        "due_date": due_date or "2026-12-31",
                        "pdf_path": pdf_path or "",
                        "created_at": _utc_now_iso(),
                    }
                )
                flash("Rechnung angelegt.", "success")

            elif action == "update" and invoice_id:
                amount_text = _sanitize_text(request.form.get("amount_eur") or "0", 20)
                invoice_number = _sanitize_text(request.form.get("invoice_number") or "", 120)
                pdf_path = _save_invoice_pdf(request.files.get("invoice_pdf"), invoice_number or "invoice")
                try:
                    amount = float(amount_text)
                except ValueError:
                    amount = 0.0

                update_payload = {
                    "invoice_number": invoice_number,
                    "period": _sanitize_text(request.form.get("period") or "", 20),
                    "status": _sanitize_text(request.form.get("status") or "Offen", 40),
                    "due_date": _sanitize_text(request.form.get("due_date") or "", 20),
                    "amount_eur": amount,
                }
                if pdf_path:
                    update_payload["pdf_path"] = pdf_path

                col.update_one(
                    {"_id": ObjectId(invoice_id)},
                    {
                        "$set": update_payload
                    },
                )
                flash("Rechnung aktualisiert.", "success")

            elif action == "delete" and invoice_id:
                col.delete_one({"_id": ObjectId(invoice_id)})
                flash("Rechnung gelöscht.", "success")
            else:
                flash("Ungültige Aktion.", "error")
        except Exception:
            flash("Rechnungsverwaltung fehlgeschlagen.", "error")
        finally:
            if client:
                client.close()

        return redirect(url_for("admin_invoices"))

    invoices = []
    try:
        client, col = _get_collection("invoices")
        invoices = list(col.find().sort("created_at", -1))
        for item in invoices:
            item["id"] = str(item.get("_id"))
    except PyMongoError:
        flash("Rechnungen konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    users = _list_users_for_admin()
    return render_template("admin_invoices.html", invoices=invoices, users=users)


@app.route('/datenschutz')
def datenschutz():
    return render_template("datenschutz.html")


@app.route('/impressum')
def impressum():
    return render_template("impressum.html")


@app.route('/nutzungsbedingungen')
def nutzungsbedingungen():
    return render_template("nutzungsbedingungen.html")

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('display_name', None)
    session.pop('is_admin', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


def main():
    app.run(host="0.0.0.0", port=4999, debug=False)

if __name__ == "__main__":
    main()