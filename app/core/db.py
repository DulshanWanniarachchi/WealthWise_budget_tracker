"""
db.py - the ONE place that owns the SQLite database: the file, the
connection, the schema and the query helpers.

WHY THIS FILE GREW (Phase 7)
  Phases 1-6 deliberately kept all four holders in Python lists and
  dicts, on the promise that storage could be swapped later without
  touching a screen. Phase 7 IS that swap. Everything that used to live
  in memory now lives in data/budget.db, and this module is the only
  thing that knows how to reach it: the holders call db.query() /
  db.execute() and nothing else. One schema, one set of error rules, and
  one place to look when a figure on screen looks wrong.

TWO CONNECTIONS, AND WHY THAT IS CORRECT
  * The SHARED connection (_conn()) is opened lazily and lives for the
    whole process. Every holder query goes through it - that is what
    "all four holders go through this one layer, not four separate
    connections" means in practice: no holder ever calls
    sqlite3.connect() itself.
  * get_connection() still hands out a FRESH connection that the caller
    owns and must close. main.py's startup probe has done exactly that
    since Phase 1 (open, run sqlite_version(), close) and main.py may
    not be edited, so that contract had to survive this phase unchanged.
    The probe's connection opens and closes once at startup; every real
    query uses the shared one.

ERROR RULES - the app must never crash because SQL failed
  * WRITE failures raise ValueError, because every screen already
    catches ValueError from its holders and shows a friendly inline
    message. A failed save therefore reads as an ordinary refusal
    instead of a traceback.
  * READ failures return an empty result ([]) or None. Screens do not
    wrap their reads in try/except - the Dashboard repaints from
    get_spent_by_budget() on every notify - so raising there would take
    the whole window down. Degrading to "no rows" keeps the UI painting.
    That is a deliberate trade-off, stated here because silently showing
    zeros is its cost.

TEST HOOK - the BUDGET_TRACKER_DB environment variable
  The app itself always uses data/budget.db. A regression suite must
  never touch that file: it would seed over the user's structure, and
  the holders' _reset() helpers would DELETE the user's money. So a
  suite points this module at a throwaway database by setting the
  variable BEFORE importing anything from app.*:

      os.environ["BUDGET_TRACKER_DB"] = "fresh"   # usual choice
      os.environ["BUDGET_TRACKER_DB"] = r"C:\\tmp\\one.db"  # a fixed file

  "fresh" resolves to a brand-new file for THIS process only, which
  gives every suite exactly the isolation the in-memory holders gave it
  for free: two suites running back to back cannot see each other's
  rows. run_all.ps1 sets it too, as a second line of defence.
"""

import atexit
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# This file lives at budget_tracker/app/core/db.py, so:
#   parents[0] = app/core   parents[1] = app   parents[2] = budget_tracker
# The database file itself goes in budget_tracker/data/budget.db
def _resolve_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Wealthwise"
    else:
        base = Path(__file__).resolve().parents[2] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base

DATA_DIR = _resolve_data_dir()

# ---------------------------------------------------------------------------
# WHICH FILE? - resolved once, at import time, before anything queries it.
# ---------------------------------------------------------------------------

_override = os.environ.get("BUDGET_TRACKER_DB", "")
_IS_THROWAWAY = _override == "fresh"

if _IS_THROWAWAY:
    # mkstemp creates the (empty) file and returns a unique name, so no
    # two test processes can ever collide.
    _fd, _name = tempfile.mkstemp(prefix="budget_tracker_test_", suffix=".db")
    os.close(_fd)
    DB_PATH = Path(_name)
elif _override:
    DB_PATH = Path(_override)          # a specific file a caller named
else:
    DB_PATH = DATA_DIR / "budget.db"   # the real thing

# The shared connection, opened on first use. None means "not open yet".
_connection: sqlite3.Connection | None = None


if _IS_THROWAWAY:
    # Tidy up behind ourselves: close first (Windows will not delete an
    # open file), then unlink. A suite that dies mid-run leaves its file
    # behind in TEMP - harmless, and the OS clears that folder anyway.
    def _discard_throwaway() -> None:
        global _connection
        try:
            if _connection is not None:
                _connection.close()
        except Exception:               # a broken handle must not mask the unlink
            pass
        _connection = None
        try:
            os.unlink(DB_PATH)
        except OSError:                 # already gone is fine
            pass

    atexit.register(_discard_throwaway)


# ---------------------------------------------------------------------------
# THE SCHEMA
#   Every statement is CREATE ... IF NOT EXISTS, so the same code path
#   serves a brand-new database and one that already has years of data -
#   which is exactly what "run schema creation safely on startup" means.
#   Seeding is NOT done here: db.py imports nothing from app.services
#   (that would be a cycle), so the holder that owns each default writes
#   its own rows the first time it loads. See _seed_if_new in
#   category_settings.py and _ensure_row in budget_settings.py.
# ---------------------------------------------------------------------------

