# Wealthwise — Budget Tracker

A desktop budgeting application built in Python that helps you manage your
monthly salary using the 50/30/20 method with customisable percentages.
Plan your budget, log daily spending, track it against your plan, and see
each month's savings — all stored locally, with a light/dark themed interface.

## Features

- Split your salary across Needs / Wants / Savings with your own percentages
- Organise spending into categories and sub-categories
- Set a monthly plan (fixed expenses) and log actual daily spending against it
- Warnings when you overspend a budget or your plan
- Custom salary-cycle start date (for salaries paid mid-month)
- Monthly history and month-to-month comparison, with per-month savings
- Reports with charts (spending split, by category, allocated vs spent)
- Light / dark mode
- Local SQLite storage — your data persists between sessions

## Tech stack

- Python
- CustomTkinter (modern UI)
- SQLite (local database, via Python's built-in sqlite3)
- matplotlib (charts)

## Running it

1. Install the dependencies:

pip install -r requirements.txt

2. Run the app:

python main.py


The app creates its own database on first launch — no setup needed.

## Project structure

- main.py — entry point and main window
- app/core/ — theme, database layer
- app/services/ — the data holders (settings, categories, expenses) and reports
- app/ui/ — the screens (dashboard, settings, categories, expenses, reports)
- app/widgets/ — shared widgets