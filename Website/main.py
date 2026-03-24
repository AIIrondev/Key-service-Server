from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, get_flashed_messages, session
import os
import json
import calendar
from datetime import timedelta, datetime, date
from pathlib import Path
from functools import wraps
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
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", app.secret_key)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PREFERRED_URL_SCHEME"] = "https" if os.environ.get("SESSION_COOKIE_SECURE") == "1" else "http"
jwt = JWTManager(app)


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; img-src 'self' data:; connect-src 'self';"
    return response

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INVOICE_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "invoices"
USERS_FILE = DATA_DIR / "users.json"
APPOINTMENTS_FILE = DATA_DIR / "appointments.json"
POSTS_FILE = DATA_DIR / "posts.json"
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "Inventarsystem")


def _issue_access_token() -> str:
    return create_access_token(identity="license-validation-client")


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _is_allowed_invoice_filename(filename: str) -> bool:
    return bool(filename) and filename.lower().endswith(".pdf")


def _save_invoice_pdf(file_obj, invoice_number: str) -> str | None:
    if not file_obj or not file_obj.filename:
        return None
    original_name = secure_filename(file_obj.filename)
    if not _is_allowed_invoice_filename(original_name):
        return None
    INVOICE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_invoice = secure_filename(invoice_number or "invoice")
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_invoice}_{original_name}"
    target = INVOICE_UPLOAD_DIR / unique_name
    file_obj.save(target)
    return f"uploads/invoices/{unique_name}"


def _get_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=1200)


def _get_mongo_db():
    client = _get_mongo_client()
    return client, client[MONGO_DB_NAME]


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


def _ensure_user_license(username: str, display_name: str) -> None:
    client = None
    try:
        client, licenses = _get_collection("licenses")
        if licenses.find_one({"username": username}):
            return
        licenses.insert_one(
            {
                "username": username,
                "school_name": f"{display_name} Schule",
                "license_key": f"LIC-{int(datetime.utcnow().timestamp())}-{username[:3].upper()}",
                "plan": "Standard",
                "status": "Aktiv",
                "valid_until": "2027-12-31",
                "created_at": _utc_now_iso(),
            }
        )
    except PyMongoError:
        return
    finally:
        if client:
            client.close()


def _ensure_user_invoice(username: str) -> None:
    client = None
    try:
        client, invoices = _get_collection("invoices")
        if invoices.find_one({"username": username}):
            return
        invoices.insert_one(
            {
                "username": username,
                "invoice_number": f"INV-{datetime.utcnow().strftime('%Y%m')}-{username[:3].upper()}",
                "period": datetime.utcnow().strftime("%m/%Y"),
                "amount_eur": 79.0,
                "status": "Offen",
                "due_date": "2026-12-31",
                "pdf_path": "",
                "created_at": _utc_now_iso(),
            }
        )
    except PyMongoError:
        return
    finally:
        if client:
            client.close()


def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")
    if not APPOINTMENTS_FILE.exists():
        APPOINTMENTS_FILE.write_text("[]", encoding="utf-8")
    if not POSTS_FILE.exists():
        POSTS_FILE.write_text("[]", encoding="utf-8")


def _read_json(file_path: Path) -> list:
    _ensure_data_files()
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _write_json(file_path: Path, payload: list) -> None:
    _ensure_data_files()
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _sanitize_text(text: str, max_length: int = 255) -> str:
    """Sanitize user text input: strip, limit length, and escape HTML."""
    text = (text or "").strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text


def _sanitize_html(html_content: str, max_length: int = 50000) -> str:
    """Sanitize HTML content: allow safe tags only."""
    if not html_content:
        return ""
    html_content = html_content[:max_length]
    allowed_tags = ["p", "br", "strong", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "blockquote", "code", "pre"]
    allowed_attrs = {"a": ["href", "title"]}
    return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)