_SCHEMA = """
-- meta: a tiny key/value table that remembers one-time decisions, above
-- all "have the default categories already been seeded?". Without it a
-- user who deleted every category would get the defaults back on the
-- next launch. Once seeded, empty must stay empty.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- budget_settings: exactly ONE row (id = 1) holding the salary, the
-- three percentages, and (Phase 8.1) the day the salary month starts
-- on. CHECK (id = 1) makes "never more than one row" a database rule
-- rather than a convention the code has to remember.
--
--   month_start_day  1-28, the day each salary cycle begins. DEFAULT 1
--                    = plain calendar months, so a database created
--                    before this column existed behaves exactly as it
--                    did before (the migration below backfills 1).
CREATE TABLE IF NOT EXISTS budget_settings (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    salary  INTEGER NOT NULL,
    needs   INTEGER NOT NULL,
    wants   INTEGER NOT NULL,
    savings INTEGER NOT NULL,
    month_start_day INTEGER NOT NULL DEFAULT 1
);

-- cycle_salary: ONE ROW PER SALARY CYCLE, remembering the salary that
-- was in effect WHILE that cycle ran (Phase 8.3 fix).
--
-- WHY A SECOND TABLE AND NOT A COLUMN ON budget_settings
--   budget_settings is deliberately ONE row (CHECK (id = 1)): it holds
--   the settings as they are NOW. History needs the settings as they
--   WERE - one figure per cycle - which a single row cannot hold, so
--   this is a small second table keyed by the cycle key the existing
--   cycle helpers hand out ("YYYY-MM", see budget_settings.cycle_of()).
--   Reading it is also strictly additive: nothing about the single
--   settings row, get_salary() or set_salary() changes.
--
-- MIGRATION: none beyond the IF NOT EXISTS below. Unlike a new COLUMN
--   on an existing table (which is why _migrate_budget_settings()
--   exists), a brand-new TABLE is created by this very statement for
--   both a fresh database and one written by Phase 7/8.2 - existing
--   files simply gain an empty table on next launch, and rows appear
--   as the user lives through cycles with the feature installed.
--
--   cycle_key  "YYYY-MM", exactly what budget_settings.cycle_of()
--              returns, i.e. the same key history records group by.
--   salary     rupees, the salary in effect for that cycle. Written by
--              budget_settings only (auto-record on set/read - see
--              _record_cycle_salary there); never written by screens.
CREATE TABLE IF NOT EXISTS cycle_salary (
    cycle_key TEXT PRIMARY KEY,
    salary    INTEGER NOT NULL
);

-- categories: ONE table for BOTH levels of the tree, so a sub-item is
-- simply a category whose parent_id points at another row. That mirrors
-- the in-memory design exactly - every node had "items", nothing was
-- special-cased - and would accept a third level later with no schema
-- change.
--
--   id         real auto-increment identity. This is the upgrade from
--              "the name is the row" that Phase 7 asked for.
--   budget     needs / wants / savings, written on EVERY row (a child
--              repeats its parent's budget). Denormalised on purpose:
--              (budget, name) is how the rest of the app addresses a
--              category, so one indexed lookup answers it without
--              walking up to the root.
--   parent_id  NULL for a top-level category, otherwise the id of the
--              category it sits under. ON DELETE CASCADE keeps "delete a
--              category and everything nested under it" true at the
--              database level (needs PRAGMA foreign_keys = ON, which
--              _conn() sets - SQLite ships with foreign keys OFF).
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    budget    TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    name      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_budget ON categories(budget, parent_id);

-- fixed_expenses: the monthly PLAN. One row per plan.
--
-- WHY category / sub_item ARE NAMES AND NOT FOREIGN KEYS
--   Phase 7 offered the choice, and the requirement settled it: a
--   RENAMED category must still break the link (reconcile() then marks
--   the expense "Uncategorised"). An id-based foreign key would do the
--   opposite - the id survives a rename, so the link would silently
--   follow the category to its new name. Keeping the name is what makes
--   rename behave like delete, which is the behaviour every existing
--   test and every screen chip depends on. A NULL in these columns is a
--   broken link; it is never a deleted row, so money can never vanish.
CREATE TABLE IF NOT EXISTS fixed_expenses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    amount   INTEGER NOT NULL,
    budget   TEXT NOT NULL,
    category TEXT,
    sub_item TEXT
);

-- "name is identity" across the WHOLE table, case-insensitively: the
-- database-level twin of fixed_expenses._require_free_name(). The
-- holder validates first (so the user gets its friendly message), and
-- this index is the defence-in-depth behind it.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fixed_name
    ON fixed_expenses(name COLLATE NOCASE);

-- daily_expenses: ACTUAL money spent. Same two link columns as above,
-- for the same reason.
--   date  "YYYY-MM-DD" text, so it sorts lexicographically and comes
--         back exactly as the screen wrote it.
--   note  NULL when the user typed nothing.
CREATE TABLE IF NOT EXISTS daily_expenses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    amount   INTEGER NOT NULL,
    budget   TEXT NOT NULL,
    category TEXT,
    sub_item TEXT,
    date     TEXT NOT NULL,
    note     TEXT
);
"""


