import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "spendly.db"

def get_db():
    """Opens connection to spendly.db and sets row_factory and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Creates all tables using CREATE TABLE IF NOT EXISTS."""
    with get_db() as conn:
        # users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # expenses table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.commit()

def seed_db():
    """Inserts demo user and 8 sample expenses if database is empty."""
    with get_db() as conn:
        # Check if users table already contains data
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if user:
            return

        # Insert demo user
        demo_user_data = {
            "name": "Demo User",
            "email": "demo@spendly.com",
            "password_hash": generate_password_hash("demo123")
        }

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (demo_user_data["name"], demo_user_data["email"], demo_user_data["password_hash"])
        )
        user_id = cursor.lastrowid

        # Insert 8 sample expenses across all required categories
        # Categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other
        expenses = [
            (user_id, 15.50, "Food", "2023-11-01", "Lunch at cafe"),
            (user_id, 12.00, "Transport", "2023-11-02", "Bus pass"),
            (user_id, 80.00, "Bills", "2023-11-03", "Internet bill"),
            (user_id, 45.00, "Health", "2023-11-04", "Pharmacy"),
            (user_id, 25.00, "Entertainment", "2023-11-05", "Movie"),
            (user_id, 60.00, "Shopping", "2023-11-06", "New shirt"),
            (user_id, 10.00, "Other", "2023-11-07", "Miscellaneous"),
            (user_id, 22.00, "Food", "2023-11-08", "Dinner"),
        ]

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            expenses
        )
        conn.commit()


def create_user(name, email, password_hash):
    """Inserts a new user and returns the new row id. Raises sqlite3.IntegrityError on duplicate email."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
