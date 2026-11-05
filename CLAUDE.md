# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run application: `python app.py`
- Install dependencies: `pip install -r requirements.txt`
- Run tests: `pytest`
- Run a specific test: `pytest <path_to_test_file>`

## Architecture
The project is a Flask-based Expense Tracker application following a simple layout:
- `app.py`: Main entry point containing route definitions and application configuration.
- `database/`: Database layer. `db.py` is intended to handle SQLite connections, initialization, and seeding.
- `static/`: Static assets including CSS (`static/css/style.css`) and JavaScript (`static/js/main.js`).
- `templates/`: Jinja2 HTML templates for the frontend.

The application is currently in early development, with several placeholder routes for core functionality (logout, profile, and expense CRUD operations) that are planned for future implementation steps.
