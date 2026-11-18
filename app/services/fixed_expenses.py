

from app.core import db
from app.core.text_rules import cap_first
from app.services import budget_settings, category_settings

# The actual money lives in daily_expenses.py; this file only READS it,
# to answer "how much of this plan has been spent?". The dependency runs
# one way only - daily_expenses deliberately does NOT import this module
# (its cascade is daily-only) - so the import graph stays acyclic:
# fixed_expenses -> daily_expenses -> budget_settings/category_settings.
from app.services import daily_expenses

# Re-exported so callers (and this file's error messages) never have to
# import budget_settings just to name a budget.
BUDGET_KEYS = budget_settings.BUDGET_KEYS
BUDGET_LABELS = budget_settings.BUDGET_LABELS

# A brand-new user has no fixed expenses. This is deliberately empty -
# Phase 5 seeds nothing.
DEFAULT_EXPENSES: list = []


# ---------------------------------------------------------------------------
# 1. STORAGE - the table and the two private reads everything below goes
#    through. There is no module-level list any more: the ROWS are the
#    state, which is exactly why a restart sees the same plans.
# ---------------------------------------------------------------------------

_TABLE = "fixed_expenses"

# The exact fields the public API has always returned. The table also
# carries an `id`, but it is deliberately NOT projected out: callers were
# written against these five, and handing them a sixth would make an
# innocent dict comparison fail for no reason.
_RECORD_FIELDS = ("name", "amount", "budget", "category", "sub_item")


def _rows(budget: str = None) -> list:
    """Every stored record WITH its id, oldest first.

    The id is what UPDATE / DELETE key on internally; _project() strips
    it again on the way out to callers. Pass a budget to filter in the
    database instead of in Python - the budget has already been validated
    by the time any caller uses this, so the parameter is safe to bind.
    """
    if budget is None:
        return db.query(
            "SELECT id, name, amount, budget, category, sub_item "
            f"FROM {_TABLE} ORDER BY id"
        )
    return db.query(
        "SELECT id, name, amount, budget, category, sub_item "
        f"FROM {_TABLE} WHERE budget = ? ORDER BY id",
        (budget,),
    )


def _project(row: dict) -> dict:
    """The public shape of one row: the five fields, no id."""
    return {key: row[key] for key in _RECORD_FIELDS}


_listeners: list = []             # callbacks to run after any change


# ---------------------------------------------------------------------------
# 2. VALIDATION - private, and the ONLY thing that decides what is legal.
#    Every public mutator runs these, so bad data cannot be stored even
#    if a future screen skips its own checking.
# ---------------------------------------------------------------------------

def _clean_name(name) -> str:
    """Return the expense name, or raise ValueError if it is blank.

    Strips the whitespace a text field collects; rejects anything that
    reduces to nothing at all.

    Phase 6 also runs the GENTLE capitalisation rule here (see
    app/core/text_rules.py): first letter up, everything else exactly as
    typed - "netflix" becomes "Netflix" while "FD" and "iPhone" are left
    alone. It applies on ADD and EDIT only, i.e. to new entries; nothing
    already stored is ever rewritten.
    """
    if not isinstance(name, str):
        raise ValueError(f"A fixed expense needs a name, got {name!r}.")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("A fixed expense needs a name.")
    return cap_first(cleaned)


def _clean_amount(value) -> int:
    """Return the amount as a whole non-negative number of rupees.

    Accepts an int directly, OR the raw string from a text field - that
    is why validation lives here and not in the screen: the screen can
    hand over whatever the user typed and still be sure the holder only
    ever stores a clean int.

    Rejects decimals ("-5", "1200.50"), letters, blanks and booleans
    (bool is a subclass of int in Python, so `True` must be caught
    explicitly before the int branch would wave it through).
    """
    if isinstance(value, bool):                     # True/False are not money
        raise ValueError(f"An amount must be a number of rupees, got {value!r}.")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"An amount cannot be negative, got {value}.")
        return value
    if isinstance(value, str):
        # Commas are a display convention (Rs. 25,000), not part of the
        # number - strip them so pasting a formatted figure still works.
        text = value.strip().replace(",", "")
        if not text.isdecimal():                    # "12.5", "-1", "abc", ""
            raise ValueError(
                "An amount must be a non-negative whole number of rupees, "
                f"got {value!r}."
            )
        return int(text)
    raise ValueError(f"An amount must be a number of rupees, got {value!r}.")


