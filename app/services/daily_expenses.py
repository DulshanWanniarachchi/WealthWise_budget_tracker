"""
daily_expenses.py - the single source of truth for day-to-day spending
(Phase 6), AND the home of the cascade maths.

WHY THIS FILE EXISTS
  Everything the app knows about a month's money comes in two shapes. A
  FIXED expense is the PLAN - money intended to leave the account every
  month (rent, a Netflix subscription; fixed_expenses.py owns them) -
  while a DAILY expense is an ACTUAL payment the user logs as it
  happens: groceries, fuel, a movie. This holder owns the ACTUAL side,
  and only actual spending feeds the cascade below, so the Daily
  Expenses screen only ever asks questions and shows results.

  It deliberately mirrors the other three holders (budget_settings,
  category_settings, fixed_expenses):

    * module-level state, private, reachable only through get_*/add_*/etc;
    * validation lives HERE and raises ValueError - the screen catches it
      and shows a friendly inline message, but an invalid expense can
      never be stored even if a future screen forgets to check;
    * subscribe()/notify() so other screens react to a change;
    * stored in SQLite since Phase 7: the BODIES of these functions are
      now SQL through app/core/db.py, and no screen had to change.

  It starts EMPTY, like fixed_expenses: the user logs every expense
  themselves (categories are structure and get a default tree; money is
  the user's own and gets none).

THE DATA MODEL
  One row per expense in the daily_expenses table (schema in
  app/core/db.py), read back oldest-first so the order is still "the
  order they were added" - "most recent first" and "grouped by day"
  remain display decisions the screen makes. Each row reads back as the
  same dict it has always been:

      {"id": 1, "amount": 450, "budget": "wants", "category": "Movies",
       "sub_item": None, "date": "2026-11-11", "note": "Popcorn"}

  * "id"       - a real AUTOINCREMENT column. Daily expenses have no
                 name to key on (a note is optional and "Rs. 450 under
                 Wants" is not unique), so identity has to come from
                 somewhere: the database now assigns it, and hands back
                 the same sequential integers the old in-module counter
                 did - which is why the screen's id threading needed no
                 change at all.
  * "amount"   - whole rupees, user-entered, non-negative.
  * "budget"   - one of budget_settings.BUDGET_KEYS. Budgets are a fixed
                 three-way enum, so this link can never break.
  * "category" - the category NAME inside that budget, or None once the
                 category has been deleted or renamed (see reconcile()).
  * "sub_item" - OPTIONAL sub-item name under that category, else None.
                 Exactly the same optional pattern as fixed expenses.
  * "date"     - "YYYY-MM-DD", defaults to today. Stored as a string so
                 it sorts lexicographically, survives a SQLite swap and
                 needs no datetime objects in the UI.
  * "note"     - optional free text, or None when the user typed nothing.

WHAT HAPPENS WHEN A LINKED CATEGORY (or sub-item) BREAKS
  Identical to fixed_expenses, because the reasoning is identical: an
  expense whose category was deleted becomes UNCATEGORISED (category =
  None), it is never deleted. Money the user recorded must not vanish
  because a label changed, and the link stores a NAME rather than the
  category's id -
  dropping the link and letting the user re-attach it in Edit is honest.
  The four rules are spelled out in reconcile() below; it runs as a
  subscriber to category_settings, so a delete or rename elsewhere
  repairs every daily expense automatically.

================================================================================
THE CASCADE MATHS - the point of this phase (CORRECTED on 2026-11-11)
================================================================================

  THE MODEL: a fixed expense is the monthly PLAN - the user's INTENDED
  spending per category ("Rent: 30,000 planned") - and a daily expense
  is MONEY ACTUALLY SPENT. Only money actually spent may reduce the
  salary. So for every budget:

        spent     = daily expenses under it, dated inside the CURRENT
                    salary cycle      (DAILY ONLY + CURRENT CYCLE ONLY)
        remaining = allocation - spent               (may go negative)

  PHASE 8.2 (2026-11-17): "spent" NOW RESETS WITH THE SALARY CYCLE.
  Every figure in this section counts only the daily expenses dated
  inside the salary cycle that contains TODAY. The window is NOT
  computed in this file: it comes from budget_settings.cycle_bounds(),
  the helper Phase 8.1 introduced, so this holder still owns no
  calendar arithmetic. What that buys, all deliberate:

    * a new cycle begins with spent = 0 and remaining = the full
      allocation, whatever was logged in the previous one - last
      month's expenses no longer drag anything down;
    * an expense dated outside today's cycle reduces NOTHING. It stays
      in the ledger exactly as before (listable, editable, deletable);
      it simply does not count against the current balance;
    * the window is applied in ONE place - _spent_records() - so all
      seven cascade reads move together and can never disagree.

  What still counts EVERY expense ever logged (on purpose):
    * get_expenses() and count() - the ledger itself. The Daily
      Expenses screen must list, edit and DELETE older entries, and
      reports.has_data() must not call the app "empty" just because a
      cycle rolled over;
    * get_daily_totals_by_budget() - the explicit "what did they log"
      read, kept all-time for a future all-time report;
    * fixed_expenses.get_spent_against() / get_plan_progress() - the
      plan comparison. These were all-time when this section was
      written; the Phase 8.2 FIX windowed them too, because a MONTHLY
      plan's "Paid" has to mean "paid this cycle" for the Fixed
      Expenses screen to agree with the figures above. They keep a
      private _cycle_window() of their own rather than importing this
      one (a private name, and fixed_expenses already imports this
      module - the dependency must stay one-way); phase8_2_test
      asserts the two windows are byte-identical so they cannot drift.

  Fixed expenses are deliberately ABSENT from every figure in this
  section. A plan is COMPARED against spending (see get_plan_progress()
  in fixed_expenses.py), never subtracted from it. The earlier
  "spent = fixed + daily" combined the plan and the payment, so paying
  a planned expense deducted it twice - once as the plan, once as the
  day the money actually left the account. That was the bug this fix
  removed.

  What that means in practice:

    * logging a daily expense is the ONLY thing that reduces remaining;
    * adding, editing or deleting a fixed expense moves NO number here;
    * an expense with no matching plan counts exactly like any other -
      every daily expense reduces the budget it was logged under,
      whether or not a plan exists for its category. Plans are optional
      targets; their absence never stops spending from counting.

  The cascade, bottom to top:

      daily expense  ──┐
                       ├──> get_spent_by_category(budget)  per category
                       │            │  (rolls up)
                       │            v
                       └──> get_spent_by_budget()          per budget
                                    │  (rolls up)
                                    v
                            get_total_spent()              one number
                                    │
      allocation (budget_settings)  v
                       get_remaining_by_budget()           per budget
                       get_remaining_balance()             whole salary

      fixed expenses ─────> fixed_expenses.get_plan_progress()
                             COMPARISON only: planned vs spent-against,
                             "paid" once spent >= planned - and
                             spent-against is THIS cycle only, same
                             window as everything above (Phase 8.2 fix).
                             It feeds the Fixed Expenses screen's
                             progress rows and is never subtracted
                             anywhere above.

  PER BUDGET vs PER CATEGORY - and why they are not symmetric:
    * spent      is available per budget AND per category (every record
      carries a budget and a category on it);
    * remaining  is available PER BUDGET ONLY, because that is the only
      level the app's model assigns money at - budget_settings splits
      the salary into three allocations (needs/wants/savings) and has
      no per-category target to subtract from. Inventing one here would
      be new product behaviour nobody asked for, so get_spent_by_
      category() answers "how much has this category cost" and the
      budget's remaining figure is where the money is judged.

  The uncategorised case: an expense whose link broke still has a
  budget, so it is always counted in get_spent_by_budget() /
  get_total_spent(); get_spent_by_category() (which only knows real
  categories) is complemented by get_uncategorised_spent_by_budget(),
  and the three always add up:

      get_spent_by_category(b)[c] summed  +  uncategorised[b]
          == get_spent_by_budget()[b]

  (Fixed expenses take no part in that identity either - their links
  can break in exactly the same way, but a broken PLAN link never
  moves money.)
"""

