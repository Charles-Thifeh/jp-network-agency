from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import sqlite3, os, hashlib, secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "jpns.db")

# ── Admin credentials (change these!) ────────────────────────────────────
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "jpns2025"   # plain text – hashed on first compare

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

ADMIN_PASSWORD_HASH = _hash(ADMIN_PASSWORD)

# ── DB setup ──────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name  TEXT NOT NULL,
                last_name   TEXT NOT NULL,
                email       TEXT NOT NULL,
                phone       TEXT NOT NULL,
                service     TEXT NOT NULL,
                message     TEXT,
                status      TEXT DEFAULT 'new',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                email       TEXT NOT NULL,
                phone       TEXT,
                subject     TEXT,
                message     TEXT NOT NULL,
                status      TEXT DEFAULT 'new',
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)

init_db()

# ── Auth helpers ──────────────────────────────────────────────────────────
def logged_in():
    return session.get("admin") is True

def require_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not logged_in():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API  (called by index.html)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/booking", methods=["POST"])
def api_booking():
    d = request.get_json(force=True)
    required = ["first_name", "last_name", "email", "phone", "service"]
    for field in required:
        if not d.get(field, "").strip():
            return jsonify({"ok": False, "error": f"{field} is required"}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO bookings (first_name,last_name,email,phone,service,message) VALUES (?,?,?,?,?,?)",
            (d["first_name"].strip(), d["last_name"].strip(), d["email"].strip(),
             d["phone"].strip(), d["service"].strip(), d.get("message","").strip())
        )
    return jsonify({"ok": True, "message": "Booking received! We'll contact you within 24 hours."})


@app.route("/api/contact", methods=["POST"])
def api_contact():
    d = request.get_json(force=True)
    if not d.get("name","").strip() or not d.get("email","").strip() or not d.get("message","").strip():
        return jsonify({"ok": False, "error": "Name, email and message are required"}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO contacts (name,email,phone,subject,message) VALUES (?,?,?,?,?)",
            (d["name"].strip(), d["email"].strip(), d.get("phone","").strip(),
             d.get("subject","").strip(), d["message"].strip())
        )
    return jsonify({"ok": True, "message": "Message sent! We'll reply within 24 hours."})


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        if username == ADMIN_USERNAME and _hash(password) == ADMIN_PASSWORD_HASH:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid credentials. Please try again."
    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/dashboard")
@require_login
def admin_dashboard():
    with get_db() as db:
        bookings = db.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
        contacts = db.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
        stats = {
            "total_bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
            "new_bookings":   db.execute("SELECT COUNT(*) FROM bookings WHERE status='new'").fetchone()[0],
            "total_contacts": db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            "new_contacts":   db.execute("SELECT COUNT(*) FROM contacts WHERE status='new'").fetchone()[0],
        }
    return render_template("dashboard.html", bookings=bookings, contacts=contacts, stats=stats)


@app.route("/admin/booking/<int:rid>/status", methods=["POST"])
@require_login
def update_booking_status(rid):
    status = request.form.get("status")
    if status in ("new","reviewed","resolved"):
        with get_db() as db:
            db.execute("UPDATE bookings SET status=? WHERE id=?", (status, rid))
    return redirect(url_for("admin_dashboard") + "#bookings")


@app.route("/admin/contact/<int:rid>/status", methods=["POST"])
@require_login
def update_contact_status(rid):
    status = request.form.get("status")
    if status in ("new","reviewed","resolved"):
        with get_db() as db:
            db.execute("UPDATE contacts SET status=? WHERE id=?", (status, rid))
    return redirect(url_for("admin_dashboard") + "#contacts")


@app.route("/admin/booking/<int:rid>/delete", methods=["POST"])
@require_login
def delete_booking(rid):
    with get_db() as db:
        db.execute("DELETE FROM bookings WHERE id=?", (rid,))
    return redirect(url_for("admin_dashboard") + "#bookings")


@app.route("/admin/contact/<int:rid>/delete", methods=["POST"])
@require_login
def delete_contact(rid):
    with get_db() as db:
        db.execute("DELETE FROM contacts WHERE id=?", (rid,))
    return redirect(url_for("admin_dashboard") + "#contacts")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