def _require_budget(budget: str) -> str:
    """Return the budget key, or raise ValueError if it is not one of the three."""
    if budget in BUDGET_KEYS:
        return budget
    raise ValueError(f"Unknown budget {budget!r} - pick Needs, Wants or Savings.")


def _resolve_category(budget: str, category) -> str:
    """Return the category's CANONICAL name in `budget`, or raise ValueError.

    Case and surrounding whitespace are ignored on the way in, so
    "housing" finds "Housing" - but what is stored is always the spelling
    category_settings actually uses, which keeps the link exact.
    """
    _require_budget(budget)
    if not isinstance(category, str) or not category.strip():
        raise ValueError("Pick a category for this fixed expense.")
    wanted = category.strip().casefold()
    for node in category_settings.get_categories(budget):
        if node["name"].casefold() == wanted:
            return node["name"]
    # Distinguish "no categories at all" from "you picked one that is not
    # there" - the first needs a different next step for the user.
    if not category_settings.get_categories(budget):
        raise ValueError(
            f"{BUDGET_LABELS[budget]} has no categories yet - add one on the "
            "Categories screen first."
        )
    raise ValueError(
        f"{BUDGET_LABELS[budget]} has no category named {category.strip()!r}."
    )


def _category_exists(budget: str, category: str) -> bool:
    """True if that category is still in the tree. Never raises."""
    try:
        _resolve_category(budget, category)
    except ValueError:
        return False
    return True


def _resolve_sub_item(budget: str, category: str, sub_item):
    """Return the sub-item's CANONICAL name, or None if none was asked for.

    The sub-item is OPTIONAL: None - or a blank string, which is what a
    field that was never touched looks like - means the expense attaches
    at CATEGORY level only, which is how every expense behaved before
    this field existed and how most of them still should.

    When one IS given it must exist under `category` in category_settings
    RIGHT NOW, exactly like the category rule above and for the same
    reason: a dangling name could later match an unrelated sub-item the
    user created for something else. Case and surrounding whitespace are
    ignored on the way in ("netflix" finds "Netflix") and the tree's own
    spelling is what comes back out, so what is stored always matches
    category_settings exactly.

    The category itself is resolved by the caller BEFORE this runs, so a
    missing category is reported there - with the better "add one on the
    Categories screen" message - rather than as a sub-item complaint.
    """
    if sub_item is None:
        return None
    if not isinstance(sub_item, str):
        raise ValueError(f"A sub-item must be text, got {sub_item!r}.")
    given = sub_item.strip()
    if not given:
        return None                      # blank == "no sub-item chosen"
    # Raises only if the CATEGORY is missing; the caller has already
    # checked that, so in practice this is just "read the item names".
    items = category_settings.get_items(budget, category)
    wanted = given.casefold()
    for item in items:
        if item.casefold() == wanted:
            return item
    # Two different mistakes, two different next steps for the user.
    if not items:
        raise ValueError(
            f"'{category}' has no sub-items - add one on the Categories "
            "screen first, or leave this expense at category level."
        )
    raise ValueError(
        f"'{category}' has no sub-item named {given!r} - add it on the "
        "Categories screen first."
    )


def _sub_item_exists(budget: str, category: str, sub_item: str) -> bool:
    """True if that sub-item is still under that category. Never raises."""
    try:
        items = category_settings.get_items(budget, category)
    except ValueError:
        return False                      # the category went with it
    return any(item.casefold() == sub_item.casefold() for item in items)


def _require_free_name(name: str, ignore: str = None) -> None:
    """Raise if another expense already uses this name (case-insensitive).

    `ignore` is the name of the record being edited, so an expense may
    keep its own name when you save without renaming it.
    """
    wanted = name.casefold()
    for expense in _rows():
        if ignore is not None and expense["name"].casefold() == ignore.casefold():
            continue
        if expense["name"].casefold() == wanted:
            raise ValueError(f"There is already a fixed expense named {name!r}.")