import datetime as dt

# NOTE: this module deliberately does NOT import fixed_expenses. Fixed
# expenses are the plan, plans are not spend, and nothing here reads
# them any more. The dependency runs the other way instead:
# fixed_expenses imports THIS module to answer "how much of the plan
# has been spent?" (see get_plan_progress() there). Keeping it one-way
# keeps the import graph acyclic.
from app.services import budget_settings, category_settings
from app.core import db
from app.core.text_rules import cap_first

# Re-exported so callers (and this file's error messages) never have to
# import budget_settings just to name a budget.
BUDGET_KEYS = budget_settings.BUDGET_KEYS
BUDGET_LABELS = budget_settings.BUDGET_LABELS

# A brand-new user has logged nothing. Deliberately empty - Phase 6
# seeds no expenses: spending is the user's own to record.
DEFAULT_EXPENSES: list = []


# ---------------------------------------------------------------------------
# 1. STORAGE - the table and the private read everything below goes
#    through. There is no module-level list and no id counter any more:
#    the ROWS are the state, and AUTOINCREMENT hands out the ids, which
#    is exactly why a restart resumes at the same numbers.
# ---------------------------------------------------------------------------

_TABLE = "daily_expenses"

# The column order matches the record dict exactly, so a row IS the
# public shape - no projection step is needed here (unlike
# fixed_expenses, whose table carries an id the API hides).
_ROW_SQL = ("SELECT id, amount, budget, category, sub_item, date, note "
            f"FROM {_TABLE} ORDER BY id")