def _conn() -> sqlite3.Connection:
    """Return the shared connection, opening it (and the schema) once."""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DB_PATH)
        # Row access by column name: db.query() turns these into plain
        # dicts, which is what every holder already expects to receive.
        _connection.row_factory = sqlite3.Row
        # OFF by default in SQLite; ON is what makes the categories
        # ON DELETE CASCADE clause above actually fire.
        _connection.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(_connection)
    return _connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    """Create every table if it does not exist yet.

    Runs once, on first use. An existing database is untouched (every
    statement is IF NOT EXISTS) and a fresh one comes up complete, so
    "existing or fresh both work" holds without a migration step.

    The one exception is _migrate_budget_settings() below: CREATE TABLE
    IF NOT EXISTS cannot ADD a column to a table that already exists, so
    a settings table created before Phase 8.1 needs that one ALTER before
    its row can carry the month start day.

    A failure here is swallowed rather than raised: if the file cannot
    be written the app still has to start, and the read rules at the top
    of this file mean the screens degrade to empty figures instead of
    dying on import.
    """
    try:
        connection.executescript(_SCHEMA)
        _migrate_budget_settings(connection)
        connection.commit()
    except sqlite3.Error:
        pass


def _migrate_budget_settings(connection: sqlite3.Connection) -> None:
    """Phase 8.1: add budget_settings.month_start_day to a database
    whose settings table was created before the column existed.

    WHY A MIGRATION IS NEEDED AT ALL
      The CREATE TABLE above runs only when the table does not exist, so
      a settings table written by Phase 7 keeps its original FIVE columns
      forever. This ALTER gives it the sixth.

    WHY DEFAULT 1 IS SAFE
      SQLite requires a non-null default when adding a NOT NULL column,
      and 1 is exactly the value budget_settings seeds - plain calendar
      months. Every existing row therefore keeps the behaviour it had
      before this phase until the user deliberately picks another day.

    Idempotent: the PRAGMA check means the ALTER runs at most once, and
    a database that already has the column (a fresh one, or any later
    launch) does nothing at all.
    """
    columns = [row[1] for row in
               connection.execute("PRAGMA table_info(budget_settings)")]
    if "month_start_day" not in columns:
        connection.execute(
            "ALTER TABLE budget_settings "
            "ADD COLUMN month_start_day INTEGER NOT NULL DEFAULT 1"
        )


# ---------------------------------------------------------------------------
# QUERY HELPERS - the only way a holder touches SQL.
# ---------------------------------------------------------------------------

def query(sql: str, params=()) -> list:
    """Run a SELECT and return a list of plain dicts (empty on failure).

    Empty list, not an exception: reads are on the Dashboard's repaint
    path and screens do not guard them. See the error rules at the top.
    """
    try:
        rows = _conn().execute(sql, params).fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def query_one(sql: str, params=()):
    """Run a SELECT expected to return at most one row.

    Returns the row as a dict, or None - both when there is genuinely
    nothing there and when the query failed, for the same reason as
    query() above.
    """
    try:
        row = _conn().execute(sql, params).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row is not None else None


def execute(sql: str, params=()) -> sqlite3.Cursor:
    """Run an INSERT / UPDATE / DELETE, commit it, return the cursor.

    The cursor is handed back because seeding and the daily-expense
    insert need lastrowid.

    Raises ValueError on failure - deliberately. Every screen catches
    ValueError from its holders and shows its inline warning, so a
    database problem surfaces as a normal "could not save" message and
    the window keeps running.
    """
    connection = _conn()
    try:
        cursor = connection.execute(sql, params)
        connection.commit()
        return cursor
    except sqlite3.Error as exc:
        try:
            connection.rollback()      # leave nothing half-written behind
        except sqlite3.Error:
            pass
        raise ValueError(f"Database error: {exc}") from exc


def get_meta(key: str):
    """Read one meta value, or None if it was never written."""
    row = query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    """Write one meta value (used to record a one-time decision)."""
    execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def close() -> None:
    """Close the shared connection so the next query reopens it.

    Only the persistence test uses this: closing and reopening in a
    fresh process is how "did it really hit the disk?" is answered.
    """
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except sqlite3.Error:
            pass
        _connection = None


def get_connection() -> sqlite3.Connection:
    """Open (or create) the database and return a connection the CALLER
    owns and must close.

    This is the Phase 1 contract and it is unchanged: main.py's startup
    probe calls it, runs sqlite_version() and closes the handle. It is
    deliberately NOT the shared connection - handing that out would let
    the probe close it underneath every holder.

    Use db.query()/db.execute() for application work.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)