def _require_known(name: str) -> dict:
    """Return the stored ROW (with its id) matching this name, or raise.

    Unlike the public reads this one INCLUDES the id, because update and
    delete need to know which row to write. Code outside this module
    should use get_expense() instead, which returns the five public
    fields only.
    """
    wanted = name.strip().casefold() if isinstance(name, str) else ""
    for expense in _rows():
        if expense["name"].casefold() == wanted:
            return expense
    raise ValueError(f"No fixed expense named {name!r}.")


# ---------------------------------------------------------------------------
# 3. READS - always return copies, so a caller can never mutate our state
#    by accident (the same rule the other two holders follow).
# ---------------------------------------------------------------------------

def get_expenses() -> list:
    """Every fixed expense, in the order they were added."""
    return [_project(row) for row in _rows()]


def get_expenses_for(budget: str) -> list:
    """The fixed expenses under one budget (Needs / Wants / Savings)."""
    _require_budget(budget)
    return [_project(row) for row in _rows(budget)]


def get_totals_by_budget() -> dict:
    """Total PLANNED amount for each budget: {"needs": 60000, ...}.

    The sum of the plans - what the user INTENDS to spend per budget.
    It is not money spent and feeds no remaining/spent figure anywhere
    (the cascade never reads it); the Fixed Expenses screen uses it as
    each section's header total.
    Uncategorised expenses are INCLUDED - only their category link is
    broken, their budget link never is, and the plan itself is unchanged.
    """
    totals = {key: 0 for key in BUDGET_KEYS}
    for expense in _rows():
        totals[expense["budget"]] += expense["amount"]
    return totals


def get_total() -> int:
    """Grand total PLANNED across all budgets (every plan's amount)."""
    row = db.query_one(f"SELECT COALESCE(SUM(amount), 0) AS total FROM {_TABLE}")
    return row["total"] if row else 0


def count() -> int:
    """How many fixed expenses exist (the screen's empty-state check)."""
    row = db.query_one(f"SELECT COUNT(*) AS n FROM {_TABLE}")
    return row["n"] if row else 0


def has(name: str) -> bool:
    """True if a fixed expense with this name already exists."""
    return get_expense(name) is not None


def get_expense(name):
    """Return a COPY of one fixed expense, or None if it does not exist.

    Used by the screen to load a row into the form for editing. Returns
    None rather than raising, because "which one?" is a question a caller
    often wants to answer for itself.
    """
    wanted = name.strip().casefold() if isinstance(name, str) else ""
    if not wanted:
        return None
    for expense in _rows():
        if expense["name"].casefold() == wanted:
            return _project(expense)
    return None


# ---------------------------------------------------------------------------
# 3b. THE PLAN READS - how much of each plan actual spending has covered.
#     Added with the plan fix: fixed expenses are the monthly PLAN and
#     daily expenses are the actual money (see THE CASCADE MATHS in
#     daily_expenses.py), so these are the only functions in the app
#     that ever bring the two together. The comparison maths lives HERE,
#     never in the Fixed Expenses screen - the screen only formats and
#     paints what it gets back.
#
#     PHASE 8.2 FIX (2026-11-18): a plan is MONTHLY, so "spent against
#     it" and "Paid" now mean THIS SALARY CYCLE. Both reads below sum
#     _daily_this_cycle() instead of every row ever - only daily expenses
#     dated inside budget_settings.cycle_bounds() count, compared with
#     the same lexicographic "YYYY-MM-DD" rule the cascade uses (no date
#     parsing). Before this fix an expense logged LAST cycle could still
#     mark this month's plan "✓ Paid", which is exactly why the Fixed
#     Expenses screen and the Dashboard disagreed about the same money.
#
#     What did NOT change, deliberately:
#       * _matches_plan() still decides WHICH plan an expense belongs to
#         (budget + category + sub-item). It has never looked at dates
#         and still does not - the window is applied to the records
#         handed TO it, not to the matching rule;
#       * the three-way under/met/over state and over_by are computed
#         from the windowed total exactly as before;
#       * section 3c (get_plan_vs_allocation, the "plan exceeds
#         allocation" warning) compares PLANNED against ALLOCATED - no
#         spending is involved, so it was left untouched.
# ---------------------------------------------------------------------------

