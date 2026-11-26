"""Read-only query helpers for the Spendly profile page.

All functions use raw sqlite3 through ``database.db.get_db()``, parameterised
SQL only, and close their connection before returning.
"""

from datetime import datetime

from database.db import get_db

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


def get_user_by_id(user_id):
    """Return profile-ready account data, or None when the user is missing."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created_at = row["created_at"] or ""
    member_since_iso = created_at[:10]
    try:
        member_since = datetime.strptime(member_since_iso, "%Y-%m-%d").strftime("%B %Y")
    except ValueError:
        member_since = member_since_iso

    name = row["name"]
    initials = "".join(part[0] for part in name.split()[:2]).upper()

    return {
        "name": name,
        "email": row["email"],
        "member_since": member_since,
        "member_since_iso": member_since_iso,
        "initials": initials,
    }


def get_summary_stats(user_id):
    """Return total spent, transaction count, and top category for a user."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COUNT(*) AS transaction_count, "
            "COALESCE(SUM(amount), 0) AS total_spent "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if totals["transaction_count"] == 0:
            return {
                "total_spent": 0.0,
                "transaction_count": 0,
                "top_category": "—",
            }

        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": float(totals["total_spent"]),
        "transaction_count": int(totals["transaction_count"]),
        "top_category": top["category"],
    }


def get_recent_transactions(user_id, limit=10):
    """Return the newest expenses for a user as template-ready dicts."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["date"],
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_category_breakdown(user_id):
    """Return the seven fixed categories with integer percentages summing to 100."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    totals = {row["category"]: float(row["total"]) for row in rows}
    grand_total = sum(totals.values())

    raw = {
        category: (totals.get(category, 0.0) / grand_total * 100) if grand_total else 0.0
        for category in CATEGORIES
    }
    percentages = {category: int(value) for category, value in raw.items()}

    remainder = 100 - sum(percentages.values())
    if remainder:
        largest = max(CATEGORIES, key=lambda category: (totals.get(category, 0.0), raw[category]))
        percentages[largest] += remainder

    return [
        {
            "name": category,
            "amount": totals.get(category, 0.0),
            "pct": percentages[category],
        }
        for category in CATEGORIES
    ]
