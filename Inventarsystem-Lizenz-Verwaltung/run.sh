#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${CONDA_DEFAULT_ENV:-}" ]] && command -v conda >/dev/null 2>&1; then
	conda deactivate || true
fi

source .venv/bin/activate

# Do not run apt here because third-party repos in dev containers can fail.
# We only check and provide the install hint if patchelf is missing.
if ! command -v patchelf >/dev/null 2>&1; then
	echo "Error: patchelf is required for Nuitka standalone builds on Linux."
	echo "Install with: sudo apt update && sudo apt install -y patchelf"
	exit 1
fi

pip install -U nuitka ordered-set zstandard flask flask-jwt-extended cryptography pyotp qrcode
python - <<'PY'
from pathlib import Path
import json

root = Path.cwd()
settings_path = root / "settings.json"
version_file = root / "Code" / "version.txt"

version = "0.1.0"
if settings_path.is_file():
		raw = settings_path.read_text(encoding="utf-8").strip()
		if raw:
				data = json.loads(raw)
				if isinstance(data, dict):
						version = str(data.get("version", version)).strip() or version
				elif isinstance(data, list):
						for item in data:
								if isinstance(item, dict) and "version" in item:
										version = str(item.get("version", version)).strip() or version
										break

version_file.write_text(f"{version}\n", encoding="utf-8")
print(f"Prepared {version_file} with version: {version}")
PY
python -m nuitka --standalone --follow-imports --include-data-dir=Code/templates=templates --include-data-dir=Code/static=static --include-data-file=licenses.json=licenses.json --assume-yes-for-downloads --output-dir=Inventarsystem_Lizenz_Verwaltung --remove-output Code/main.py
if [[ -x "./build/main.dist/main.bin" ]]; then
	./build/main.dist/main.bin
else
	echo "Build step finished but executable not found at ./build/main.dist/main.bin"
	exit 1
fi