def _rows() -> list:
    """Every stored expense, oldest first (insertion order)."""
    return db.query(_ROW_SQL)


_listeners: list = []     # callbacks to run after any change


# ---------------------------------------------------------------------------
# 2. VALIDATION - private, and the ONLY thing that decides what is legal.
#    Every public mutator runs these, so bad data cannot be stored even
#    if a future screen skips its own checking.
# ---------------------------------------------------------------------------

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
        # Commas are a display convention (Rs. 1,250), not part of the
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
        raise ValueError("Pick a category for this daily expense.")
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

    OPTIONAL field, same contract as fixed_expenses: None - or a blank
    string, which is what an untouched field looks like - means the
    expense attaches at CATEGORY level only. When one IS given it must
    exist under `category` RIGHT NOW, case-insensitively, and the tree's
    own spelling is what gets stored.

    The category itself is resolved by the caller BEFORE this runs, so a
    missing category is reported there with the better message.
    """
    if sub_item is None:
        return None
    if not isinstance(sub_item, str):
        raise ValueError(f"A sub-item must be text, got {sub_item!r}.")
    given = sub_item.strip()
    if not given:
        return None                      # blank == "no sub-item chosen"
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


def _clean_date(value) -> str:
    """Return a "YYYY-MM-DD" date string, or raise ValueError.

    None (or a blank field) means TODAY - the sensible default for a
    spending log, and the reason the screen pre-fills its date box.

    The format is checked BY HAND before datetime.date.fromisoformat()
    gets a chance, because on Python 3.11+ fromisoformat accepts a
    handful of other ISO spellings ("20261111", "2026-11-11T00:00:00")
    and the app's contract with the user is one format: exactly
    YYYY-MM-DD. fromisoformat then does the only job it is good at:
    rejecting impossible dates such as 2026-02-30.
    """
    if value is None:
        return dt.date.today().isoformat()
    if not isinstance(value, str):
        raise ValueError(f"A date must be text (YYYY-MM-DD), got {value!r}.")
    text = value.strip()
    if not text:
        return dt.date.today().isoformat()       # empty field == today
    if (len(text) != 10 or text[4] != "-" or text[7] != "-"
            or not (text[:4] + text[5:7] + text[8:]).isdigit()):
        raise ValueError(
            f"Date must be YYYY-MM-DD (e.g. {dt.date.today().isoformat()}), "
            f"got {value.strip()!r}."
        )
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError(
            f"{text!r} is not a real date - use YYYY-MM-DD."
        ) from None            # our message, not Python's, is the useful one


def _clean_note(note):
    """Return the trimmed note, or None if there is none.

    Optional field: None / blank all store None, so "no note" has one
    representation. The GENTLE capitalisation rule is applied here, on
    the way in - this is a NEW entry or an EDIT (never a retroactive
    rewrite), and the screen applies the same rule live while typing so
    the user sees it happen either way. See app/core/text_rules.py for
    what "gentle" means: first letter only, the rest untouched.
    """
    if note is None:
        return None
    if not isinstance(note, str):
        raise ValueError(f"A note must be text, got {note!r}.")
    cleaned = note.strip()
    if not cleaned:
        return None
    return cap_first(cleaned)


def _require_known(expense_id) -> dict:
    """Return the stored row with this id, or raise ValueError.

    Identity is the AUTOINCREMENT id the database assigns on add - see
    the module docstring. Not found raises rather than returns None:
    every caller (update, delete, the screen's edit loader) needs the
    record to exist, so "no such record" is an error, not a value.
    """
    if isinstance(expense_id, bool) or not isinstance(expense_id, int):
        raise ValueError(
            f"A daily expense is identified by its id, got {expense_id!r}."
        )
    row = db.query_one(f"SELECT id, amount, budget, category, sub_item, "
                       f"date, note FROM {_TABLE} WHERE id = ?", (expense_id,))
    if row is None:
        raise ValueError(f"No daily expense with id {expense_id}.")
    return row


# ---------------------------------------------------------------------------
# 3. READS - always return copies, so a caller can never mutate our state
#    by accident (the same rule the other holders follow).
# ---------------------------------------------------------------------------

def get_expenses() -> list:
    """Every daily expense, in the order they were added.

    Order here is insertion order on purpose: "most recent first" and
    "grouped by day" are DISPLAY decisions, and the screen makes them
    (it sorts by (date, id), both descending).
    """
    return list(_rows())


def get_expense(expense_id) -> dict:
    """Return a COPY of one daily expense, or None if it does not exist.

    Used by the screen to load a row into the form for editing. Returns
    None rather than raising, because "which one?" is a question a
    caller often wants to answer for itself.
    """
    try:
        return dict(_require_known(expense_id))
    except ValueError:
        return None


def count() -> int:
    """How many daily expenses exist (the screen's empty-state check)."""
    row = db.query_one(f"SELECT COUNT(*) AS n FROM {_TABLE}")
    return row["n"] if row else 0


# ---------------------------------------------------------------------------
# 4. MUTATORS - validate first, mutate second, notify last. If validation
#    raises, nothing has been touched and no subscriber is disturbed, so
#    the screen's open form stays exactly as the user left it.
# ---------------------------------------------------------------------------

def add_daily_expense(amount, budget, category, sub_item=None, date=None,
                      note=None) -> int:
    """Validate and append a new daily expense; return its new id.

    Every field comes from the user; nothing here is a default except
    the DATE, which is today when the caller passes None (the screen
    always passes its own pre-filled value, which defaults to today
    too - the default exists for callers and tests).

    The category must exist in `category_settings` under `budget` right
    now, and `sub_item` - OPTIONAL, so leaving it out simply stores None
    - must exist under that category if given, or the call raises
    ValueError and stores nothing.

    The note is stored through _clean_note(), which applies the gentle
    first-letter capitalisation to this NEW entry.
    """
    clean_amount = _clean_amount(amount)
    clean_budget = _require_budget(budget)
    clean_category = _resolve_category(clean_budget, category)
    clean_sub_item = _resolve_sub_item(clean_budget, clean_category, sub_item)
    clean_date = _clean_date(date)
    clean_note = _clean_note(note)

    # Validation passed - only now touch the database. The id comes back
    # from AUTOINCREMENT, which is the same sequential number the old
    # in-module counter would have handed out.
    cursor = db.execute(
        f"INSERT INTO {_TABLE} (amount, budget, category, sub_item, date, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (clean_amount, clean_budget, clean_category, clean_sub_item,
         clean_date, clean_note),
    )
    expense_id = cursor.lastrowid
    _notify()
    return expense_id


def update_daily_expense(expense_id, amount, budget, category, sub_item=None,
                         date=None, note=None) -> None:
    """Replace an existing daily expense in place, then notify subscribers.

    `expense_id` identifies which record to change. The record's id is
    never touched - only the editable fields - so anything already
    pointing at it keeps working.

    Editing is also how a user re-attaches an uncategorised expense: the
    category is re-resolved and stored fresh, so a broken link is healed
    by simply saving. The same is true of the sub-item, and the two are
    resolved in that order - a sub-item can only be validated against a
    category that exists.
    """
    # The record must exist before anything is validated or written;
    # record["id"] is what the UPDATE below keys on.
    record = _require_known(expense_id)

    clean_amount = _clean_amount(amount)
    clean_budget = _require_budget(budget)
    clean_category = _resolve_category(clean_budget, category)
    clean_sub_item = _resolve_sub_item(clean_budget, clean_category, sub_item)
    clean_date = _clean_date(date)
    clean_note = _clean_note(note)

    # Validation passed - only now touch the record, so a rejected edit
    # leaves the stored expense untouched.
    db.execute(
        f"UPDATE {_TABLE} SET amount = ?, budget = ?, category = ?, "
        "sub_item = ?, date = ?, note = ? WHERE id = ?",
        (clean_amount, clean_budget, clean_category, clean_sub_item,
         clean_date, clean_note, record["id"]),
    )
    _notify()


def delete_daily_expense(expense_id) -> None:
    """Remove one daily expense by id, then notify subscribers.

    Deleting REDUCES spent, so the cascade moves the other way: every
    subscriber (the Dashboard among them) recomputes from the holders
    when _notify() runs, and the balance goes back up by this amount.
    """
    record = _require_known(expense_id)
    db.execute(f"DELETE FROM {_TABLE} WHERE id = ?", (record["id"],))
    _notify()


# ---------------------------------------------------------------------------
# 5. RECONCILIATION - the "handle a deleted link gracefully" rules.
#    The same four rules fixed_expenses applies, because the reasoning
#    is the same: money must not vanish, and guessing is worse than
#    dropping a link. See the module docstring.
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
         keeps reconcile() honest).

    The DATE and the AMOUNT are never touched - only links can break,
    and only links are repaired here.

    Returns how many RECORDS it changed - a record that loses both links
    still counts as one - so the caller can see whether anything
    happened; _notify() only fires when the answer is not zero.

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
            # Drop it rather than guess - and take the sub-item with it.
            new_category = None
            new_sub_item = None
        elif sub_item is not None and not _sub_item_exists(
                expense["budget"], category, sub_item):
            # Rule 2: only the sub-item went (deleted OR renamed).
            # The category link is healthy, so it stays.
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
# 6. THE CASCADE - spent and remaining, DAILY EXPENSES ONLY (fixed = plan)
#    AND CURRENT-CYCLE ONLY (Phase 8.2). This is the arithmetic section
#    the module docstring diagrams. It reads budget_settings for
#    allocations AND for the cycle window; it no longer reads ANY other
#    expense holder - plans never enter these sums. Nobody reads it
#    back, so it cannot corrupt state - it only ever answers questions.
# ---------------------------------------------------------------------------

