import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVOICE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "invoices")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "Invario_Website")
LICENSE_COLLECTION = "licenses"


def _get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1200)
    return client, client[MONGO_DB_NAME][LICENSE_COLLECTION]

def load_licenses() -> dict:
    """Load all licenses from MongoDB and return them as a list."""
    client = None
    try:
        client, col = _get_collection()
        return list(col.find({}, {"_id": 0}).sort("created_at", 1))
    except PyMongoError:
        return []
    finally:
        if client:
            client.close()


def save_licenses(data: dict) -> bool:
    """Replace MongoDB licenses with provided list data."""
    if not isinstance(data, list):
        return False

    client = None
    try:
        client, col = _get_collection()
        col.delete_many({})

        prepared = []
        for item in data:
            if not isinstance(item, dict):
                continue
            license_key = str(item.get("license_key", "")).strip()
            user_id = str(item.get("user_id", "")).strip()
            if not license_key:
                continue
            prepared.append(
                {
                    "user_id": user_id,
                    "license_key": license_key,
                    "hwid_uuid": str(item.get("hwid_uuid", "")).strip(),
                    "created_at": item.get("created_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
                }
            )

        if prepared:
            col.insert_many(prepared)

        return True
    except PyMongoError:
        return False
    finally:
        if client:
            client.close()


def export_backup() -> dict:
    """Export current licenses content from MongoDB."""
    return load_licenses()


def import_backup(data: dict) -> bool:
    """Import and restore licenses in MongoDB from backup data."""
    return save_licenses(data)