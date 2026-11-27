# Spec: Date Filter for Profile Page

## Overview
Step 06 adds an optional date-range filter to the existing `/profile` page so a signed-in user can narrow their spending overview to a chosen period. The profile currently shows lifetime totals, all recent transactions, and an all-time category breakdown; once real expense history grows, those numbers are hard to act on. A simple `from` / `to` filter — applied consistently to the summary stats, transaction list, and category breakdown — lets users answer "what did I spend last week?" without leaving the page, while keeping the unfiltered view as the default so existing behaviour and shareable URLs remain stable.

## Depends on
- **Step 01 — Database setup**: `database/db.py` already provides `get_db()`, the `expenses` table, and `date TEXT NOT NULL` stored as `YYYY-MM-DD`, which is directly comparable for range queries.
- **Step 02 — Registration**: user accounts exist in `users`.
- **Step 03 — Login / Logout**: `session["user_id"]` identifies the signed-in user; `/profile` is already protected.
- **Step 04 — Profile page design**: `templates/profile.html` renders the four profile sections and extends `base.html`.
- **Step 05 — Backend connection**: `database/queries.py` supplies `get_summary_stats`, `get_recent_transactions`, and `get_category_breakdown`, and `app.py` passes their results into the template. This step extends those helpers rather than replacing them.

## Routes
No new routes. The existing `GET /profile` route is modified to accept two optional query parameters and remains **logged-in only**:

- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — render the profile using only expenses whose `date` falls within the inclusive range; either bound may be omitted — logged-in
- `GET /profile` — unchanged lifetime view when no valid bounds are supplied — logged-in

The auth guard must run before any filter parsing. An unauthenticated request with filter parameters still redirects to `/login`.

## Database changes
**No database changes.** Verified against `database/db.py`: `expenses` already has `user_id INTEGER NOT NULL`, `amount REAL NOT NULL`, `category TEXT NOT NULL`, and `date TEXT NOT NULL`, with `created_at TEXT DEFAULT (datetime('now'))` and a foreign key to `users(id)`. Dates are seeded and documented as `YYYY-MM-DD`, so lexical `>=` / `<=` comparisons give correct chronological ranges. No new tables, columns, indexes, or constraints are needed.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html`
  - Add a `GET` filter form above the profile workspace (or above the ledger section) that posts back to `url_for('profile')` with two labelled date inputs named `from` and `to`, an **Apply** submit button, and a **Clear** link back to plain `/profile`.
  - Re-populate the inputs with the raw submitted values from `filter_from` / `filter_to`; never echo a password or any other session data.
  - Render `filter_errors` (if any) as an accessible inline message near the form.
  - When a valid range is active, show a short note such as `Showing 2023-11-03 to 2023-11-05` and keep it visible in the heading area so the displayed numbers are clearly scoped.
  - Add an empty-state message (e.g. `No expenses match this date range.`) inside the transactions table area and the category list when the filtered result is empty; keep the table markup valid.
  - Continue to extend `base.html`, use the ₹ symbol for every amount, and use existing profile class naming conventions.

- **Modify:** `static/css/style.css`
  - Add styles for the filter form, labels, inputs, buttons, error message, active-range note, and empty state.
  - Use only existing CSS variables such as `var(--border)`, `var(--paper-card)`, `var(--ink-muted)`, `var(--accent)`, `var(--accent-light)`, and `var(--radius-sm)`. No hardcoded hex values and no inline styles.

## Files to change
- `app.py` — add a small `parse_date_filter()` helper using `datetime.strptime` with `%Y-%m-%d`; read `request.args.get("from")` / `request.args.get("to")`; pass parsed bounds and raw values/errors into `render_template`; forward bounds to the three query helpers.
- `database/queries.py` — extend `get_summary_stats(user_id, date_from=None, date_to=None)`, `get_recent_transactions(user_id, limit=10, date_from=None, date_to=None)`, and `get_category_breakdown(user_id, date_from=None, date_to=None)`. All existing calls without date arguments must keep their current behaviour.
- `templates/profile.html` — add the filter form, error/active-range messaging, and empty states described above.
- `static/css/style.css` — add the corresponding variable-based styles.

## Files to create
- `tests/test_profile_date_filter.py` — cover: default unfiltered profile still shows the 8 seed expenses and ₹269.50; an inclusive range `from=2023-11-03&to=2023-11-05` shows 3 transactions totalling ₹150.00 with Bills as top category; one-sided `from` and `to` bounds; an out-of-range window returns 0 transactions, ₹0.00, top category `—`, and an empty breakdown; malformed dates and `from > to` produce a friendly error with no 500; a filtered request while signed out redirects to `/login`; filter values never leak another user's expenses. Reuse the temporary-DB fixture pattern from `tests/test_backend_connection.py`.

## New dependencies
No new dependencies. Use only `datetime` from the Python standard library plus the already-installed Flask, sqlite3, and Werkzeug packages listed in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only through `get_db()`.
- Parameterised queries only — build optional `WHERE` fragments from fixed literal strings and pass every `user_id`, `date_from`, and `date_to` value as a bound `?` parameter. Never f-string or concatenate request data into SQL.
- Passwords hashed with werkzeug — do not alter registration/login hashing or echo passwords; password handling is out of scope for this step.
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html` — including any new template (none are expected here).
- Keep `session["user_id"]` as the only source of user identity; query arguments must never select another user's rows.
- Accept dates only as real calendar dates in exactly `YYYY-MM-DD` form (use a `strptime` round-trip so `2023-2-3` is rejected).
- Bounds are inclusive: a transaction on `from` or `to` is included. One valid bound alone is allowed; an invalid non-empty bound is ignored and reported, not applied.
- If both bounds are valid but `from > to`, report `Start date must be on or before end date.` and ignore both bounds for that request.
- The no-filter path must be byte-for-byte equivalent in behaviour to Step 05: all 8 seed rows, ₹269.50 total, 8 transactions, and Bills as top category.
- Apply the same bounds to summary stats, the transaction list, and category breakdown so the three sections never disagree.
- Keep the existing `limit=10` behaviour for recent transactions after filtering; keep category percentages as integers summing to 100, with the largest category absorbing the rounding remainder as in Step 05.
- Do not modify `spendly.db` by hand and do not add inline `<style>` attributes.

