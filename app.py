import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

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
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
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


@app.route("/login")
def login():
    return render_template("login.html")


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
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