def _cycle_window() -> tuple:
    """(first day, last day) of the CURRENT salary cycle, as ISO strings.

    Phase 8.2 fix: the window the plan reads below count over. The
    arithmetic belongs to budget_settings.cycle_bounds() (Phase 8.1) -
    all this does is turn the two dates into the "YYYY-MM-DD" strings
    daily_expenses stores, which is formatting rather than date maths,
    so this file still contains no calendar logic of its own.

    Deliberately the same three lines as daily_expenses._cycle_window():
    a plan is monthly and the cascade is monthly, so they MUST describe
    the same window - phase8_2_test asserts the two helpers agree, which
    is what keeps them from drifting apart. (It is private rather than
    imported from there because daily_expenses must not grow a public
    window API just for this, and fixed_expenses -> daily_expenses is
    already the one allowed direction between the two.)

    Re-read on EVERY call, never cached: the cycle rolls over while the
    app is open and the user can change the start day in Settings.
    """
    start, end = budget_settings.cycle_bounds()
    return start.isoformat(), end.isoformat()


def _daily_this_cycle() -> list:
    """The daily expenses dated inside the CURRENT salary cycle.

    The only "money spent" the plan reads below are allowed to see, and
    the whole point of the Phase 8.2 fix: a plan is a monthly target, so
    it can only be measured against this month's payments. An expense
    from an earlier cycle is still real money - it simply has already
    been counted against an earlier copy of the plan.

    The filter is the lexicographic string comparison the cascade uses
    (first <= date <= last): "YYYY-MM-DD" sorts in day order, so no row
    is ever parsed. `or ""` sorts a defensive blank BEFORE every real
    date, so a malformed row falls outside the window instead of raising.

    Still a READ of daily_expenses.get_expenses() (the full ledger), so
    the window is applied here rather than by narrowing the ledger - the
    Daily Expenses screen keeps listing, editing and deleting every row
    it always did.
    """
    first, last = _cycle_window()
    return [d for d in daily_expenses.get_expenses()
            if first <= (d["date"] or "") <= last]

def _matches_plan(plan: dict, daily: dict) -> bool:
    """Does this daily expense count toward this plan? THE matching rule.

    A daily expense D counts toward a fixed plan P exactly when:

      1. the budgets match (needs / wants / savings), AND
      2. the categories match - both sides are stored in the category
         tree's canonical spelling (they are resolved through
         category_settings when saved); compared casefold() so a stale
         capitalisation cannot hide money, AND
      3. either
           a. the plan has NO sub-item (a plan for the whole category):
              every daily expense in that category counts, including
              ones logged against sub-items; or
           b. the plan HAS a sub-item: only daily expenses logged
              against that exact sub-item (casefold compare) count -
              category-level spending does NOT pay a sub-item plan.

    A plan whose category link broke (category is None) matches
    NOTHING: pairing two broken links would credit unrelated money to
    the plan. Its spent figure reads 0 until the user re-attaches it in
    Edit - and that is display-only, the daily money itself still
    counts as spending and still reduces the budget (see
    daily_expenses.py).

    Matching decides only WHICH PLAN an expense is shown against. It
    never gates whether the expense counts: every daily expense reduces
    remaining no matter what; a category with no plan simply has
    nothing to compare against.
    """
    if plan["category"] is None or daily["category"] is None:
        return False
    if plan["budget"] != daily["budget"]:
        return False
    if plan["category"].casefold() != daily["category"].casefold():
        return False
    if plan["sub_item"] is None:
        return True      # a plan for the whole category: any spend counts
    return (daily["sub_item"] is not None
            and daily["sub_item"].casefold() == plan["sub_item"].casefold())


def get_spent_against(name: str) -> int:
    """Daily spending THIS SALARY CYCLE against ONE plan, by name.

    THE "spent against plan" read: the sum of every daily expense
    _matches_plan() accepts for that fixed expense, counted only when it
    is dated inside today's salary cycle (Phase 8.2 fix). Last cycle's
    payments no longer mark this cycle's plan as covered - see
    _daily_this_cycle().

    0 when the expense does not exist, or when nothing has been logged
    against it THIS CYCLE. Read-only - the money itself stays in
    daily_expenses, and the matching rule itself is unchanged.
    """
    plan = get_expense(name)
    if plan is None:
        return 0
    return sum(d["amount"] for d in _daily_this_cycle()
               if _matches_plan(plan, d))


