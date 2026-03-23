from pathlib import Path
import sys
import os
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, get_flashed_messages, session, send_file
import verify
import backup
import pyotp
import qrcode
import json
from io import BytesIO
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

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

totp_key = "Hsdfisdf4n34234dfiseLoasjfj3asnnvhxbbfgrzzuewwndcodrweokyn"

app = Flask(__name__, template_folder=str(_resolve_template_dir()))
app.secret_key = "ASDfhbsdfseiufhgildsrfrjg874368546987s6e8468f4s"
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", app.secret_key)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
jwt = JWTManager(app)


@app.after_request
def apply_security_headers(response):
    # Apply baseline hardening headers for all endpoints.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")

    # Emit HSTS only for HTTPS requests to avoid breaking local HTTP development.
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    return response


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

def generate_totp_qrcode():
    uri = pyotp.totp.TOTP(totp_key).provisioning_uri(name='',issuer_name='Inventarsystem Lizenz Verwaltung')
    qrcode.make(uri).save("qr.png")

def check_totp(key):
    totp = pyotp.TOTP(totp_key)
    return totp.verify(key)

APP_VERSION = _read_app_version()


def _issue_access_token() -> str:
    return create_access_token(identity="license-validation-client")


@app.route('/access_token', methods=['POST'])
def access_token():
    data = request.get_json(silent=True) or {}
    provided_totp = data.get("totp") or request.form.get("totp") or request.form.get("password")

    if not provided_totp:
        return jsonify({"error": "Missing 'totp' in request"}), 400

    if not check_totp(str(provided_totp)):
        return jsonify({"error": "Invalid credentials"}), 401

    token = _issue_access_token()
    return jsonify({"access_token": token, "token_type": "Bearer"}), 200

@app.route("/validate__information", methods=['POST'])
def validate__information():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    license_key = data.get("license")
    hwid_uuid = data.get("hwid")
    if not license_key or not hwid_uuid:
        return jsonify({"error": "Missing 'license' or 'hwid' in JSON data"}), 400
    if verify.check(license_key, hwid_uuid):
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "invalid"}), 402

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('default'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        totp = data.get("totp") or request.form.get('password') or request.form.get('totp')

        if not totp:
            if request.is_json:
                return jsonify({"error": "Missing TOTP"}), 400
            flash('Please fill all fields', 'error')
            return redirect(url_for('login'))
        
        user_log = check_totp(totp)

        if user_log:
            session['username'] = "Whatareyoulookingfor"
            session['access_token'] = _issue_access_token()

            if request.is_json:
                return jsonify({"access_token": session['access_token'], "token_type": "Bearer"}), 200

            return redirect(url_for('default'))
        else:
            if request.is_json:
                return jsonify({"error": "Invalid credentials"}), 401
            flash('Invalid credentials', 'error')
            get_flashed_messages()

    return render_template('login.html')

@app.route("/")
def default():
    if 'username' not in session:
        return redirect(url_for('login'))

    keys = verify.load_file()
    return render_template("main.html", keys=keys)


@app.route("/generate_new", methods=["POST"])
def generate_new():
    if 'username' not in session:
        return redirect(url_for('login'))

    new_license = verify.new_key()
    flash(f"New key generated: {new_license}", "success")
    return redirect(url_for('default'))


@app.route("/remove_key/<user_id>", methods=["POST"])
def remove_key(user_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if verify.remove_key(user_id):
        flash(f"Key for user {user_id} removed", "success")
    else:
        flash(f"No key found for user {user_id}", "error")

    return redirect(url_for('default'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('access_token', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


@app.route('/download_backup', methods=['GET'])
def download_backup():
    if 'username' not in session:
        return redirect(url_for('login'))

    licenses_data = backup.export_backup()
    json_str = json.dumps(licenses_data, indent=2)
    return send_file(
        BytesIO(json_str.encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name='licenses_backup.json'
    )


@app.route('/upload_backup', methods=['POST'])
def upload_backup():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('default'))

    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('default'))

    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)
        
        if backup.import_backup(data):
            flash('Licenses backup restored successfully', 'success')
        else:
            flash('Failed to restore backup - invalid format', 'error')
    except json.JSONDecodeError:
        flash('Invalid JSON file', 'error')
    except Exception as e:
        flash(f'Error uploading backup: {str(e)}', 'error')

    return redirect(url_for('default'))


def main():
    app.run(host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    main()