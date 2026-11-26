"""Tests for the Step 05 profile backend connection."""

import sqlite3
import sys

import pytest

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_path = tmp_path / "spendly-test.db"
    monkeypatch.setattr("database.db.DB_PATH", str(db_path))

    sys.modules.pop("app", None)
    import app as app_module

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("No Spend", "no-spend@example.com", "not-a-real-hash"),
        )

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as client:
        yield app_module, client


def test_get_user_by_id_returns_profile_fields(app_client):
    user = get_user_by_id(1)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["member_since"].endswith("2026")
    assert user["member_since_iso"][:4] == "2026"
    assert user["initials"] == "DU"


def test_get_user_by_id_missing_returns_none(app_client):
    assert get_user_by_id(9999) is None


def test_summary_stats_for_seed_user(app_client):
    summary = get_summary_stats(1)
    assert summary["transaction_count"] == 8
    assert summary["total_spent"] == pytest.approx(269.50)
    assert summary["top_category"] == "Bills"


def test_summary_stats_for_user_without_expenses(app_client):
    assert get_summary_stats(2) == {
        "total_spent": 0.0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions_are_newest_first(app_client):
    transactions = get_recent_transactions(1)
    assert len(transactions) == 8
    assert transactions[0]["date"] == "2023-11-08"
    assert transactions[-1]["date"] == "2023-11-01"
    assert set(transactions[0]) == {"date", "description", "category", "amount"}


def test_recent_transactions_empty_for_new_user(app_client):
    assert get_recent_transactions(2) == []


def test_category_breakdown_sums_to_100(app_client):
    categories = get_category_breakdown(1)
    assert [item["name"] for item in categories] == [
        "Food",
        "Transport",
        "Bills",
        "Health",
        "Entertainment",
        "Shopping",
        "Other",
    ]
    assert sum(item["pct"] for item in categories) == 100
    bills = next(item for item in categories if item["name"] == "Bills")
    assert bills["amount"] == pytest.approx(80.00)
    assert bills["pct"] == max(item["pct"] for item in categories)


def test_category_breakdown_empty_for_new_user(app_client):
    assert get_category_breakdown(2) == []


def test_profile_redirects_when_signed_out(app_client):
    _, client = app_client
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_renders_live_seed_data(app_client):
    _, client = app_client
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["user_name"] = "Demo User"

    response = client.get("/profile")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "November 2026" in body
    assert "269.50" in body
    assert "Bills" in body
    assert "₹" in body


def test_profile_for_user_without_expenses(app_client):
    _, client = app_client
    with client.session_transaction() as session:
        session["user_id"] = 2
        session["user_name"] = "No Spend"

    body = client.get("/profile").get_data(as_text=True)
    assert "No Spend" in body
    assert "0.00" in body
    assert "Demo User" not in body
