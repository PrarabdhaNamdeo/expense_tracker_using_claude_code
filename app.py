import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_db, init_db, seed_db

app = Flask(__name__)

# Secret key required for session-based flash messages.
# Set SECRET_KEY in the environment for production; this fallback is for local development only.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")

# Initialize and seed database on startup
with app.app_context():
    init_db()
    seed_db()


def validate_registration(name, email, password):
    """Returns an error message for invalid registration input, or None if valid."""
    if not name or not email or not password:
        return "All fields are required."
    if not 1 <= len(name) <= 100:
        return "Please enter a valid name (1-100 characters)."

    local_part, separator, domain = email.partition("@")
    if not separator or "@" in domain or not local_part or "." not in domain:
        return "Please enter a valid email address."

    if len(password) < 8:
        return "Password must be at least 8 characters."

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
    if existing:
        return "An account with this email already exists."

    return None


# ------------------------------------------------------------------ #
# Hardcoded profile preview data — Step 05 replaces this with DB reads #
# ------------------------------------------------------------------ #

PROFILE_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "member_since": "2023-11-01",
    "initials": "DU",
}

PROFILE_SUMMARY = {
    "total_spent": 269.50,
    "transaction_count": 8,
    "top_category": "Bills",
}

PROFILE_TRANSACTIONS = [
    {"date": "2023-11-08", "description": "Dinner", "category": "Food", "amount": 22.00},
    {"date": "2023-11-06", "description": "New shirt", "category": "Shopping", "amount": 60.00},
    {"date": "2023-11-05", "description": "Movie", "category": "Entertainment", "amount": 25.00},
    {"date": "2023-11-04", "description": "Pharmacy", "category": "Health", "amount": 45.00},
    {"date": "2023-11-03", "description": "Internet bill", "category": "Bills", "amount": 80.00},
    {"date": "2023-11-02", "description": "Bus pass", "category": "Transport", "amount": 12.00},
]

PROFILE_CATEGORIES = [
    {"category": "Bills", "total": 80.00, "percent": 30},
    {"category": "Shopping", "total": 60.00, "percent": 22},
    {"category": "Health", "total": 45.00, "percent": 17},
    {"category": "Food", "total": 37.50, "percent": 14},
    {"category": "Entertainment", "total": 25.00, "percent": 9},
    {"category": "Transport", "total": 12.00, "percent": 4},
    {"category": "Other", "total": 10.00, "percent": 4},
]


@app.context_processor
def inject_nav_user():
    """Share the signed-in username with base.html."""
    if session.get("user_id"):
        return {"nav_user": session.get("user_name", PROFILE_USER["name"])}
    return {"nav_user": None}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = validate_registration(name, email, password)
    if error:
        return render_template("register.html", error=error, name=name, email=email)

    try:
        create_user(name, email, generate_password_hash(password))
    except sqlite3.IntegrityError:
        # Handles the race between the duplicate check and the INSERT.
        return render_template(
            "register.html",
            error="An account with this email already exists.",
            name=name,
            email=email,
        )

    flash("Account created successfully. Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html", error="Email and password are required.", email=email
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    flash("Signed in successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=PROFILE_USER,
        summary=PROFILE_SUMMARY,
        transactions=PROFILE_TRANSACTIONS,
        categories=PROFILE_CATEGORIES,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
