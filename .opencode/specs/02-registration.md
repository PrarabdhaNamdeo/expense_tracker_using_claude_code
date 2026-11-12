# Spec: Registration

## Overview

Implement working user registration for Spendly. The `/register` page already
exists as a front-end-only form that renders `templates/register.html` but
discards its submission — `app.py` only defines a `GET` handler. This step
turns that page into a real sign-up flow: the submitted name, email, and
password are validated, the password is hashed, and a new row is inserted into
the existing `users` table. Registration is the entry point for every
authenticated feature that follows (login, logout, profile, and per-user
expenses), so it must be correct and safe from the start.

## Depends on

- **Step 01 — Database setup** (`.claude/specs/01-database-setup.md`).
  Requires the `users` table, `get_db()`, and `init_db()` / `seed_db()` to
  already exist in `database/db.py`, and `app.py` to initialise the database
  on startup. Both are complete.

## Routes

- `POST /register` — accepts `name`, `email`, `password` as form data,
  creates the user, then redirects — **public**
- `GET /register` — existing route; now also renders validation errors and
  previously entered values — **public**

`/register` must reject non-POST access to the submit logic (i.e. GET keeps
rendering the empty form). No other routes change.

## Database changes

**No database changes.** The existing schema already supports registration:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
)
```

`email` is already `UNIQUE NOT NULL`, which enforces one account per address
and lets the application detect duplicates. No new tables, columns, indexes,
or constraints are required.

## Templates

- **Create:** none
- **Modify:**
  - `templates/register.html`
    - Keep the existing `error` block; ensure errors render above the form.
    - Re-populate the `name` and `email` inputs with the submitted values
      when re-rendering after a validation failure
      (e.g. `value="{{ name or '' }}"`), never the password.
    - Add a success banner block (e.g. `{% if success %}`) if success is
      communicated via the template instead of a redirect flash.
    - Add `minlength="8"` to the password input to match server-side rules.
  - `templates/login.html`
    - Add a success message block (e.g. `{% if success %}<div class="auth-success">…</div>{% endif %}`)
      shown after a successful registration redirects to `/login`.
    - Existing error block stays unchanged.

## Files to change

- `app.py` — add `POST` handling to `/register`, request parsing, validation,
  hashing, insert, error handling, and redirect.
- `database/db.py` — add a `create_user(name, email, password_hash)` helper
  using `get_db()` and a parameterised `INSERT`. Return the new user's id or
  raise/return on duplicate email.
- `templates/register.html` — error display, value retention, password
  `minlength`.
- `templates/login.html` — success message after registration.
- `static/css/style.css` — add an `.auth-success` rule using existing CSS
  variables (`var(--accent)`, `var(--accent-light)`), mirroring `.auth-error`.

## Files to create

- None. All necessary templates and modules already exist.

## New dependencies

**No new dependencies.** Use only what is already installed:

- `flask` (`request`, `redirect`, `url_for`, `render_template`, `flash`)
- `werkzeug.security` (`generate_password_hash`, `check_password_hash` if
  needed later)
- `sqlite3` (standard library)

## Implementation details

### `app.py`

1. Import `request`, `redirect`, `url_for`, `flash` from `flask`, plus
   `sqlite3`. Import `create_user` from `database.db`.
2. Set `app.secret_key` (read from `os.environ.get("SECRET_KEY")` with a
   clearly-marked development fallback) so `flash()` works. Never commit a
   production secret.
3. Extend the route:

```python
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        # validate → on failure re-render with error + values
        # hash and insert → on success flash + redirect to login
    return render_template("register.html")
```

### Validation rules (server-side, in this order)

1. `name`, `email`, `password` must all be non-empty.
2. `name` must be between 1 and 100 characters.
3. `email` must contain exactly one `@` with non-empty local part and a
   domain containing a `.` (keep it simple; the browser also validates type
   `email`).
4. `password` must be at least 8 characters.
5. Email must not already exist in `users` (case-insensitive, since it is
   stored lowercased).
6. On any failure: re-render `register.html` with a friendly `error` message
   and the submitted `name` / `email`, HTTP 200.

Do not reveal whether a specific email exists beyond the necessary
"An account with this email already exists." message.

### Success path

- `generate_password_hash(password)` — never store plaintext.
- Insert with a parameterised query:
  `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)`
- Catch `sqlite3.IntegrityError` (race to duplicate email) and re-render with
  the duplicate-email error.
- `flash("Account created successfully. Please sign in.", "success")` and
  `redirect(url_for("login"))`.

### `database/db.py`

```python
def create_user(name, email, password_hash):
    """Inserts a new user and returns the new row id. Raises sqlite3.IntegrityError on duplicate email."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
```

Reuse `get_db()` so `row_factory` and `PRAGMA foreign_keys = ON` apply.

## Rules for implementation

- No SQLAlchemy or ORMs.
- Parameterised queries only — never string-format user input into SQL.
- Passwords hashed with `werkzeug.security.generate_password_hash`; never log
  or echo the plaintext password.
- Use CSS variables — never hardcode hex values in templates or new CSS.
- All templates extend `base.html`.
- Keep changes minimal and consistent with existing naming and structure in
  `app.py`, `database/db.py`, and `static/css/style.css`.
- No new pip packages.
- Registration must not log the user in — that belongs to Step 03 (login).
- Do not modify `spendly.db` by hand; let the app create rows at runtime.

## Definition of done

- [ ] `python app.py` starts without errors and `http://localhost:5001/register` renders the form.
- [ ] Submitting a valid new name/email/password creates a row in `users`
      with a hashed `password_hash` (not the plaintext password).
- [ ] After successful registration the browser lands on `/login` and shows a
      success message.
- [ ] The newly registered email can be found in `spendly.db` and its
      `password_hash` starts with a werkzeug hash prefix (e.g. `scrypt:`/`pbkdf2:`).
- [ ] Submitting an email that already exists (e.g. `demo@spendly.com`) shows
      "An account with this email already exists." and creates no new row.
- [ ] Submitting a password shorter than 8 characters shows a validation error
      and creates no new row.
- [ ] Submitting with an empty name or email shows a validation error and
      creates no new row.
- [ ] After a validation error, the name and email fields retain what the user
      typed and the password field is blank.
- [ ] Emails are stored lowercased, so `Demo@Spendly.com` collides with
      `demo@spendly.com`.
- [ ] The GET `/register` page still loads normally with no errors.
- [ ] No plaintext password appears anywhere in the database or response HTML.
