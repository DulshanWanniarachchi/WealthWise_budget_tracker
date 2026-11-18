
from app.core import db
from app.services import budget_settings

# Re-exported so callers can treat this module as the whole category API.
# The three budgets are not owned here - budget_settings owns them.
BUDGET_KEYS = budget_settings.BUDGET_KEYS
BUDGET_LABELS = budget_settings.BUDGET_LABELS

# ---------------------------------------------------------------------------
# 1. DEFAULTS - what a brand-new user starts with.
#    Written as node specs: a plain string is a category with no
#    sub-items, and a dict may carry "items". _insert_spec() writes them
#    into the table, so seeding stays readable.
#    EVERYTHING below is user-removable - nothing is locked.
# ---------------------------------------------------------------------------

DEFAULT_TREE = {
    "needs": [
        {"name": "Rent"},
        {"name": "Groceries"},
        {"name": "Meat (Proteins)"},
        {"name": "Bills (Electricity + Water)"},
        {"name": "Internet (Wifi + Mobile)"},
        {"name": "Transport/Fuel"},
    ],
    "wants": [
        {"name": "Movies"},
        {"name": "Cosmetics"},
        {"name": "Shopping + Installment payments"},
        {"name": "Subscriptions", "items": [
            "Google",
            "YouTube",
            "Spotify/Apple Music",
            "Netflix",
        ]},
        {"name": "Going out"},
    ],
    "savings": [
        {"name": "Transfers (Trading etc)"},
        {"name": "Standing Orders"},
        {"name": "FD"},
        {"name": "Money Market/FI"},
    ],
}

# The meta key that records "the default tree has been offered once".
_SEED_KEY = "categories_seeded"


# ---------------------------------------------------------------------------
# 2. MODULE STATE - only the subscription list is still held in memory.
#    The tree itself lives in the database now; the listeners are not
#    data, so there is nothing to persist about them.
# ---------------------------------------------------------------------------

_listeners: list = []  # callbacks to run after any successful change


# ---------------------------------------------------------------------------
# 3. ROW READS - the only place that knows the table's shape. Every one
#    returns plain dicts in INSERTION ORDER (ORDER BY id), which is the
#    order the screens have always displayed.
# ---------------------------------------------------------------------------

def _root_rows(budget: str) -> list:
    """Top-level categories of one budget: [{"id", "name"}, ...]."""
    return db.query(
        "SELECT id, name FROM categories "
        "WHERE budget = ? AND parent_id IS NULL ORDER BY id",
        (budget,),
    )


def _child_rows(parent_id: int) -> list:
    """Sub-items of one category: [{"id", "name"}, ...]."""
    return db.query(
        "SELECT id, name FROM categories WHERE parent_id = ? ORDER BY id",
        (parent_id,),
    )


def _row_node(row: dict) -> dict:
    """Turn one row into a node dict, recursing through its children.

    Recursion rather than a hard-coded second level: the in-memory model
    was a uniform tree, and this keeps that promise - a category with no
    items simply gets an empty list, and a deeper level would work with
    no change here.
    """
    return {
        "name": row["name"],
        "items": [_row_node(child) for child in _child_rows(row["id"])],
    }


# ---------------------------------------------------------------------------
# 4. VALIDATION - shared by every mutator. All of it raises ValueError,
#    which the UI catches. Nothing here touches the database before it
#    passes.
#
#    The helpers take a list of ROW dicts rather than nodes: a row has
#    "name" (which is all _index_of/_require_new/_require_at ask about)
#    plus "id" (which the mutators need in order to UPDATE or DELETE the
#    right row).
# ---------------------------------------------------------------------------

def _clean_name(name) -> str:
    """Return the trimmed name, or raise ValueError if unusable."""
    if not isinstance(name, str):
        raise ValueError(f"A name must be text, got {name!r}.")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("A name cannot be empty.")
    return cleaned