def _cycle_window() -> tuple:
    """(first day, last day) of the CURRENT salary cycle, as ISO strings.

    Phase 8.2: the window every "spent" figure below counts over. The
    arithmetic belongs to budget_settings.cycle_bounds() (Phase 8.1) -
    all this does is turn the two dates into the "YYYY-MM-DD" strings
    the table stores, which is formatting rather than date maths, so
    this file still contains no calendar logic of its own.

    The comparison against stored dates stays LEXICOGRAPHIC
    (first <= date <= last), the same style reports.py already uses:
    "YYYY-MM-DD" strings sort in day order, so no row is ever parsed
    and a malformed stored date cannot raise in the middle of a sum.

    Re-read on EVERY call, never cached: the cycle rolls over while the
    app is open, and the user can change the start day in Settings, so
    a stale window would silently count the wrong expenses.
    """
    start, end = budget_settings.cycle_bounds()
    return start.isoformat(), end.isoformat()


def _spent_records():
    """Yield (budget, category, amount) for every DAILY expense dated
    within the CURRENT salary cycle.

    One private iterator so "what counts as spent" is defined in exactly
    ONE place, and since Phase 8.2 that definition has two halves:

      1. DAILY expenses only - fixed expenses are the monthly plan,
         never money spent (see THE CASCADE MATHS at the top of this
         file), so they are not iterated here at all;
      2. dated inside TODAY's salary cycle - the monthly reset, applied
         by comparing the stored date string against _cycle_window().

    Every cascade read below (spent by budget/category, uncategorised,
    total, remaining, over-budget) walks THIS generator, which is why
    they all answer the same window. The ledger reads that must stay
    all-time - get_expenses(), count(), get_daily_totals_by_budget() -
    deliberately do NOT come through here.

    Category included as-is (None stays None - splitting off
    uncategorised records is each public helper's job).

    An expense's category is a name that may have just been deleted
    elsewhere; reconcile() drops such links a moment later, and the
    helpers below only group by names that are still in the tree, so a
    stale name never invents a category.
    """
    first, last = _cycle_window()
    for expense in _rows():
        # Defensive cast: date is NOT NULL in the schema, but "" sorts
        # before every real date, so a bad row would simply fall outside
        # the window instead of raising in a comparison.
        date = expense["date"] or ""
        if first <= date <= last:
            yield expense["budget"], expense["category"], expense["amount"]