def get_plan_progress() -> list:
    """One status dict per fixed expense, in get_expenses() order:

        {"name", "budget", "category", "sub_item",
         "planned" : the fixed amount (the plan),
         "spent"   : THIS cycle's daily money matched against it,
         "progress": spent / planned clamped to 0.0..1.0 - bar-ready,
         "paid"    : spent >= planned - the plan is COVERED this cycle,
         "state"   : "under" | "met" | "over" - THE three-way comparison
                     (Phase 7), so "over plan" can never be mistaken
                     for "cleanly paid" on screen,
         "over_by" : spent - planned when state is "over", else 0}

    The three states, exactly:
        under  - spent <  planned: in progress, bar part-full,
        met    - spent == planned: cleanly paid ("✓ Paid", success),
        over   - spent >  planned: overspent, and it must LOOK like a
                 warning - danger colour, "Over by Rs. ..." label.

    paid stays True for "over" as well (the plan IS covered - the
    money exceeded it), but the screen keys off state, never off paid,
    so an over-plan row can never render as a clean tick.

    PHASE 8.2 FIX: `spent` is this cycle's, so every figure derived from
    it - progress, paid, state, over_by - resets with the cycle too. The
    arithmetic below is byte-for-byte what it was; only the ledger it
    reads (_daily_this_cycle()) narrowed. A plan whose whole payment
    happened last month therefore reads state "under" / paid False again
    on the first day of a new cycle, which is what "monthly plan" means.

    The Fixed Expenses screen reads this ONCE per rebuild so every row
    shows the same instant, then only formats text and paints - all
    arithmetic happens here. progress is clamped here too, so no caller
    can show a >100% bar (an over-plan bar shows FULL + danger rather
    than a >100% fill).

    planned == 0: there is nothing to pay, so the plan reports
    progress 1.0 / paid True / state "met" immediately - consistent
    with its own rule spent >= planned (0 >= 0) rather than
    contradicting it. (Any spending against a 0 plan is state "over".)
    """
    daily = _daily_this_cycle()
    out = []
    for plan in _rows():
        spent = sum(d["amount"] for d in daily if _matches_plan(plan, d))
        planned = plan["amount"]
        # THE three-way comparison (Phase 7). Written out longhand
        # rather than folded into "paid" so the screen can never
        # conflate "exactly met" with "gone past".
        if spent < planned:
            state, over_by = "under", 0
        elif spent > planned:
            state, over_by = "over", spent - planned
        else:
            state, over_by = "met", 0
        out.append({
            "name": plan["name"],
            "budget": plan["budget"],
            "category": plan["category"],
            "sub_item": plan["sub_item"],
            "planned": planned,
            "spent": spent,
            "progress": 1.0 if planned <= 0 else min(spent / planned, 1.0),
            "paid": spent >= planned,
            "state": state,
            "over_by": over_by,
        })
    return out


# ---------------------------------------------------------------------------
# 3c. PLAN vs ALLOCATION - is one budget's PLAN bigger than its slice of
#     the salary? (Warning #2 of the overspend warnings, Phase 7.)
#     Comparison only: it never blocks anything and never moves money -
#     the user is free to plan more than they allocated; the Fixed
#     Expenses screen just says so out loud.
#
#     DELIBERATELY UNTOUCHED by the Phase 8.2 fix: this compares PLANNED
#     against ALLOCATED - two figures that have nothing to do with when
#     money was spent - so it has no window and needs none. Only section
#     3b (plan vs SPENDING) became current-cycle.
# ---------------------------------------------------------------------------

