# Spec: Login and Logout

## Overview

Implement working sign-in and sign-out for Spendly. The `/login` page already
exists as a front-end-only form that renders `templates/login.html`, and
`/logout` is a placeholder string in `app.py`. This step turns both into a real
session flow: submitted credentials are checked against the `users` table with
`werkzeug`'s `check_password_hash`, a successful sign-in stores the user in
Flask's signed session cookie, and signing out clears that session. Login is
the gate for every authenticated feature that follows (profile in Step 04,
expenses in Steps 05-09), so it must never reveal which emails exist, never
store or echo plaintext passwords, and must leave the visitor logged out on
every failure path.

## Depends on

- **Step 01 — Database setup** (`.claude/specs/01-database-setup.md`).
  Requires the `users` table, `get_db()`, the seeded demo user
  (`demo@spendly.com` / `demo123`), and startup initialisation in `app.py`.
  All are present on `main`.
- **Step 02 — Registration**. Login only needs the `users` table, which already
  exists, so the flow can be built on `main`. However, the registration work
  currently lives on the unmerged `feature/registration-01` branch and adds
  two things this step also touches:
  - `app.secret_key` (required for sessions and flash messages)
  - the flashed-message block in `templates/login.html`
  - `create_user()` in `database/db.py`

  If Step 02 is merged before implementation, reuse its `app.secret_key` and
  flash block instead of duplicating them. If it is not merged, this step
  must add `app.secret_key` itself; it must not add `create_user()`.

## Routes

- `GET /login` — render the sign-in form (now also shows flashed messages and
  the previously entered email after a failed attempt) — **public (guests only)**
- `POST /login` — accepts `email` and `password` as form data, verifies the
  credentials, writes the user to the session, and redirects — **public
  (guests only)**
- `GET /logout` — clears the session and redirects to `/login` — **logged-in**
  (also safe and harmless when visited while logged out)

`/login` and `/register` are guest-only: when a session already has a
`user_id`, both reject `GET` and `POST` with a redirect to `/` instead of
rendering the form. This applies retroactively to the registration route too,
so a signed-in user can no longer reach either auth page.

Existing routes (`/`, `/register`, `/terms`, `/privacy`) and the remaining
placeholders (`/profile`, `/expenses/*`) are unchanged by this step.

## Database changes

