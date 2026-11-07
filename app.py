from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "eventease-demo-secret-key"
DB = "database.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        location TEXT NOT NULL,
        category TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        image TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registered_at TEXT NOT NULL,
        UNIQUE(user_id, event_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    """)
    admin = conn.execute("SELECT id FROM users WHERE email=?", ("admin@eventease.com",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
            ("Administrator", "admin@eventease.com",
             generate_password_hash("admin123"), "admin", datetime.now().isoformat())
        )
    if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        sample = [
            ("Tech Innovation Summit", "A full-day summit exploring cloud computing, AI, cybersecurity and the future of technology.",
             "2026-09-12", "09:30 AM", "Main Auditorium", "Technology", 300,
             "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=1200&q=80"),
            ("Campus Cultural Fest", "A vibrant celebration featuring music, dance, art, food and student performances.",
             "2026-09-20", "04:00 PM", "College Open Ground", "Cultural", 800,
             "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1200&q=80"),
            ("Entrepreneurship Meetup", "Meet founders, innovators and aspiring entrepreneurs and learn how ideas become businesses.",
             "2026-10-03", "10:00 AM", "Innovation Lab", "Business", 150,
             "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=1200&q=80"),
            ("Photography Workshop", "Hands-on workshop covering composition, lighting, portrait photography and editing.",
             "2026-10-11", "02:00 PM", "Creative Studio", "Workshop", 60,
             "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1200&q=80"),
            ("Sports Championship", "Inter-department sports championship with football, cricket, volleyball and athletics.",
             "2026-10-18", "08:00 AM", "College Stadium", "Sports", 500,
             "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80"),
            ("Developer Hackathon", "Build, collaborate and present innovative software solutions in a 24-hour coding challenge.",
             "2026-11-07", "09:00 AM", "Computer Science Block", "Technology", 200,
             "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1200&q=80")
        ]
        conn.executemany("""INSERT INTO events(title,description,date,time,location,category,capacity,image,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                         [(*e, datetime.now().isoformat()) for e in sample])
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}

@app.route("/")
def home():
    conn = get_db()
    events = conn.execute("SELECT * FROM events ORDER BY date ASC LIMIT 6").fetchall()
    conn.close()
    return render_template("index.html", events=events)

@app.route("/events")
def events():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    conn = get_db()
    sql = "SELECT * FROM events WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE ? OR description LIKE ? OR location LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY date ASC"
    rows = conn.execute(sql, params).fetchall()
    categories = conn.execute("SELECT DISTINCT category FROM events ORDER BY category").fetchall()
    conn.close()
    return render_template("events.html", events=rows, categories=categories, q=q, category=category)

@app.route("/event/<int:event_id>")
def event_details(event_id):
    conn = get_db()
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    registered = False
    if session.get("user_id"):
        registered = conn.execute("SELECT id FROM registrations WHERE user_id=? AND event_id=?",
                                   (session["user_id"], event_id)).fetchone() is not None
    conn.close()
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("events"))
    return render_template("event_details.html", event=event, registered=registered)

@app.route("/register-event/<int:event_id>", methods=["POST"])
@login_required
def register_event(event_id):
    conn = get_db()
    try:
        conn.execute("INSERT INTO registrations(user_id,event_id,registered_at) VALUES(?,?,?)",
                     (session["user_id"], event_id, datetime.now().isoformat()))
        conn.commit()
        flash("You are successfully registered for this event!", "success")
    except sqlite3.IntegrityError:
        flash("You are already registered for this event.", "warning")
    finally:
        conn.close()
    return redirect(url_for("event_details", event_id=event_id))

@app.route("/cancel-registration/<int:event_id>", methods=["POST"])
@login_required
def cancel_registration(event_id):
    conn = get_db()
    conn.execute("DELETE FROM registrations WHERE user_id=? AND event_id=?", (session["user_id"], event_id))
    conn.commit()
    conn.close()
    flash("Registration cancelled.", "info")
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "warning")
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute("INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
                         (name, email, generate_password_hash(password), "user", datetime.now().isoformat()))
            conn.commit()
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    registrations = conn.execute("""
        SELECT e.*, r.registered_at FROM registrations r
        JOIN events e ON e.id=r.event_id
        WHERE r.user_id=? ORDER BY e.date ASC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("dashboard.html", user=user, registrations=registrations)

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    events = conn.execute("""
        SELECT e.*, COUNT(r.id) AS registrations
        FROM events e LEFT JOIN registrations r ON e.id=r.event_id
        GROUP BY e.id ORDER BY e.date ASC
    """).fetchall()
    users = conn.execute("SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()
    registrations = conn.execute("""
        SELECT r.id, r.registered_at, u.name AS user_name, u.email, e.title AS event_title
        FROM registrations r JOIN users u ON u.id=r.user_id JOIN events e ON e.id=r.event_id
        ORDER BY r.registered_at DESC
    """).fetchall()
    stats = {
        "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "registrations": conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    }
    conn.close()
    return render_template("admin.html", events=events, users=users, registrations=registrations, stats=stats)

@app.route("/admin/event/new", methods=["GET", "POST"])
@admin_required
def create_event():
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in
                ["title","description","date","time","location","category","capacity","image"]]
        try:
            capacity = int(data[6])
            if capacity < 1:
                raise ValueError
        except ValueError:
            flash("Capacity must be a positive number.", "danger")
            return render_template("create_event.html", event=None)
        conn = get_db()
        conn.execute("""INSERT INTO events(title,description,date,time,location,category,capacity,image,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)""", (*data[:6], capacity, data[7], datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash("Event created successfully.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("create_event.html", event=None)

@app.route("/admin/event/<int:event_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_event(event_id):
    conn = get_db()
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not event:
        conn.close()
        flash("Event not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in
                ["title","description","date","time","location","category","capacity","image"]]
        try:
            capacity = int(data[6])
        except ValueError:
            flash("Capacity must be a number.", "danger")
            conn.close()
            return render_template("create_event.html", event=event)
        conn.execute("""UPDATE events SET title=?,description=?,date=?,time=?,location=?,category=?,capacity=?,image=?
                        WHERE id=?""", (*data[:6], capacity, data[7], event_id))
        conn.commit()
        conn.close()
        flash("Event updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))
    conn.close()
    return render_template("create_event.html", event=event)

@app.route("/admin/event/<int:event_id>/delete", methods=["POST"])
@admin_required
def delete_event(event_id):
    conn = get_db()
    conn.execute("DELETE FROM registrations WHERE event_id=?", (event_id,))
    conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    flash("Event deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
