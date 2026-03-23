import os
import json
from pathlib import Path

LICENSES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__),"licenses.json"))


def load_licenses() -> dict:
    """Load licenses.json file and return its content."""
    try:
        with open(LICENSES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_licenses(data: dict) -> bool:
    """Save licenses data to licenses.json file."""
    try:
        os.makedirs(os.path.dirname(LICENSES_FILE), exist_ok=True)
        with open(LICENSES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving licenses: {e}")
        return False


def export_backup() -> dict:
    """Export current licenses.json content."""
    return load_licenses()


def import_backup(data: dict) -> bool:
    """Import and restore licenses from backup data."""
    try:
        if not isinstance(data, list):
            return False
        save_licenses(data)
        return True
    except Exception as e:
        print(f"Error importing backup: {e}")
        return False