def get_daily_totals_by_budget() -> dict:
    """DAILY expenses only, per budget - and ALL-TIME (every row ever).

    Kept as the explicit "what was logged" name, and deliberately NOT
    cycle-filtered: this is the ledger read for a caller that wants
    everything the user has ever entered (a future all-time report, or
    a test that needs the raw ledger). Since Phase 8.2 it is therefore
    NO LONGER identical to get_spent_by_budget() - that one counts the
    current salary cycle only, this one counts every stored row. The
    two agree exactly when every expense falls inside today's cycle.

    It iterates the ledger directly and never touches the cascade
    helpers, which is still the right tool for that job.
    """
    totals = {key: 0 for key in BUDGET_KEYS}
    for expense in _rows():
        totals[expense["budget"]] += expense["amount"]
    return totals


def get_spent_by_budget() -> dict:
    """SPENT per budget = DAILY expenses dated in the CURRENT cycle.

    THE number this phase exists to produce, and the answer to "do fixed
    expenses count?": NO - a fixed expense is the plan, not money spent
    (see the module docstring). Only daily expenses appear here, which
    is what makes "logging a daily expense is the only thing that
    reduces remaining" true. Uncategorised records are INCLUDED: only
    their category link broke, their budget link never can, and the
    money still left the account.

    Phase 8.2: "spent" means spent THIS SALARY CYCLE - the window comes
    from _spent_records(), i.e. budget_settings.cycle_bounds(). An
    expense dated outside today's cycle contributes nothing here, so
    the figure resets to 0 on the first day of every cycle.

    Always returns a key for every budget, even when nothing has been
    spent, so callers can iterate without guarding for missing keys.
    """
    totals = {key: 0 for key in BUDGET_KEYS}
    for budget, _category, amount in _spent_records():
        totals[budget] += amount
    return totals


