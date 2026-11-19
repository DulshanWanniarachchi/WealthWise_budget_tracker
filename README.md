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

## A peek at the application

<img width="975" height="672" alt="image" src="https://github.com/user-attachments/assets/e5266bff-efc1-4ed9-8740-cfa296583308" />
<img width="975" height="675" alt="image" src="https://github.com/user-attachments/assets/034b972c-0a0a-4e53-939d-c63792632e5c" />
<img width="975" height="674" alt="image" src="https://github.com/user-attachments/assets/75473a1e-238e-4f51-9a95-e0f7a8c79353" />
<img width="975" height="672" alt="image" src="https://github.com/user-attachments/assets/552734f7-4549-44c4-bc52-4822206f7212" />
<img width="975" height="669" alt="image" src="https://github.com/user-attachments/assets/b9324dbf-6b49-4e18-aa24-00b230a239ac" />
<img width="975" height="667" alt="image" src="https://github.com/user-attachments/assets/4b6d25fb-44b4-4c25-b036-941b1e5404ed" />
<img width="975" height="671" alt="image" src="https://github.com/user-attachments/assets/9fe14960-6139-412c-9aaa-bb334e6f4aa9" />
<img width="975" height="667" alt="image" src="https://github.com/user-attachments/assets/10de8172-57a8-4eb6-8b71-ede0ad1d50e6" />
<img width="975" height="669" alt="image" src="https://github.com/user-attachments/assets/c792e60e-4489-4d07-b167-70b0a515a7de" />

