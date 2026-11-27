"""Behaviour tests for the optional /profile date filter (Step 06).

Expectations come from .opencode/specs/06-date-filter-for-profile-page.md.
Each test runs against a freshly seeded temporary database, so spendly.db is
never touched and tests do not depend on one another.
"""

import importlib
import re
import sqlite3
import sys
from html import unescape
from pathlib import Path

import pytest

from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

DEMO_DB_FILENAME = "spendly-test.db"
DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
SECOND_EMAIL = "second@example.com"
SECOND_PASSWORD = "second123"

# Distinctive category names; "Other" is omitted because it can occur in
# unrelated page copy, which would make the empty-breakdown assertion noisy.
CATEGORY_NAMES_WITH_EXPENSES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
)


# --------------------------------------------------------------------------- #
# Fixtures and small verification helpers                                      #
# --------------------------------------------------------------------------- #

def _db_path(tmp_path):
    return Path(tmp_path) / DEMO_DB_FILENAME


def _fetch_user_row(db_path, email):
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT id, name FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def _insert_expense(db_path, user_id, amount, category, date, description):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A Flask test client backed by a newly seeded temporary database."""
    monkeypatch.setattr("database.db.DB_PATH", str(_db_path(tmp_path)))
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def demo_user_id(client, tmp_path):
    """Primary key of the seeded demo account."""
    row = _fetch_user_row(_db_path(tmp_path), DEMO_EMAIL)
    assert row is not None, "startup seeding must create the demo account"
    return row[0]


@pytest.fixture()
def demo_client(client, demo_user_id, tmp_path):
    """A test client already signed in as the seeded demo user."""
    row = _fetch_user_row(_db_path(tmp_path), DEMO_EMAIL)
    with client.session_transaction() as session:
        session["user_id"] = row[0]
        session["user_name"] = row[1]
    return client


def _register_and_sign_in_second_user(client, db_path):
    """Create a second account through the app and sign in as it."""
    with client.session_transaction() as session:
        session.clear()

    registered = client.post(
        "/register",
        data={
            "name": "Second User",
            "email": SECOND_EMAIL,
            "password": SECOND_PASSWORD,
        },
    )
    assert registered.status_code == 302

    signed_in = client.post(
        "/login", data={"email": SECOND_EMAIL, "password": SECOND_PASSWORD}
    )
    assert signed_in.status_code == 302

    row = _fetch_user_row(db_path, SECOND_EMAIL)
    assert row is not None
    return row[0]


def _html(response):
    return response.data.decode("utf-8")


def _visible_text(response):
    """Strip markup so assertions target what a person can actually read."""
    raw = _html(response)
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _assert_amount(text, amount):
    formatted = f"{amount:.2f}"
    assert re.search(r"₹\s*" + re.escape(formatted), text), (
        f"expected a rupee amount of {formatted} on the profile page"
    )


def _assert_no_amount(text, amount):
    formatted = f"{amount:.2f}"
    assert not re.search(r"₹\s*" + re.escape(formatted), text), (
        f"the rupee amount {formatted} should not be visible on this page"
    )


def _assert_transaction_count(text, expected):
    number = str(expected)
    pattern = (
        rf"\b{number}\s*(?:total\s+)?transactions\b|"
        rf"\btransactions\b\s*:?\s*{number}\b"
    )
    assert re.search(pattern, text, re.I), (
        f"expected the page to report {expected} transactions; saw: {text[:500]}"
    )


def _assert_top_category(text, category):
    if category.isalnum():
        matched = re.search(rf"\b{re.escape(category)}\b", text, re.I)
    else:
        matched = category in text
    assert matched, f"expected {category!r} as the displayed top category"


def _input_values(html, name):
    """Return the value attributes of inputs carrying the given name."""
    name_pattern = r'\bname\s*=\s*["\']' + re.escape(name) + r'["\']'
    value_pattern = r'\bvalue\s*=\s*["\']([^"\']*)["\']'
    values = []
    for tag in re.findall(r"<input\b[^>]*>", html, re.I):
        if re.search(name_pattern, tag, re.I):
            match = re.search(value_pattern, tag, re.I)
            if match:
                values.append(match.group(1))
    return values


def _displayed_percentages(text):
    return [int(value) for value in re.findall(r"\b(\d{1,3})\s*%", text)]


# --------------------------------------------------------------------------- #
# Page-level behaviour                                                          #
# --------------------------------------------------------------------------- #

def test_view_unfiltered_profile_shows_all_eight_seed_expenses_and_lifetime_stats(
    demo_client,
):
    response = demo_client.get("/profile")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "Demo User" in text
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)
    _assert_top_category(text, "Bills")
    for amount in (15.50, 12.00, 80.00, 45.00, 25.00, 60.00, 10.00, 22.00):
        _assert_amount(text, amount)


def test_view_inclusive_range_shows_exactly_three_expenses_and_scoped_stats(
    demo_client,
):
    response = demo_client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert response.status_code == 200
    text = _visible_text(response)
    _assert_amount(text, 150.00)
    _assert_transaction_count(text, 3)
    _assert_top_category(text, "Bills")
    for amount in (80.00, 45.00, 25.00):
        _assert_amount(text, amount)
    for amount in (15.50, 12.00, 60.00, 10.00, 22.00):
        _assert_no_amount(text, amount)
    assert "Showing" in text
    assert "2023-11-03" in text and "2023-11-05" in text


def test_view_inclusive_range_breakdown_percentages_sum_to_one_hundred(
    demo_client, demo_user_id
):
    response = demo_client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert response.status_code == 200
    breakdown = get_category_breakdown(demo_user_id, "2023-11-03", "2023-11-05")
    assert sum(row["pct"] for row in breakdown) == 100
    displayed = _displayed_percentages(_visible_text(response))
    if displayed:
        assert sum(displayed) == 100


def test_view_from_only_bound_shows_only_expenses_on_or_after_start_date(
    demo_client,
):
    response = demo_client.get("/profile?from=2023-11-08")

    assert response.status_code == 200
    text = _visible_text(response)
    _assert_amount(text, 22.00)
    _assert_transaction_count(text, 1)
    _assert_top_category(text, "Food")
    for amount in (15.50, 12.00, 80.00, 45.00, 25.00, 60.00, 10.00):
        _assert_no_amount(text, amount)


def test_view_to_only_bound_shows_only_two_expenses_on_or_before_end_date(
    demo_client,
):
    response = demo_client.get("/profile?to=2023-11-02")

    assert response.status_code == 200
    text = _visible_text(response)
    _assert_amount(text, 27.50)
    _assert_transaction_count(text, 2)
    assert "2023-11-01" in text and "2023-11-02" in text
    for amount in (80.00, 45.00, 25.00, 60.00, 10.00, 22.00):
        _assert_no_amount(text, amount)


def test_view_out_of_range_window_shows_empty_state_and_zero_stats(
    demo_client, demo_user_id
):
    response = demo_client.get("/profile?from=2024-01-01&to=2024-01-31")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "No expenses match this date range." in text
    _assert_amount(text, 0.00)
    _assert_transaction_count(text, 0)
    _assert_top_category(text, "—")
    for category in CATEGORY_NAMES_WITH_EXPENSES:
        assert not re.search(rf"\b{category}\b", text, re.I)
    assert get_category_breakdown(demo_user_id, "2024-01-01", "2024-01-31") == []


def test_view_malformed_from_date_shows_friendly_error_with_unfiltered_stats(
    demo_client,
):
    response = demo_client.get("/profile?from=not-a-date")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "YYYY-MM-DD" in text
    assert "not-a-date" in _input_values(_html(response), "from")
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)
    _assert_top_category(text, "Bills")


def test_view_unpadded_date_shows_friendly_error_and_retains_raw_value(
    demo_client,
):
    response = demo_client.get("/profile?from=2023-2-3")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "YYYY-MM-DD" in text
    assert "2023-2-3" in _input_values(_html(response), "from")
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)


def test_view_reversed_range_shows_start_after_end_error_with_unfiltered_stats(
    demo_client,
):
    response = demo_client.get("/profile?from=2023-11-08&to=2023-11-01")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "Start date must be on or before end date." in text
    assert "2023-11-08" in _input_values(_html(response), "from")
    assert "2023-11-01" in _input_values(_html(response), "to")
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)


def test_view_malformed_to_date_alone_shows_error_and_unfiltered_stats(
    demo_client,
):
    response = demo_client.get("/profile?to=not-a-date")

    assert response.status_code == 200
    text = _visible_text(response)
    assert "YYYY-MM-DD" in text
    assert "not-a-date" in _input_values(_html(response), "to")
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)


def test_view_profile_renders_get_filter_form_with_apply_button_and_clear_link(
    demo_client,
):
    response = demo_client.get("/profile")

    assert response.status_code == 200
    html = _html(response)
    assert re.search(r'<form\b[^>]*\bmethod\s*=\s*["\']get["\']', html, re.I)
    assert re.search(r'<form\b[^>]*\baction\s*=\s*["\']/profile["\']', html, re.I)

    input_tags = re.findall(r"<input\b[^>]*>", html, re.I)
    for name in ("from", "to"):
        name_pattern = r'\bname\s*=\s*["\']' + name + r'["\']'
        assert any(re.search(name_pattern, tag, re.I) for tag in input_tags), (
            f"missing a date input named {name!r}"
        )
    assert len(re.findall(r"<label\b", html, re.I)) >= 2

    text = _visible_text(response)
    assert re.search(r"\bApply\b", text, re.I)
    assert re.search(
        r'<a\b[^>]*\bhref\s*=\s*["\']/profile["\'][^>]*>\s*Clear', html, re.I
    )


def test_follow_clear_link_from_filtered_profile_restores_lifetime_view(
    demo_client,
):
    filtered = demo_client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert filtered.status_code == 200
    clear_link = re.search(
        r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']*)["\'][^>]*>\s*Clear',
        _html(filtered),
        re.I,
    )
    assert clear_link is not None, "a Clear link back to plain /profile is required"

    cleared = demo_client.get(clear_link.group(1))

    assert cleared.status_code == 200
    text = _visible_text(cleared)
    _assert_amount(text, 269.50)
    _assert_transaction_count(text, 8)


def test_request_filtered_profile_while_signed_out_redirects_to_login(client):
    response = client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_view_filtered_profile_hides_other_users_expenses_in_both_directions(
    client, demo_client, tmp_path
):
    db_path = _db_path(tmp_path)
    second_id = _register_and_sign_in_second_user(client, db_path)
    _insert_expense(
        db_path, second_id, 999.00, "Shopping", "2023-11-04", "Second user purchase"
    )

    second_page = client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert second_page.status_code == 200
    second_text = _visible_text(second_page)
    _assert_amount(second_text, 999.00)
    assert "Second user purchase" in second_text
    for amount in (80.00, 45.00, 25.00, 150.00, 269.50):
        _assert_no_amount(second_text, amount)

    demo_row = _fetch_user_row(db_path, DEMO_EMAIL)
    with client.session_transaction() as session:
        session["user_id"] = demo_row[0]
        session["user_name"] = demo_row[1]

    demo_page = client.get("/profile?from=2023-11-03&to=2023-11-05")

    assert demo_page.status_code == 200
    demo_text = _visible_text(demo_page)
    _assert_amount(demo_text, 150.00)
    _assert_no_amount(demo_text, 999.00)
    assert "Second user purchase" not in demo_text


# --------------------------------------------------------------------------- #
# Query-helper behaviour with optional date bounds                             #
# --------------------------------------------------------------------------- #

def test_get_summary_stats_without_bounds_returns_lifetime_totals(demo_user_id):
    stats = get_summary_stats(demo_user_id)

    assert stats["total_spent"] == pytest.approx(269.50)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_with_inclusive_bounds_returns_scoped_totals(
    demo_user_id,
):
    stats = get_summary_stats(demo_user_id, "2023-11-03", "2023-11-05")

    assert stats["total_spent"] == pytest.approx(150.00)
    assert stats["transaction_count"] == 3
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_with_single_bounds_returns_matching_totals(
    demo_user_id,
):
    from_only = get_summary_stats(demo_user_id, date_from="2023-11-08")
    to_only = get_summary_stats(demo_user_id, date_to="2023-11-02")

    assert from_only["transaction_count"] == 1
    assert from_only["total_spent"] == pytest.approx(22.00)
    assert to_only["transaction_count"] == 2
    assert to_only["total_spent"] == pytest.approx(27.50)


def test_get_summary_stats_with_empty_window_returns_zero_and_dash(demo_user_id):
    stats = get_summary_stats(demo_user_id, "2024-01-01", "2024-01-31")

    assert stats["total_spent"] == 0.0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


def test_get_recent_transactions_without_bounds_returns_all_eight_rows(
    demo_user_id,
):
    rows = get_recent_transactions(demo_user_id)

    assert len(rows) == 8
    assert rows[0]["date"] == "2023-11-08"


def test_get_recent_transactions_with_inclusive_bounds_returns_three_scoped_rows(
    demo_user_id,
):
    rows = get_recent_transactions(
        demo_user_id, date_from="2023-11-03", date_to="2023-11-05"
    )

    assert [row["date"] for row in rows] == [
        "2023-11-05",
        "2023-11-04",
        "2023-11-03",
    ]
    assert [row["amount"] for row in rows] == pytest.approx([25.0, 45.0, 80.0])
    assert {row["category"] for row in rows} == {
        "Bills",
        "Health",
        "Entertainment",
    }


def test_get_recent_transactions_with_single_bounds_returns_matching_rows(
    demo_user_id,
):
    from_only = get_recent_transactions(demo_user_id, date_from="2023-11-08")
    to_only = get_recent_transactions(demo_user_id, date_to="2023-11-02")

    assert [row["amount"] for row in from_only] == pytest.approx([22.0])
    assert [row["date"] for row in to_only] == ["2023-11-02", "2023-11-01"]
    assert [row["amount"] for row in to_only] == pytest.approx([12.0, 15.5])


def test_get_recent_transactions_with_bounds_still_honours_limit(
    demo_user_id, tmp_path
):
    db_path = _db_path(tmp_path)
    for day in range(1, 13):
        _insert_expense(
            db_path,
            demo_user_id,
            1.00,
            "Other",
            f"2023-12-{day:02d}",
            f"Extra purchase {day}",
        )

    rows = get_recent_transactions(
        demo_user_id, limit=10, date_from="2023-12-01", date_to="2023-12-31"
    )

    assert len(rows) == 10
    assert rows[0]["date"] == "2023-12-12"


def test_get_recent_transactions_with_empty_window_returns_no_rows(demo_user_id):
    rows = get_recent_transactions(
        demo_user_id, date_from="2024-01-01", date_to="2024-01-31"
    )

    assert rows == []


def test_get_category_breakdown_without_bounds_covers_categories_and_sums_to_100(
    demo_user_id,
):
    rows = get_category_breakdown(demo_user_id)

    assert len(rows) == 7
    assert sum(row["pct"] for row in rows) == 100


def test_get_category_breakdown_with_inclusive_bounds_returns_only_scoped_categories(
    demo_user_id,
):
    rows = get_category_breakdown(demo_user_id, "2023-11-03", "2023-11-05")
    active = {row["name"]: row["amount"] for row in rows if row["amount"] > 0}

    assert active == {"Bills": 80.0, "Health": 45.0, "Entertainment": 25.0}
    assert sum(row["pct"] for row in rows) == 100


def test_get_category_breakdown_with_to_only_bound_uses_matching_categories(
    demo_user_id,
):
    rows = get_category_breakdown(demo_user_id, date_to="2023-11-02")
    active = {row["name"]: row["amount"] for row in rows if row["amount"] > 0}

    assert active == {"Food": 15.5, "Transport": 12.0}
    assert sum(row["pct"] for row in rows) == 100


def test_get_category_breakdown_with_empty_window_returns_no_rows(demo_user_id):
    rows = get_category_breakdown(demo_user_id, "2024-01-01", "2024-01-31")

    assert rows == []


def test_query_helpers_with_bounds_ignore_expenses_of_other_users(
    demo_user_id, client, tmp_path
):
    db_path = _db_path(tmp_path)
    second_id = _register_and_sign_in_second_user(client, db_path)
    _insert_expense(
        db_path, second_id, 999.00, "Shopping", "2023-11-04", "Second user purchase"
    )

    stats = get_summary_stats(demo_user_id, "2023-11-03", "2023-11-05")
    transactions = get_recent_transactions(
        demo_user_id, date_from="2023-11-03", date_to="2023-11-05"
    )
    breakdown = get_category_breakdown(demo_user_id, "2023-11-03", "2023-11-05")

    assert stats["total_spent"] == pytest.approx(150.00)
    assert len(transactions) == 3
    assert sum(row["amount"] for row in breakdown) == pytest.approx(150.00)
    assert all(row["amount"] != pytest.approx(999.00) for row in transactions)