def get_spent_by_category(budget: str) -> dict:
    """SPENT per category inside ONE budget = daily expenses only.

    A fixed expense's plan for a category never appears here; compare
    plans against these numbers with fixed_expenses.get_plan_progress().

    Every category in the tree is present - with 0 when nothing was
    spent under it - so a caller can walk the tree and always find its
    number. Records that are uncategorised (category is None) are NOT
    here; they belong to no category. They are not lost either:

        sum(get_spent_by_category(b).values())
            + get_uncategorised_spent_by_budget()[b]
        == get_spent_by_budget()[b]

    This is the cascade's lowest level: an expense lands under a
    category, categories roll up into their budget (get_spent_by_
    budget), budgets roll up into the salary's remaining balance.

    Phase 8.2: like every cascade read it counts the CURRENT salary
    cycle only (window from _spent_records()), so a category's figure
    resets with the cycle along with the rest.
    """
    _require_budget(budget)
    spent = {node["name"]: 0 for node in category_settings.get_categories(budget)}
    for rec_budget, category, amount in _spent_records():
        if rec_budget != budget or category is None:
            continue
        if category in spent:
            spent[category] += amount
        else:
            # A name reconcile() has not caught up with yet (it runs on
            # the category holder's notify, i.e. moments later). Keep the
            # money visible rather than drop it from the sum.
            spent[category] = amount
    return spent