def get_plan_vs_allocation() -> dict:
    """Per budget: what is PLANNED vs what is ALLOCATED.

        {"needs" | "wants" | "savings":
            {"planned"  : sum of this budget's fixed expenses (the plan),
             "allocated": salary x percentage for this budget,
             "exceeds"  : planned > allocated - THE warning flag,
             "over_by"  : planned - allocated when it exceeds, else 0}}

    THE "plan exceeds allocation" comparison, living here (in the plan
    holder) rather than in the screen, per the rule that comparison
    maths belongs in holders. Sources: get_totals_by_budget() for the
    planned side, budget_settings.get_allocations() for the slice -
    this function changes neither and notifies nobody; it only reads
    and compares. The screen calls it once per rebuild and paints the
    warning line under the section header when exceeds is True.
    """
    planned = get_totals_by_budget()
    allocations = budget_settings.get_allocations()
    out = {}
    for key in BUDGET_KEYS:
        p, a = planned[key], allocations[key]
        out[key] = {
            "planned": p,
            "allocated": a,
            "exceeds": p > a,
            "over_by": (p - a) if p > a else 0,
        }
    return out


# ---------------------------------------------------------------------------
# 4. MUTATORS - validate first, mutate second, notify last. If validation
#    raises, nothing has been touched and no subscriber is disturbed, so
#    the screen's open form stays exactly as the user left it.
# ---------------------------------------------------------------------------

def add_fixed_expense(name, amount, budget, category, sub_item=None) -> None:
    """Validate and append a new fixed expense, then notify subscribers.

    Every field comes from the user; nothing here is a default. The
    category must exist in `category_settings` under `budget` right now,
    and `sub_item` - which is OPTIONAL, so leaving it out (or passing
    None) simply stores None - must exist under that category if it is
    given, or the call raises ValueError and stores nothing.
    """
    clean_name = _clean_name(name)
    clean_amount = _clean_amount(amount)
    clean_budget = _require_budget(budget)
    clean_category = _resolve_category(clean_budget, category)
    clean_sub_item = _resolve_sub_item(clean_budget, clean_category, sub_item)
    _require_free_name(clean_name)

    # Validation passed - only now touch the database, so a refused add
    # stores nothing and notifies nobody.
    db.execute(
        f"INSERT INTO {_TABLE} (name, amount, budget, category, sub_item) "
        "VALUES (?, ?, ?, ?, ?)",
        (clean_name, clean_amount, clean_budget, clean_category, clean_sub_item),
    )
    _notify()


def update_fixed_expense(old_name, name, amount, budget, category,
                         sub_item=None) -> None:
    """Replace an existing fixed expense in place, then notify subscribers.

    `old_name` identifies which record to change (names are identity).
    The new name must not collide with a DIFFERENT expense's name, which
    is what `ignore=old_name` makes possible: saving without renaming is
    allowed.

    Editing is also how a user re-attaches an uncategorised expense: the
    category is re-resolved and stored fresh, so a broken link is healed
    by simply saving. The same is true of the sub-item, and the two are
    resolved in that order - a sub-item can only be validated against a
    category that exists.

    `sub_item` defaults to None, meaning "category level only". The
    screen always passes the picker's current value explicitly, so
    editing never loses a sub-item by accident; a caller that passes
    nothing is saying the expense should attach at category level.
    """
    record = _require_known(old_name)

    clean_name = _clean_name(name)
    clean_amount = _clean_amount(amount)
    clean_budget = _require_budget(budget)
    clean_category = _resolve_category(clean_budget, category)
    clean_sub_item = _resolve_sub_item(clean_budget, clean_category, sub_item)
    _require_free_name(clean_name, ignore=old_name)

    # Validation passed - only now touch the record, so a rejected edit
    # leaves the stored expense untouched.
    db.execute(
        f"UPDATE {_TABLE} SET name = ?, amount = ?, budget = ?, "
        "category = ?, sub_item = ? WHERE id = ?",
        (clean_name, clean_amount, clean_budget, clean_category,
         clean_sub_item, record["id"]),
    )
    _notify()


def delete_fixed_expense(name) -> None:
    """Remove one fixed expense by name, then notify subscribers.

    The row goes; the category it pointed at does not (nothing here
    touches the tree), so deleting a plan can never cascade into anyone
    else's data.
    """
    record = _require_known(name)
    db.execute(f"DELETE FROM {_TABLE} WHERE id = ?", (record["id"],))
    _notify()


