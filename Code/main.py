from pathlib import Path
import sys
from flask import Flask, render_template
import verify
import requests
import json

def _resolve_template_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "templates",
        Path(sys.argv[0]).resolve().parent / "templates",
        Path.cwd() / "templates",
    ]

    for path in candidates:
        if path.is_dir():
            return path

    return candidates[0]


app = Flask(__name__, template_folder=str(_resolve_template_dir()))


def _read_app_version() -> str:
    candidates = [
        Path(__file__).resolve().parent / "version.txt",
        Path(sys.argv[0]).resolve().parent / "version.txt",
        Path.cwd() / "version.txt",
    ]

    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or "unknown"

    return "unknown"


APP_VERSION = _read_app_version()

@app.route("/_validate__information", methods=['POST'])
def default():
    data = requests.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    license_key = data.get("license")
    hwid_uuid = data.get("hwid")
    if not license_key or not hwid_uuid:
        return jsonify({"error": "Missing 'license' or 'hwid' in JSON data"}), 400
    if verify.check(license_key, hwid_uuid):
        return 200


def main():
    app.run(host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    main()