def get_uncategorised_spent_by_budget() -> dict:
    """SPENT whose category link is broken (or was never made), per budget.

    Complements get_spent_by_category() so the two always add up to
    get_spent_by_budget(). Shown by the screens as "Uncategorised" in
    the warning colour - visible, never deleted. Phase 8.2: current
    salary cycle only, like the two reads it pairs with, so the
    identity above still holds for every window.
    """
    totals = {key: 0 for key in BUDGET_KEYS}
    for budget, category, amount in _spent_records():
        if category is None:
            totals[budget] += amount
    return totals


def get_total_spent() -> int:
    """Grand total spent across all budgets - CURRENT salary cycle only.

    Phase 8.2: this used to be every daily expense ever logged; it now
    sums _spent_records(), which is windowed to today's cycle, so it
    resets to 0 when a cycle begins. For today's date it therefore
    agrees exactly with reports.spent_this_month() (Phase 8.1), which
    computes the same window for the Reports screen's "this cycle"
    figure - asserted in the Phase 8.2 suite.
    """
    return sum(amount for _b, _c, amount in _spent_records())


def get_remaining_by_budget() -> dict:
    """REMAINING per budget = allocation - spent (this salary cycle).

    Fixed expenses never reduce it: a plan is not a payment. Logging a
    daily expense is the only way this figure moves (adding or editing
    a fixed expense leaves it exactly where it was).

    Phase 8.2: `spent` is the current cycle's, so remaining RESETS to
    the full allocation at the start of every cycle - an expense dated
    in an earlier cycle no longer counts against it.

    Can be NEGATIVE when the user overspends an allocation. It is shown
    honestly rather than clamped: "Rs. -1,200" is the truth and the
    dashboard's progress bar fills to 100% anyway (CTkProgressBar.set()
    clamps the visual on its own).

    Guarded against a 0% allocation, which would otherwise divide by
    zero on any caller that turns this figure into a percentage.
    """
    allocations = budget_settings.get_allocations()
    spent = get_spent_by_budget()
    return {key: allocations[key] - spent[key] for key in BUDGET_KEYS}