def _validate_username(username: str) -> bool:
    """Validate username format: alphanumeric, underscore, dash, 3-30 chars."""
    if not username or not isinstance(username, str):
        return False
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return False
    return all(c.isalnum() or c in "_-" for c in username)


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
    return render_template("team.html")


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
            session['access_token'] = _issue_access_token()
            _ensure_user_license(session['username'], session['display_name'])
            _ensure_user_invoice(session['username'])

            if request.is_json:
                return jsonify({"access_token": session['access_token'], "token_type": "Bearer"}), 200

            return redirect(url_for('default'))

        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        flash('Login fehlgeschlagen. Bitte pruefen Sie Ihre Eingaben.', 'error')
        get_flashed_messages()

    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        display_name = (request.form.get("display_name") or "").strip()
        password = request.form.get("password") or ""
        password_repeat = request.form.get("password_repeat") or ""

        if not username or not display_name or not password or not password_repeat:
            flash("Bitte alle Felder ausfuellen.", "error")
            return redirect(url_for("register"))

        if not _validate_username(username):
            flash("Benutzername muss 3-30 Zeichen lang sein und nur Buchstaben, Zahlen, - und _ enthalten.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Das Passwort muss mindestens 8 Zeichen haben.", "error")
            return redirect(url_for("register"))

        if password != password_repeat:
            flash("Die Passwoerter stimmen nicht ueberein.", "error")
            return redirect(url_for("register"))

        if _find_user(username):
            flash("Benutzername bereits vergeben.", "error")
            return redirect(url_for("register"))

        display_name = _sanitize_text(display_name, 100)

        try:
            existing_users = user_store.get_all_users() or []
            is_first_user = len(existing_users) == 0
            if not user_store.add_user(username, password, display_name, ""):
                flash("Benutzer konnte nicht erstellt werden.", "error")
                return redirect(url_for("register"))
            if is_first_user:
                user_store.make_admin(username)
        except Exception:
            flash("MongoDB ist derzeit nicht erreichbar.", "error")
            return redirect(url_for("register"))

        flash("Registrierung erfolgreich. Bitte jetzt einloggen.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/appointments', methods=['GET', 'POST'])
@login_required
def appointments():
    today = date.today()
    month = request.args.get("month", type=int) or today.month
    year = request.args.get("year", type=int) or today.year

    month = 1 if month < 1 else 12 if month > 12 else month
    year = 1970 if year < 1970 else year

    if request.method == 'POST':
        selected_date = (request.form.get("selected_date") or "").strip()
        appointment_time = (request.form.get("appointment_time") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        note = (request.form.get("note") or "").strip()

        try:
            date.fromisoformat(selected_date)
        except ValueError:
            flash("Bitte einen gueltigen Termin im Kalender auswaehlen.", "error")
            return redirect(url_for("appointments", month=month, year=year))

        if not appointment_time or not subject:
            flash("Bitte Uhrzeit und Betreff ausfuellen.", "error")
            return redirect(url_for("appointments", month=month, year=year))

        subject = _sanitize_text(subject, 200)
        note = _sanitize_text(note, 2000)

        entries = _read_json(APPOINTMENTS_FILE)
        entries.append(
            {
                "id": f"a-{int(datetime.utcnow().timestamp() * 1000)}",
                "username": session.get("username"),
                "display_name": session.get("display_name"),
                "date": selected_date,
                "time": appointment_time,
                "subject": subject,
                "note": note,
                "status": "Angefragt",
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        )
        _write_json(APPOINTMENTS_FILE, entries)

        flash("Termin erfolgreich angefragt.", "success")
        selected = date.fromisoformat(selected_date)
        return redirect(url_for("appointments", month=selected.month, year=selected.year))

    cal = calendar.Calendar(firstweekday=0)
    month_grid = cal.monthdayscalendar(year, month)
    month_name = calendar.month_name[month]

    previous_month = month - 1
    previous_year = year
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    all_appointments = _read_json(APPOINTMENTS_FILE)
    user_appointments = [item for item in all_appointments if item.get("username") == session.get("username")]
    user_appointments.sort(key=lambda item: (item.get("date", ""), item.get("time", "")), reverse=False)

    return render_template(
        "appointments.html",
        month=month,
        month_name=month_name,
        year=year,
        month_grid=month_grid,
        today_iso=today.isoformat(),
        previous_month=previous_month,
        previous_year=previous_year,
        next_month=next_month,
        next_year=next_year,
        user_appointments=user_appointments,
    )


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    all_appointments = _read_json(APPOINTMENTS_FILE)
    all_appointments.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)
    
    status_counts = {
        "Angefragt": len([a for a in all_appointments if a.get("status") == "Angefragt"]),
        "Bestaetigt": len([a for a in all_appointments if a.get("status") == "Bestaetigt"]),
        "Abgelehnt": len([a for a in all_appointments if a.get("status") == "Abgelehnt"]),
    }
    
    posts = _read_json(POSTS_FILE)
    total_posts = len(posts)
    
    return render_template(
        "admin_dashboard.html",
        appointments=all_appointments,
        status_counts=status_counts,
        total_posts=total_posts,
    )


@app.route('/admin/appointment/<appointment_id>', methods=['POST'])
@admin_required
def update_appointment(appointment_id):
    action = request.form.get("action", "").strip()
    response_text = _sanitize_text(request.form.get("response") or "", 5000)
    
    if action not in ["confirm", "reject"]:
        flash("Ungueltige Aktion.", "error")
        return redirect(url_for("admin_dashboard"))
    
    all_appointments = _read_json(APPOINTMENTS_FILE)
    appointment = None
    for item in all_appointments:
        if item.get("id") == appointment_id:
            appointment = item
            break
    
    if not appointment:
        flash("Termin nicht gefunden.", "error")
        return redirect(url_for("admin_dashboard"))
    
    if action == "confirm":
        appointment["status"] = "Bestaetigt"
    else:
        appointment["status"] = "Abgelehnt"
    
    appointment["response"] = response_text
    appointment["responded_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    appointment["responded_by"] = session.get("username")
    
    _write_json(APPOINTMENTS_FILE, all_appointments)
    flash(f"Termin wurde {('bestaetigt' if action == 'confirm' else 'abgelehnt')}.", "success")
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
                flash("Bitte Titel und inhalt ausfuellen.", "error")
                return redirect(url_for("admin_blog"))
            
            posts = _read_json(POSTS_FILE)
            posts.append({
                "id": f"p-{int(datetime.utcnow().timestamp() * 1000)}",
                "title": title,
                "excerpt": excerpt or (content[:150] + "...") if len(content) > 150 else content,
                "content": content,
                "author": session.get("username"),
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "published": True,
            })
            _write_json(POSTS_FILE, posts)
            flash("Beitrag veroeffentlicht.", "success")
            return redirect(url_for("admin_blog"))
        
        elif action == "delete":
            post_id = (request.form.get("post_id") or "").strip()
            if not post_id or not post_id.startswith("p-"):
                flash("Ungueltige Beitrag-ID.", "error")
                return redirect(url_for("admin_blog"))
            posts = _read_json(POSTS_FILE)
            original_count = len(posts)
            posts = [p for p in posts if p.get("id") != post_id]
            if len(posts) == original_count:
                flash("Beitrag nicht gefunden.", "error")
                return redirect(url_for("admin_blog"))
            _write_json(POSTS_FILE, posts)
            flash("Beitrag geloescht.", "success")
            return redirect(url_for("admin_blog"))
    
    posts = _read_json(POSTS_FILE)
    posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("admin_blog.html", posts=posts)


@app.route('/blog')
def blog():
    posts = _read_json(POSTS_FILE)
    posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template("blog.html", posts=posts)


@app.route('/blog/<post_id>')
def blog_post(post_id):
    if not post_id or not post_id.startswith("p-"):
        flash("Ungueltige Beitrag-ID.", "error")
        return redirect(url_for("blog"))
    
    posts = _read_json(POSTS_FILE)
    post = None
    for p in posts:
        if p.get("id") == post_id:
            post = p
            break
    
    if not post:
        flash("Beitrag nicht gefunden.", "error")
        return redirect(url_for("blog"))
    
    return render_template("blog_post.html", post=post)


@app.route('/my/licenses', methods=['GET', 'POST'])
@login_required
def my_licenses():
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "", 30)
        license_id = _sanitize_text(request.form.get("license_id") or "", 64)
        target_username = _sanitize_text(request.form.get("target_username") or "", 80)

        if action != "transfer" or not license_id or not target_username:
            flash("Ungueltige Weitergabe-Angaben.", "error")
            return redirect(url_for("my_licenses"))

        if target_username == session.get("username"):
            flash("Bitte einen anderen Nutzer waehlen.", "error")
            return redirect(url_for("my_licenses"))

        client = None
        try:
            client, col = _get_collection("licenses")
            result = col.update_one(
                {"_id": ObjectId(license_id), "username": session.get("username")},
                {
                    "$set": {
                        "username": target_username,
                        "transferred_at": _utc_now_iso(),
                        "transferred_by": session.get("username"),
                    }
                },
            )
            if result.modified_count:
                flash("Lizenz wurde erfolgreich weitergegeben.", "success")
            else:
                flash("Lizenz konnte nicht weitergegeben werden.", "error")
        except Exception:
            flash("Weitergabe fehlgeschlagen.", "error")
        finally:
            if client:
                client.close()
        return redirect(url_for("my_licenses"))

    licenses = []
    client = None
    try:
        client, col = _get_collection("licenses")
        licenses = list(col.find({"username": session.get("username")}).sort("created_at", -1))
        for item in licenses:
            item["id"] = str(item.get("_id"))
    except PyMongoError:
        flash("Lizenzdaten konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    transfer_users = [u for u in _list_users_for_admin() if u.get("username") != session.get("username")]
    return render_template("my_licenses.html", licenses=licenses, transfer_users=transfer_users)


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
            flash("Bitte Titel und Beschreibung ausfuellen.", "error")
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
                flash("Sie koennen Ihr eigenes Konto nicht loeschen.", "error")
                return redirect(url_for("admin_users"))
            user_store.delete_user(username)
            flash("Benutzer geloescht.", "success")
        else:
            flash("Ungueltige Aktion.", "error")
        return redirect(url_for("admin_users"))

    users = _list_users_for_admin()
    return render_template("admin_users.html", users=users)


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


@app.route('/admin/licenses', methods=['GET', 'POST'])
@admin_required
def admin_licenses():
    client = None
    if request.method == 'POST':
        action = _sanitize_text(request.form.get("action") or "", 50)
        license_id = _sanitize_text(request.form.get("license_id") or "", 64)

        try:
            client, col = _get_collection("licenses")

            if action == "create":
                username = _sanitize_text(request.form.get("username") or "", 80)
                school_name = _sanitize_text(request.form.get("school_name") or "", 200)
                license_key = _sanitize_text(request.form.get("license_key") or "", 120)
                plan = _sanitize_text(request.form.get("plan") or "Standard", 80)
                status = _sanitize_text(request.form.get("status") or "Aktiv", 40)
                valid_until = _sanitize_text(request.form.get("valid_until") or "", 40)

                if not username or not school_name:
                    flash("Bitte Benutzername und Schule angeben.", "error")
                    return redirect(url_for("admin_licenses"))

                col.insert_one(
                    {
                        "username": username,
                        "school_name": school_name,
                        "license_key": license_key or f"LIC-{int(datetime.utcnow().timestamp())}-{username[:3].upper()}",
                        "plan": plan,
                        "status": status,
                        "valid_until": valid_until or "2027-12-31",
                        "created_at": _utc_now_iso(),
                    }
                )
                flash("Lizenz angelegt.", "success")

            elif action == "update" and license_id:
                col.update_one(
                    {"_id": ObjectId(license_id)},
                    {
                        "$set": {
                            "school_name": _sanitize_text(request.form.get("school_name") or "", 200),
                            "license_key": _sanitize_text(request.form.get("license_key") or "", 120),
                            "plan": _sanitize_text(request.form.get("plan") or "Standard", 80),
                            "status": _sanitize_text(request.form.get("status") or "Aktiv", 40),
                            "valid_until": _sanitize_text(request.form.get("valid_until") or "", 40),
                        }
                    },
                )
                flash("Lizenz aktualisiert.", "success")

            elif action == "transfer" and license_id:
                target_username = _sanitize_text(request.form.get("target_username") or "", 80)
                if not target_username:
                    flash("Bitte Zielnutzer waehlen.", "error")
                    return redirect(url_for("admin_licenses"))

                col.update_one(
                    {"_id": ObjectId(license_id)},
                    {
                        "$set": {
                            "username": target_username,
                            "transferred_at": _utc_now_iso(),
                            "transferred_by": session.get("username"),
                        }
                    },
                )
                flash("Lizenz weitergegeben.", "success")

            elif action == "delete" and license_id:
                col.delete_one({"_id": ObjectId(license_id)})
                flash("Lizenz geloescht.", "success")
            else:
                flash("Ungueltige Aktion.", "error")
        except Exception:
            flash("Lizenzverwaltung fehlgeschlagen.", "error")
        finally:
            if client:
                client.close()

        return redirect(url_for("admin_licenses"))

    licenses = []
    try:
        client, col = _get_collection("licenses")
        licenses = list(col.find().sort("created_at", -1))
        for item in licenses:
            item["id"] = str(item.get("_id"))
    except PyMongoError:
        flash("Lizenzen konnten nicht geladen werden.", "error")
    finally:
        if client:
            client.close()

    users = _list_users_for_admin()
    return render_template("admin_licenses.html", licenses=licenses, users=users)


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
                flash("Rechnung geloescht.", "success")
            else:
                flash("Ungueltige Aktion.", "error")
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
    session.pop('access_token', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


def main():
    app.run(host="0.0.0.0", port=4999, debug=False)

if __name__ == "__main__":
    main()