**No database changes.** The existing schema already supports login:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
)
```

`email` is `UNIQUE NOT NULL` and `password_hash` is already populated by
`seed_db()` and (once merged) registration. No new tables, columns, indexes,
or constraints are required.

## Templates

- **Create:** none.
- **Modify:**
  - `templates/login.html`
    - Render flashed messages (`get_flashed_messages(with_categories=true)`)
      above the form, using `auth-{{ category }}` classes so registration's
      success message and this step's sign-out message display correctly.
      Skip this block if Step 02 already added it.
    - Keep the existing `{% if error %}` block and show its message above the
      form.
    - Re-populate the email input with `value="{{ email or '' }}"` after a
      failed attempt; always leave the password input blank.
    - Optionally add `minlength="8"` to the password input (server remains the
      source of truth). Do not add client-side validation that blocks a
      legitimate demo login.
  - `templates/base.html`
    - Make the nav session-aware: when `session.get('user_id')` is set, show
      the user's name and a "Sign out" link to `url_for('logout')`; otherwise
      keep the existing "Sign in" and "Get started" links.
    - Use the same markup/CSS classes already present (`.nav-links`, `.nav-cta`),
      no new layout.
  - `static/css/style.css`
    - Reuse the existing `.auth-error` rule for failures.
    - If `.auth-success` does not yet exist (it is added by Step 02), add it
      using CSS variables only (`var(--accent)`, `var(--accent-light)`,
      `var(--radius-sm)`), mirroring `.auth-error`.
    - If a nav user-name label needs styling, add one small rule built on
      existing variables; no hardcoded colours.

## Files to change

- `app.py` — add `POST` handling to `/login`, session write, real `/logout`,
  and `app.secret_key` if it is not already defined. Import `request`,
  `session`, `redirect`, `url_for`, `flash`, plus `check_password_hash` and
  `get_db` (and `sqlite3` only if it is genuinely needed).
- `templates/login.html` — flash rendering, error display, email retention.
- `templates/base.html` — session-aware navigation with a sign-out link.
- `static/css/style.css` — only if `.auth-success` or a nav user-name style is
  still missing.

## Files to create

- None. All required templates and modules already exist.

## New dependencies

**No new dependencies.** Use only what is already installed:

- `flask` (`request`, `session`, `redirect`, `url_for`, `flash`,
  `render_template`)
- `werkzeug.security` (`check_password_hash`; `generate_password_hash` is
  already used by the seed data)
- `sqlite3` (standard library)

Do not add Flask-Login, Flask-WTF, or any other extension in this step.

## Rules for implementation

- No SQLAlchemy or ORMs.
- Parameterised queries only — never string-format user input into SQL.
- Passwords hashed with `werkzeug`; use `check_password_hash()` for
  verification. Never store, log, or echo the plaintext password.
- Use CSS variables — never hardcode hex values in templates or new CSS.
- All templates extend `base.html`.
- Keep changes minimal and consistent with existing naming and structure in
  `app.py`, `database/db.py`, and `static/css/style.css`.
- Do not modify `spendly.db` by hand; use the existing demo user or register a
  user through the app.

### Login route behaviour

1. If the session already has a `user_id`, redirect to `/` for both `GET` and
   `POST` (guest-only route) instead of rendering the form or processing
   credentials.
2. `GET` renders `login.html` (passing no `error`).
3. `POST` reads `email` and `password` from `request.form`, stripping the
   email and lowercasing it; the password is used as submitted.
4. If either field is empty, re-render with `error = "Email and password are required."`,
   HTTP 200, and the submitted email preserved.
5. Look the user up with a parameterised query:
   `SELECT id, name, password_hash FROM users WHERE email = ?` using
   `get_db()` (not a raw `sqlite3.connect`), so `row_factory` applies.
6. If the user does not exist **or** `check_password_hash()` fails, re-render
   with the same generic message, `"Invalid email or password."`, HTTP 200.
   Do not distinguish "unknown email" from "wrong password" anywhere in the
   response, status code, or timing-sensitive branching.
7. On success, call `session.clear()` first (prevents session fixation), then
   store `session["user_id"] = user["id"]` and `session["user_name"] = user["name"]`.
8. Redirect to `url_for("landing")` for now. Step 04 will change the
   destination to the profile page once it exists.
9. Never accept a `next`/`redirect` query parameter — no open redirects.

### Logout route behaviour

1. `session.clear()`.
2. `flash("You've been signed out.", "success")`.
3. `redirect(url_for("login"))`.
4. Visiting `/logout` while already logged out must not error; it simply
   redirects to `/login`.

### Session and security notes

- `app.secret_key` is required before `session` or `flash` is used. Read it
  from `os.environ.get("SECRET_KEY")` with a clearly marked development
  fallback, exactly as planned in Step 02. Never commit a production secret.
- Do not introduce a `login_required` decorator or protect `/profile` here;
  that belongs to Step 04. This step only establishes the session contract
  (`user_id`, `user_name`).
- Keep the existing `if __name__ == "__main__"` block and port `5001`.
- If Step 02 is already merged, do not re-add `app.secret_key` or duplicate
  the flash block; adapt to what is on the branch.

## Definition of done

- [ ] `python app.py` starts without errors and `http://localhost:5001/login` renders the form.
- [ ] Signing in as `demo@spendly.com` / `demo123` succeeds and redirects to `/`.
- [ ] After a successful sign-in the navbar shows the user's name and a
      "Sign out" link instead of "Sign in" / "Get started".
- [ ] The session survives a page refresh and navigation to other pages.
- [ ] Signing in with the correct email and a wrong password shows
      "Invalid email or password." and does not create a session.
- [ ] Signing in with an unknown email shows the exact same generic error and
      no hint that the account does not exist.
- [ ] Signing in with an email in different case (`DEMO@SPENDLY.COM`) still
      works because emails are compared lowercased.
- [ ] Submitting an empty email or password shows a validation error and does
      not create a session.
- [ ] After a failed attempt the email field still contains what was typed and
      the password field is blank.
- [ ] The plaintext password never appears in the HTML response or in logs.
- [ ] Visiting `/logout` clears the session, redirects to `/login`, and shows
      "You've been signed out."; the navbar returns to "Sign in" /
      "Get started".
- [ ] Visiting `/logout` while already signed out still redirects to `/login`
      with no error.
- [ ] `/login` and `/logout` behave correctly even if the user opens them in a
      fresh browser session (no stale session data required).
- [ ] While signed in, visiting `/login` or `/register` (by URL or form POST)
      redirects to `/` instead of showing the auth form.
- [ ] After signing out, `/login` and `/register` are reachable again.
- [ ] Existing pages (`/`, `/register`, `/terms`, `/privacy`) still render.
- [ ] No new pip packages, no database schema changes, and no plaintext
      passwords stored anywhere.