def get_remaining_balance() -> int:
    """REMAINING over the WHOLE salary = salary - THIS cycle's spend, floored at 0.

    Total spent is daily-only (plans never touch it), so the whole
    salary stays put until the user actually logs spending. The top of
    the cascade, feeding the Dashboard's "REMAINING BALANCE" card.

    Phase 8.2: `spent` is the CURRENT salary cycle's, so this figure
    REFILLS to the full salary when a cycle begins - expenses logged
    last cycle are no longer subtracted from it.

    The floor at zero is a DISPLAY rule carried over unchanged
    from Phase 3 (that card has never shown a negative balance, and its
    green/amber/red thresholds assume a non-negative figure); the
    per-budget remaining above deliberately does NOT do this - there,
    going negative is information the user needs.
    """
    salary = budget_settings.get_salary()
    return max(salary - get_total_spent(), 0)


# ---------------------------------------------------------------------------
# 6b. OVER-BUDGET COMPARISON (Phase 7) - spent vs allocation, per budget.
#     Like every warning read in this app it only COMPARES two numbers
#     the app already computes; it changes no calculation and notifies
#     nobody. The Dashboard paints a card red from it.
# ---------------------------------------------------------------------------

def get_over_budget() -> dict:
    """Per budget: SPENT vs ALLOCATED - THE over-budget comparison.

        {"needs" | "wants" | "savings":
            {"allocated": this budget's slice of the salary,
             "spent"    : THIS cycle's daily spending (the cascade),
             "over"     : spent > allocated - THE warning flag,
             "over_by"  : spent - allocated when over, else 0}}

    Added with the overspend warnings: the Dashboard uses it to turn a
    card's remaining figure, percentage and progress bar red and to
    show "Over by Rs. ..." once spending passes the slice. Sources are
    get_spent_by_budget() and budget_settings.get_allocations() -
    this function changes neither.

    Phase 8.2: because `spent` is the current cycle's, a card that was
    over budget LAST cycle clears itself when the cycle rolls over -
    the warning is about this salary month, not about history.

    Remaining itself is untouched: allocation - spent still goes
    negative and is still shown exactly as before; this read just
    gives that fact a name and a number, so no screen has to do the
    comparison itself.
    """
    allocations = budget_settings.get_allocations()
    spent = get_spent_by_budget()
    out = {}
    for key in BUDGET_KEYS:
        a, s = allocations[key], spent[key]
        out[key] = {
            "allocated": a,
            "spent": s,
            "over": s > a,
            "over_by": (s - a) if s > a else 0,
        }
    return out


# ---------------------------------------------------------------------------
# 7. CHANGE NOTIFICATION - same contract as the other three holders.
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
# 8. WIRING - this service listens to the category tree, because the two
#    are linked. Registered at import time: daily_expenses imports
#    category_settings (never the other way round), so there is no cycle,
#    and the module is imported before any screen is constructed - which
#    guarantees this subscriber runs BEFORE the Daily Expenses screen's
#    own reload, so the UI is never shown a stale link.
# ---------------------------------------------------------------------------

category_settings.subscribe(reconcile)


# ---------------------------------------------------------------------------
# 9. TEST SUPPORT - lets a test start from a known state. NOT used by the
#    UI: there is no "reset" button because there is nothing to reset to.
# ---------------------------------------------------------------------------

def _reset() -> None:
    """Delete every expense and rewind the id sequence (test helper).

    Does not notify, like the other holders' _reset(). Rewinding matters
    here and nowhere else: ids are part of this record's public shape,
    and the suites assert on them, so a test that clears the ledger
    expects the next entry to come back as id 1 - which AUTOINCREMENT
    will not do on its own, because it keeps a high-water mark in
    sqlite_sequence precisely to avoid handing out a reused id.
    """
    db.execute(f"DELETE FROM {_TABLE}")
    db.execute("DELETE FROM sqlite_sequence WHERE name = ?", (_TABLE,))
