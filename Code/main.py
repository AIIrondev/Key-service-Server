from pathlib import Path
import sys
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, get_flashed_messages, session, send_file
import verify
import backup
import pyotp
import qrcode
import json
from io import BytesIO

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
        totp = request.form['password']
        if not totp:
            flash('Please fill all fields', 'error')
            return redirect(url_for('login'))
        
        user_log = check_totp(totp)

        if user_log:
            session['username'] = "Whatareyoulookingfor"
            return redirect(url_for('default'))
        else:
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