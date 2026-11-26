import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_db, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

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
# Step 05 — profile data helpers                                      #
# Each marked block is owned by exactly one implementation subagent.  #
# ------------------------------------------------------------------ #

# ===== SUBAGENT 1: TRANSACTION HISTORY (only edit this block) =====
def build_transactions(user_id):
    return get_recent_transactions(user_id, limit=10)


# ===== SUBAGENT 2: SUMMARY (only edit this block) =====
def build_summary(user_id):
    return get_summary_stats(user_id)


# ===== SUBAGENT 3: CATEGORY BREAKDOWN (only edit this block) =====
def build_categories(user_id):
    return get_category_breakdown(user_id)


@app.context_processor
def inject_nav_user():
    """Share the signed-in username with base.html."""
    if session.get("user_id"):
        return {"nav_user": session.get("user_name")}
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

    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=user,
        summary=build_summary(user_id),
        transactions=build_transactions(user_id),
        categories=build_categories(user_id),
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
