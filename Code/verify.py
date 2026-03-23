import json
import os
import secrets

LICENSES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "licenses.json"))


def load_file() -> dict:
    with open(LICENSES_FILE, "r") as f:
        data = json.load(f)
        return data

def check(license_key, hwid_uuid) -> bool:
    data = load_file()
    for i in data:
        if str(i["license_key"]) == str(license_key):
            if str(i["hwid_uuid"]) == str(hwid_uuid):
                return True
            elif str(i["hwid_uuid"]) == "":
                i["hwid_uuid"] = str(hwid_uuid)
                register_new_Key(data)
                return True
    return False

def register_new_Key(data_stream):
    with open(LICENSES_FILE, "w") as f:
        json.dump(data_stream, f, indent=2)

def new_key() -> str:
    data = load_file()
    existing_ids = []
    for item in data:
        user_id = str(item.get("user_id", "")).strip()
        if user_id.isdigit():
            existing_ids.append(int(user_id))

    next_id = (max(existing_ids) + 1) if existing_ids else 1
    generated_key = key_generator()
    data.append(
        {
            "user_id": f"{next_id:04d}",
            "license_key": generated_key,
            "hwid_uuid": "",
        }
    )
    register_new_Key(data)
    return generated_key


def remove_key(user_id: str) -> bool:
    data = load_file()
    filtered = [item for item in data if str(item.get("user_id", "")) != str(user_id)]

    if len(filtered) == len(data):
        return False

    register_new_Key(filtered)
    return True

def key_generator():
    return secrets.token_urlsafe(32)