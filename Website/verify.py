import os
import secrets
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVOICE_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "invoices")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "Invario_Website")
LICENSE_COLLECTION = "licenses"


def _get_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1200)
    return client, client[MONGO_DB_NAME][LICENSE_COLLECTION]


def _next_user_id(col) -> str:
    existing_ids = []
    for item in col.find({}, {"user_id": 1, "_id": 0}):
        user_id = str(item.get("user_id", "")).strip()
        if user_id.isdigit():
            existing_ids.append(int(user_id))
    next_id = (max(existing_ids) + 1) if existing_ids else 1
    return f"{next_id:04d}"


def load_file() -> list:
    client = None
    try:
        client, col = _get_collection()
        docs = list(col.find({}, {"_id": 0}).sort("created_at", 1))
        return docs
    except PyMongoError:
        return []
    finally:
        if client:
            client.close()

def check(license_key, hwid_uuid) -> bool:
    client = None
    try:
        client, col = _get_collection()
        doc = col.find_one({"license_key": str(license_key)})
        if not doc:
            return False

        current_hwid = str(doc.get("hwid_uuid", ""))
        if current_hwid == str(hwid_uuid):
            return True

        if current_hwid == "":
            col.update_one(
                {"_id": doc.get("_id")},
                {
                    "$set": {
                        "hwid_uuid": str(hwid_uuid),
                        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    }
                },
            )
            return True

        return False
    except PyMongoError:
        return False
    finally:
        if client:
            client.close()

def register_new_Key(data_stream):
    if not isinstance(data_stream, list):
        return False

    client = None
    try:
        client, col = _get_collection()
        col.delete_many({})
        prepared = []
        for item in data_stream:
            if not isinstance(item, dict):
                continue
            prepared.append(
                {
                    "user_id": str(item.get("user_id", "")).strip(),
                    "license_key": str(item.get("license_key", "")).strip(),
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

def new_key() -> str:
    generated_key = key_generator()
    client = None
    try:
        client, col = _get_collection()
        col.insert_one(
            {
                "user_id": _next_user_id(col),
                "license_key": generated_key,
                "hwid_uuid": "",
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        )
    except PyMongoError:
        return ""
    finally:
        if client:
            client.close()

    return generated_key


def remove_key(user_id: str) -> bool:
    client = None
    try:
        client, col = _get_collection()
        result = col.delete_one({"user_id": str(user_id)})
        return result.deleted_count > 0
    except PyMongoError:
        return False
    finally:
        if client:
            client.close()

def key_generator():
    return secrets.token_urlsafe(32)