# ---------------------------------------------------------------------------
# 5. RECONCILIATION - the "handle a deleted link gracefully" rules.
#    Two independent links, checked in a fixed order; the module
#    docstring spells out the four cases this implements.
# ---------------------------------------------------------------------------

def reconcile() -> int:
    """Repair every expense whose category OR sub-item link has broken.

    Called as a subscriber to category_settings, so it runs after ANY
    change in the tree - deleting and renaming both break a name-based
    link and are both handled here, at whichever level they happened.

    The rules, in the order they are applied to each record:

      1. category gone (deleted or renamed)  ->  category = None AND
         sub_item = None. A sub-item only exists underneath its
         category, so it cannot outlive one.
      2. category still there, sub-item gone (deleted or renamed)  ->
         sub_item = None, category UNTOUCHED. The expense is still
         correctly filed under its category; only the finer link broke.
      3. both links healthy  ->  untouched.
      4. category already None  ->  sub_item is cleared if it is
         somehow still set (the mutators never store that pair; this
         keeps the invariant true even for a record that arrived from
         elsewhere).

    Returns how many RECORDS it changed - a record that loses both links
    still counts as one - so the caller (and the docstring above) can
    see whether anything happened; _notify() only fires when the answer
    is not zero.

    Also public so a test can call it directly.
    """
    changed = 0
    for expense in _rows():
        category = expense["category"]
        sub_item = expense["sub_item"]
        new_category, new_sub_item = category, sub_item

        if category is None:
            # Rule 4: already uncategorised - a sub-item must not
            # outlive its category (defensive; see the docstring).
            if sub_item is None:
                continue
            new_sub_item = None
        elif not _category_exists(expense["budget"], category):
            # Rule 1: the whole category is gone (deleted OR renamed).
            # Drop it rather than guess - and take the sub-item with it,
            # since a sub-item of a category we can no longer name would
            # be a dangling half-link.
            new_category = None
            new_sub_item = None
        elif sub_item is not None and not _sub_item_exists(
                expense["budget"], category, sub_item):
            # Rule 2: only the sub-item went (deleted OR renamed).
            # The category link is healthy, so it stays - the expense
            # is still filed in the right place.
            new_sub_item = None
        else:
            continue                      # rule 3: both links healthy

        # Nothing is written unless a link actually broke, so a clean
        # tree costs one SELECT per record and no UPDATEs at all.
        db.execute(
            f"UPDATE {_TABLE} SET category = ?, sub_item = ? WHERE id = ?",
            (new_category, new_sub_item, expense["id"]),
        )
        changed += 1

    if changed:
        _notify()
    return changed


# ---------------------------------------------------------------------------
# 6. CHANGE NOTIFICATION - same contract as the other two holders.
# ---------------------------------------------------------------------------

def subscribe(callback) -> None:
    """Register a zero-argument callback to run after every change."""
    if callback not in _listeners:
        _listeners.append(callback)


def _notify() -> None:
    """Run every subscriber. Copy the list first: a subscriber may
    unsubscribe (or subscribe) while we are walking it."""
    for callback in list(_listeners):
        callback()


# ---------------------------------------------------------------------------
# 7. WIRING - this service listens to the category tree, because the two
#    are linked. Registered at import time: fixed_expenses imports
#    category_settings (never the other way round), so there is no cycle,
#    and the module is imported before any screen is constructed - which
#    guarantees this subscriber runs BEFORE the Fixed Expenses screen's
#    own reload, so the UI is never shown a stale link.
# ---------------------------------------------------------------------------

category_settings.subscribe(reconcile)


# ---------------------------------------------------------------------------
# 8. TEST SUPPORT - lets a test start from a known state. NOT used by the
#    UI: there is no "reset" button because there are no defaults to
#    reset to.
# ---------------------------------------------------------------------------

def _reset() -> None:
    """Delete every plan (test helper). Does not notify.

    The id sequence is left alone on purpose: fixed-expense ids are an
    internal detail that never reaches a screen or a test (the public
    dict is five fields), so there is nothing to rewind. Names are what
    identify these records, and a DELETE frees them again.
    """
    db.execute(f"DELETE FROM {_TABLE}")