def _require_budget(budget: str) -> None:
    """Raise ValueError unless `budget` is one of the three budgets."""
    if budget not in BUDGET_KEYS:
        raise ValueError(
            f"Unknown budget {budget!r} - expected one of: {', '.join(BUDGET_KEYS)}."
        )


def _index_of(nodes: list, name: str) -> int:
    """Position of `name` among `nodes`, or -1.

    Comparison is case-insensitive so "Rent" and "rent" count as the
    same category - otherwise users could create two rows that read as
    duplicates and later break name lookups.
    """
    target = name.casefold()
    for position, node in enumerate(nodes):
        if node["name"].casefold() == target:
            return position
    return -1


def _require_new(nodes: list, name: str, parent: str) -> None:
    """Raise ValueError if `name` is already used by a sibling."""
    if _index_of(nodes, name) != -1:
        raise ValueError(f"{parent} already has an entry named '{name}'.")


def _require_at(nodes: list, name: str, parent: str) -> int:
    """Return the position of `name`, or raise ValueError if absent."""
    position = _index_of(nodes, name)
    if position == -1:
        raise ValueError(f"No entry named '{name}' under {parent}.")
    return position


def _category_row(budget: str, category: str) -> dict:
    """Resolve (budget, category) to its LIVE row, or raise ValueError.

    Shared by every sub-item operation and by count_items(). Returns
    {"id", "name"} - the id is what the SQL statements need, the name is
    what the error messages quote (they must read exactly as they did
    when this returned the node itself).
    """
    _require_budget(budget)
    rows = _root_rows(budget)
    position = _require_at(rows, _clean_name(category), BUDGET_LABELS[budget])
    return rows[position]


def _category_id(budget: str, category: str) -> int:
    """Just the id of _category_row() - for the pure-read helpers."""
    return _category_row(budget, category)["id"]


# ---------------------------------------------------------------------------
# 5. READ ACCESSORS - always return freshly built structures.
# ---------------------------------------------------------------------------

def get_structure() -> dict:
    """Return {'needs': [node, ...], 'wants': ..., 'savings': ...}.

    Built from the database on every call, so what a caller gets is
    always a fresh set of dicts: mutating it cannot change the stored
    tree (there is nothing behind it to change any more, but the
    contract callers were written against is kept).
    """
    return {key: [_row_node(row) for row in _root_rows(key)] for key in BUDGET_KEYS}


def get_categories(budget: str) -> list:
    """Return one budget's category nodes (with their sub-items)."""
    _require_budget(budget)
    return [_row_node(row) for row in _root_rows(budget)]