## Definition of done
- [ ] `python app.py` starts cleanly and a signed-in visit to `/profile` still shows "Demo User", ₹269.50, 8 transactions, and Bills as the top category.
- [ ] Visiting `/profile?from=2023-11-03&to=2023-11-05` shows exactly 3 transactions (Bills ₹80.00, Health ₹45.00, Entertainment ₹25.00) and a total of ₹150.00.
- [ ] The same filtered page shows transaction count 3, top category Bills, and a category breakdown whose percentages still add up to 100 %.
- [ ] Visiting `/profile?from=2023-11-08` shows only the 22.00 Food entry; visiting `/profile?to=2023-11-02` shows only the two entries dated 2023-11-01 and 2023-11-02 (₹27.50 total).
- [ ] Visiting `/profile?from=2024-01-01&to=2024-01-31` shows "No expenses match this date range.", ₹0.00, 0 transactions, top category `—`, and no breakdown rows — with no server error.
- [ ] Visiting `/profile?from=not-a-date` renders HTTP 200 with a readable date-format error and the unfiltered lifetime numbers.
- [ ] Visiting `/profile?from=2023-11-08&to=2023-11-01` renders HTTP 200 with the start/end error and the unfiltered lifetime numbers.
- [ ] The date inputs retain the submitted values after Apply or an error, and the **Clear** link returns to the plain lifetime `/profile` view.
- [ ] Visiting `/profile?from=2023-11-03` while signed out redirects to `/login` rather than rendering filtered data.
- [ ] Registering a second user, signing in, and applying any date range shows none of the demo user's expenses.
- [ ] Every amount on the filtered page still uses the ₹ symbol, and `profile.html` plus the new CSS rules contain no hardcoded hex colours.
- [ ] `pytest` passes, including the new `tests/test_profile_date_filter.py` and the existing `tests/test_backend_connection.py`.
