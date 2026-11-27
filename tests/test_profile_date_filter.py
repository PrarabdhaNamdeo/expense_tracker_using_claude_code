"""Tests for the Step 06 profile date filter."""

import sqlite3
import sys

import pytest

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_path = tmp_path / "spendly-test.db"
    monkeypatch.setattr("database.db.DB_PATH", str(db_path))

    sys.modules.pop("app", None)
    import app as app_module

    # A second user with an expense inside the demo user's test range proves
    # that date filtering never crosses user boundaries.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@example.com", "not-a-real-hash"),
        )
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (2, 999.00, "Shopping", "2023-11-04", "Other user secret spend"),
        )

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as client:
        yield app_module, client


def sign_in(client, user_id=1, name="Demo User"):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = name


def test_no_filter_keeps_step05_defaults(app_client):
    summary = get_summary_stats(1)
    assert summary["transaction_count"] == 8
    assert summary["total_spent"] == pytest.approx(269.50)
    assert summary["top_category"] == "Bills"
    assert len(get_recent_transactions(1)) == 8


def test_default_profile_still_shows_lifetime_numbers(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile").get_data(as_text=True)

    assert "269.50" in body
    assert "Bills" in body
    assert "Showing" not in body


def test_query_helpers_apply_inclusive_bounds(app_client):
    summary = get_summary_stats(1, "2023-11-03", "2023-11-05")
    assert summary == {
        "total_spent": pytest.approx(150.0),
        "transaction_count": 3,
        "top_category": "Bills",
    }

    transactions = get_recent_transactions(
        1, date_from="2023-11-03", date_to="2023-11-05"
    )
    assert [item["date"] for item in transactions] == [
        "2023-11-05",
        "2023-11-04",
        "2023-11-03",
    ]

    categories = get_category_breakdown(1, "2023-11-03", "2023-11-05")
    assert sum(item["pct"] for item in categories) == 100
    bills = next(item for item in categories if item["name"] == "Bills")
    assert bills["amount"] == pytest.approx(80.0)


def test_filtered_profile_shows_only_the_selected_range(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile?from=2023-11-03&to=2023-11-05").get_data(as_text=True)

    assert "Showing 2023-11-03 to 2023-11-05" in body
    assert "150.00" in body
    assert "Internet bill" in body
    assert "Pharmacy" in body
    assert "Movie" in body
    assert "Lunch at cafe" not in body
    assert "2023-11-01" not in body


def test_one_sided_bounds(app_client):
    from_only = get_summary_stats(1, date_from="2023-11-08")
    assert from_only["transaction_count"] == 1
    assert from_only["total_spent"] == pytest.approx(22.0)

    to_only = get_summary_stats(1, date_to="2023-11-02")
    assert to_only["transaction_count"] == 2
    assert to_only["total_spent"] == pytest.approx(27.50)

    _, client = app_client
    sign_in(client)
    body = client.get("/profile?from=2023-11-08").get_data(as_text=True)
    assert "Showing expenses from 2023-11-08" in body
    assert "22.00" in body

    body = client.get("/profile?to=2023-11-02").get_data(as_text=True)
    assert "Showing expenses up to 2023-11-02" in body
    assert "27.50" in body


def test_out_of_range_window_shows_empty_state(app_client):
    assert get_summary_stats(1, "2024-01-01", "2024-01-31") == {
        "total_spent": 0.0,
        "transaction_count": 0,
        "top_category": "—",
    }
    assert get_recent_transactions(1, date_from="2024-01-01", date_to="2024-01-31") == []
    assert get_category_breakdown(1, "2024-01-01", "2024-01-31") == []

    _, client = app_client
    sign_in(client)
    body = client.get("/profile?from=2024-01-01&to=2024-01-31").get_data(as_text=True)

    assert body.count("No expenses match this date range.") == 2
    assert "0.00" in body
    assert "—" in body


def test_malformed_date_is_reported_and_ignored(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile?from=not-a-date").get_data(as_text=True)

    assert "Enter dates as YYYY-MM-DD." in body
    assert "269.50" in body
    assert 'name="from"' in body
    assert 'value="not-a-date"' in body


def test_unpadded_date_is_rejected(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile?from=2023-11-3").get_data(as_text=True)

    assert "Enter dates as YYYY-MM-DD." in body
    assert "269.50" in body


def test_reversed_range_is_reported_and_ignored(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile?from=2023-11-08&to=2023-11-01").get_data(as_text=True)

    assert "Start date must be on or before end date." in body
    assert "269.50" in body


def test_filter_form_and_clear_link(app_client):
    _, client = app_client
    sign_in(client)

    body = client.get("/profile").get_data(as_text=True)

    assert 'class="profile-filter"' in body
    assert 'action="/profile"' in body
    assert 'name="from"' in body
    assert 'name="to"' in body
    assert 'class="profile-filter-clear" href="/profile"' in body


def test_filtered_profile_requires_login(app_client):
    _, client = app_client

    response = client.get("/profile?from=2023-11-03")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_filter_never_leaks_another_users_expenses(app_client):
    _, client = app_client
    sign_in(client, 1, "Demo User")

    body = client.get("/profile?from=2023-11-03&to=2023-11-05").get_data(as_text=True)

    assert "Other user secret spend" not in body
    assert "999.00" not in body

    sign_in(client, 2, "Other User")
    body = client.get("/profile?from=2023-11-03&to=2023-11-05").get_data(as_text=True)

    assert "Other user secret spend" in body
    assert "269.50" not in body
    assert "Demo User" not in body