def count_items(budget: str, category: str) -> int:
    """How many sub-items a category has - handy for the UI's labels."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM categories WHERE parent_id = ?",
        (_category_id(budget, category),),
    )
    return row["n"] if row else 0


def get_items(budget: str, category: str) -> list:
    """The sub-item NAMES under one category, as a plain list of strings.

    The read counterpart to count_items(): that one says HOW MANY, this
    one says WHICH. Phase 5 needs the names because a fixed expense may
    point at a sub-item by name (see fixed_expenses), and the Fixed
    Expenses screen needs them to fill its sub-item dropdown.

    Returns a fresh list, like every other read here, so a caller cannot
    mutate the tree by accident. Raises ValueError when the budget is
    unknown or the category is not in it - exactly like count_items(),
    because both ask _category_row() the same question.
    """
    return [row["name"] for row in _child_rows(_category_id(budget, category))]


# ---------------------------------------------------------------------------
# 6. MUTATORS - category level (under a budget).
#    validate first, write second, notify last. If validation raises,
#    nothing has been stored and no subscriber is disturbed, so the
#    screen's open form stays exactly as the user left it.
# ---------------------------------------------------------------------------

def add_category(budget: str, name: str) -> None:
    """Add a new category under `budget`. Raises ValueError if the name
    is empty, not text, already used in that budget, or the budget is
    unknown."""
    _require_budget(budget)
    name = _clean_name(name)
    _require_new(_root_rows(budget), name, BUDGET_LABELS[budget])
    db.execute(
        "INSERT INTO categories (budget, parent_id, name) VALUES (?, NULL, ?)",
        (budget, name),
    )
    _notify()


def rename_category(budget: str, old_name: str, new_name: str) -> None:
    """Rename a category, keeping its sub-items attached.

    Sub-items hang off this row's id, so they follow the rename
    automatically - that is the structural part of the tree working as
    designed. (Expense links are names, so THEY break; see reconcile()
    in fixed_expenses.py / daily_expenses.py.)
    """
    _require_budget(budget)
    old_name = _clean_name(old_name)
    new_name = _clean_name(new_name)
    rows = _root_rows(budget)
    position = _require_at(rows, old_name, BUDGET_LABELS[budget])

    # Renaming a node to the name it already has is a no-op, not a
    # duplicate error (the uniqueness check would otherwise see itself).
    if new_name.casefold() == old_name.casefold():
        return

    _require_new(rows, new_name, BUDGET_LABELS[budget])
    db.execute(
        "UPDATE categories SET name = ? WHERE id = ?",
        (new_name, rows[position]["id"]),
    )
    _notify()


def delete_category(budget: str, name: str) -> None:
    """Delete a category AND everything nested under it.

    The nesting is removed by the database itself: parent_id carries
    ON DELETE CASCADE, so deleting this row deletes its sub-items too
    (app/core/db.py turns foreign keys on - SQLite ships with them off).

    Defaults are deletable like any other - nothing is locked.

    Note that expenses pointing at this category are NOT touched here:
    their links are names, so they simply become dangling and
    reconcile() marks them "Uncategorised" a moment later (it runs as a
    subscriber). Money never disappears with a label.
    """
    _require_budget(budget)
    name = _clean_name(name)
    rows = _root_rows(budget)
    position = _require_at(rows, name, BUDGET_LABELS[budget])
    db.execute("DELETE FROM categories WHERE id = ?", (rows[position]["id"],))
    _notify()


# ---------------------------------------------------------------------------
# 7. MUTATORS - sub-item level (under a category).
#    Any category may hold items; none is privileged. Each one starts by
#    resolving the category through _category_row() in section 4, which
#    is where a wrong budget or a missing category is reported.
# ---------------------------------------------------------------------------

def add_item(budget: str, category: str, name: str) -> None:
    """Add a sub-item under `category`."""
    parent = _category_row(budget, category)
    name = _clean_name(name)
    _require_new(_child_rows(parent["id"]), name, f"'{parent['name']}'")
    db.execute(
        "INSERT INTO categories (budget, parent_id, name) VALUES (?, ?, ?)",
        (budget, parent["id"], name),
    )
    _notify()


def rename_item(budget: str, category: str, old_name: str, new_name: str) -> None:
    """Rename a sub-item, keeping its position in the list."""
    parent = _category_row(budget, category)
    old_name = _clean_name(old_name)
    new_name = _clean_name(new_name)
    items = _child_rows(parent["id"])
    position = _require_at(items, old_name, f"'{parent['name']}'")

    if new_name.casefold() == old_name.casefold():
        return

    _require_new(items, new_name, f"'{parent['name']}'")
    db.execute(
        "UPDATE categories SET name = ? WHERE id = ?",
        (new_name, items[position]["id"]),
    )
    _notify()


def delete_item(budget: str, category: str, name: str) -> None:
    """Delete one sub-item (the category itself stays)."""
    parent = _category_row(budget, category)
    name = _clean_name(name)
    items = _child_rows(parent["id"])
    position = _require_at(items, name, f"'{parent['name']}'")
    db.execute("DELETE FROM categories WHERE id = ?", (items[position]["id"],))
    _notify()


# ---------------------------------------------------------------------------
# 8. SEEDING - the default tree, ONCE per database.
# ---------------------------------------------------------------------------

def _insert_spec(budget: str, parent_id, spec) -> None:
    """Write one DEFAULT_TREE entry (and its children) as rows.

    Accepts either "Rent" or {"name": "Subscriptions", "items": [...]}.
    The insert returns the new row's id, which becomes the parent id for
    whatever nests underneath - that is the whole of the tree in one
    small recursion.

    Also used by the test helpers in section 10, which is why it is
    separate from _seed_if_new(): "write these nodes" and "decide whether
    to write the defaults" are two different jobs.
    """
    if isinstance(spec, str):
        spec = {"name": spec}
    cursor = db.execute(
        "INSERT INTO categories (budget, parent_id, name) VALUES (?, ?, ?)",
        (budget, parent_id, spec["name"]),
    )
    for child in spec.get("items", []):
        _insert_spec(budget, cursor.lastrowid, child)


def _seed_if_new() -> None:
    """Write DEFAULT_TREE only on a database that has never been seeded.

    TWO conditions, both required, and the difference between them
    matters:

      * the meta flag says "this database has been initialised once".
        It is written even when nothing was inserted, so a user who
        deletes every category does NOT get the defaults back on the
        next launch - empty must stay empty;
      * the emptiness check says "there is nothing here to preserve",
        which is what makes a brand-new file receive the tree.

    A database that already has categories (an upgrade from Phase 6, or
    one where the user has been working) is left completely alone: only
    the flag is set.

    Failure is swallowed, like budget_settings' seeding: the app must
    start even if the file is unwritable, and the reads above will then
    report an empty tree rather than raising.
    """
    if db.get_meta(_SEED_KEY) is not None:
        return                                   # decided once, never again
    try:
        if db.query_one("SELECT id FROM categories LIMIT 1") is None:
            for budget in BUDGET_KEYS:
                for spec in DEFAULT_TREE[budget]:
                    _insert_spec(budget, None, spec)
        db.set_meta(_SEED_KEY, "1")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# 9. CHANGE NOTIFICATION - same contract as budget_settings.
# ---------------------------------------------------------------------------

def subscribe(callback) -> None:
    """Register a zero-argument callback to run after every successful
    change. The Categories screen subscribes its rebuild method once at
    startup; there is nothing to unsubscribe for the app's lifetime.
    """
    if callback not in _listeners:
        _listeners.append(callback)


def _notify() -> None:
    """Run every subscriber - only AFTER a change was stored, so
    listeners always read a valid tree."""
    for callback in _listeners:
        callback()


# ---------------------------------------------------------------------------
# 10. TEST SUPPORT - lets a suite start from a known state. NOT used by
#    the UI: there is no "reset" button because there is nothing to
#    reset to. Both helpers are deliberately SILENT (no notify), exactly
#    like the `_tree = _fresh_tree()` assignment they replaced: a suite
#    that swaps the tree behind the holder's back must not also trigger
#    reconcile(), or it would be testing its own shortcut.
# ---------------------------------------------------------------------------

def _reset() -> None:
    """Put the default tree back (test helper). Does not notify."""
    db.execute("DELETE FROM categories")
    for budget in BUDGET_KEYS:
        for spec in DEFAULT_TREE[budget]:
            _insert_spec(budget, None, spec)


def _replace_structure(structure: dict) -> None:
    """Swap the whole tree in one go (test helper). Does not notify.

    Takes the shape get_structure() returns, so a suite can save the
    tree, empty it, and put the original back byte-for-byte.
    """
    db.execute("DELETE FROM categories")
    for budget in BUDGET_KEYS:
        for node in structure.get(budget, []):
            _insert_spec(budget, None, node)


# ---------------------------------------------------------------------------
# 11. STARTUP - seed a brand-new database before anyone reads from it.
# ---------------------------------------------------------------------------

_seed_if_new()
