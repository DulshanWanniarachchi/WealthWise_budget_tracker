"""
reports.py - the Reports screen's data layer (Phase 8).

WHAT THIS FILE IS
  Every number the Reports screen draws comes from here. The screen only
  receives plain lists / dicts of already-aggregated values and hands
  them to matplotlib - it never sums, sorts or groups anything itself.

WHY IT LIVES IN app/services/ (not in the screen)
  This is the same discipline the rest of the app uses: validation and
  maths live beside the storage, the screen only presents. It means the
  aggregation can be unit-tested with no window at all, and a future
  screen (an export dialog, a summary on the Dashboard) can reuse these
  exact functions instead of re-deriving them.

READ-ONLY - the most important rule in this file
  Nothing here writes to the database. Every function only calls the
  four existing holders' public READERS:
      budget_settings  - salary, percentages, allocations
      category_settings - the category tree (to name the budgets)
      fixed_expenses   - the monthly PLAN (never spending)
      daily_expenses   - what was actually spent
  Reports therefore cannot change a single rupee of the user's data.

  ONE HONEST FOOTNOTE to that rule (Phase 8.3 fix): budget_settings'
  salary readers now AUTO-RECORD the current cycle's salary into the
  cycle_salary table (see that file for why). So a read that falls
  back through get_salary() may upsert exactly ONE row - the CURRENT
  cycle's, with the salary it already had on file. Money, the ledger,
  the settings row and every past cycle's record stay untouched, and
  reports.py itself still executes no SQL at all.

WHAT "SPENT" MEANS HERE (carried over from the Phase 6 plan fix)
  SPENT = daily expenses ONLY. Fixed expenses are the plan, plans do
  not move money. So "allocated vs spent" compares the budget share
  against real logged spending, and "planned" (fixed) is shown as its
  own third figure - never added to spent.

  Since Phase 8.2 "spent" is also CURRENT-SALARY-CYCLE only: the
  cascade reads below (get_spent_by_budget, get_spent_by_category,
  get_total_spent, ...) already filter to today's cycle inside
  daily_expenses, so nothing needs a window of its own here. The one
  function that does compute a window explicitly is spent_this_month(),
  because it must also answer for a date OTHER than today (its `date`
  argument) - and for today the two agree, which the Phase 8.2 suite
  asserts.

PHASE 8.3 - HISTORY (read-only, and the one reader that looks BACK)
  cycle_history() groups the whole ledger into salary cycles and drops
  the current one, so the Reports screen can show finished months. It is
  deliberately the exception to the current-cycle rule above: history
  must see every cycle, so it groups by cycle_of() itself instead of
  using the windowed cascade reads. It stores nothing itself - since
  the 8.3 fix it READS one more thing, the per-cycle salary table
  budget_settings keeps, so each record's "saved" is measured against
  the salary that was in effect during THAT cycle (with an honest
  fallback for cycles older than the feature - see cycle_history()).

PHASE 8.4 - COMPARE (read-only; history's figures, shown twice)
  compare_cycles(keys) answers the Reports screen's new Compare tab:
  given the cycle keys the user picked, it returns one record per
  cycle - each one cycle_history()'s OWN record plus a per-budget
  breakdown of what was spent inside that cycle. The shared figures
  are copied, never re-derived (a Compare tab that disagreed with
  History about October would be a bug report waiting to happen), and
  the breakdown is grouped with the same cycle_of() discipline history
  uses - no new date arithmetic anywhere in this file.

COLOUR KEYS
  This layer deliberately returns no colours: it returns budget KEYS
  ("needs" / "wants" / "savings") and lets the screen map them through
  budget_settings.BUDGET_ACCENTS -> theme.color(...), exactly like the
  Categories and Fixed Expenses screens already do. That keeps every
  hex value in theme.py and the aggregation in here - each concern in
  its own file.
"""

import datetime as dt

from app.services import (
    budget_settings,
    category_settings,
    daily_expenses,
    fixed_expenses,
)

# Re-exported for the screen's convenience (same trick daily_expenses
# uses) so a caller never needs to import budget_settings separately.
BUDGET_KEYS = budget_settings.BUDGET_KEYS
BUDGET_LABELS = budget_settings.BUDGET_LABELS

# The neutral key used for money that belongs to NO category. Grey
# rather than "warning": warning is already Wants' identity, and a grey
# bar reads as "no category" at a glance in both palettes.
UNCATEGORISED = "Uncategorised"


# ---------------------------------------------------------------------------
# 1. EMPTY-STATE GATE - one answer for "is there anything to report yet?"
# ---------------------------------------------------------------------------

def has_data() -> bool:
    """True once the user has logged at least one daily expense.

    This is the Reports screen's empty-state switch. Only DAILY expenses
    count: a brand-new user has a seeded plan and a seeded category tree,
    but those are not spending - there is genuinely nothing to chart yet,
    which is exactly the state this function detects.
    """
    return daily_expenses.count() > 0


# ---------------------------------------------------------------------------
# 2. THE DONUT - spending split across the three budgets
# ---------------------------------------------------------------------------

def budget_split() -> list:
    """Actual daily spending per budget, for the pie/donut chart.

    Returns one dict per budget, always in BUDGET_KEYS order, with
    zeros kept in so the legend can honestly say "Savings  Rs. 0":

        [{"key": "needs", "label": "Needs", "amount": 1450}, ...]

    The three amounts always add up to daily_expenses.get_total_spent()
    (both current-cycle since Phase 8.2).
    """
    spent = daily_expenses.get_spent_by_budget()
    return [
        {"key": key, "label": BUDGET_LABELS[key], "amount": spent[key]}
        for key in BUDGET_KEYS
    ]


# ---------------------------------------------------------------------------
# 3. THE BAR CHART - spending by category (one budget, or all of them)
# ---------------------------------------------------------------------------

def spending_by_category(budget=None) -> list:
    """Spending per category, largest first, for the bar chart.

    `budget` is a budget key for "just this one", or None for "show all"
    (what the screen sends when the picker is on "All").

    Returns a list of:
        {"name":   the category's own name,
         "label":  what to print under the bar,
         "amount": rupees spent there,
         "budget": the budget key the category belongs to, or None
                   when the money is uncategorised}

    Design decisions worth knowing:

    * ZEROS ARE DROPPED. The tree seeds every category, so a naive read
      would draw six bars of which four are empty - noise, not data.
      A budget where nothing has been spent therefore comes back empty,
      and the screen shows its own "nothing spent here yet" note.

    * "ALL" KEEPS THE BUDGETS SEPARATE. Category names are per-budget
      and the default tree really does contain "Other" in BOTH wants and
      savings, so the names are aggregated per (budget, category) pair -
      never merged across budgets, which would quietly add two different
      categories together. Only when the same name appears in more than
      one budget does the LABEL gain a prefix ("Wants  Other"), so the
      common single-budget case stays clean.

    * UNCATEGORISED IS SHOWN, NOT HIDDEN. Money whose category link has
      broken (or was never set) is real money; it appears as its own
      row so the chart still adds up to get_spent_by_budget().
    """
    if budget is not None:
        keys = (budget,)
    else:
        keys = BUDGET_KEYS

    rows = []
    for key in keys:
        for name, amount in daily_expenses.get_spent_by_category(key).items():
            if amount > 0:
                rows.append({"name": name, "amount": amount, "budget": key})
        if budget is None:
            # Under a single budget the picker already says which one it
            # is, so the uncategorised money needs no budget label.
            unc = daily_expenses.get_uncategorised_spent_by_budget()[key]
            if unc > 0:
                rows.append({"name": UNCATEGORISED, "amount": unc,
                             "budget": None})
        else:
            unc = daily_expenses.get_uncategorised_spent_by_budget()[budget]
            if unc > 0 and not any(r["name"] == UNCATEGORISED for r in rows):
                rows.append({"name": UNCATEGORISED, "amount": unc,
                             "budget": None})

    # Biggest first: a bar chart reads left-to-right, so the eye wants
    # the story in descending order.
    rows.sort(key=lambda row: row["amount"], reverse=True)

    # Disambiguate labels only where a name really does occur twice.
    counts = {}
    for row in rows:
        counts[row["name"]] = counts.get(row["name"], 0) + 1
    for row in rows:
        if counts[row["name"]] > 1 and row["budget"] is not None:
            row["label"] = f"{BUDGET_LABELS[row['budget']]}  {row['name']}"
        else:
            row["label"] = row["name"]
    return rows


# ---------------------------------------------------------------------------
# 4. THE COMPARISON CHART - allocated / planned / actual, per budget
# ---------------------------------------------------------------------------

def planned_vs_actual() -> list:
    """The three money figures every budget has, side by side.

        {"key": ..., "label": ...,
         "allocated": budget share   (salary x percentage),
         "planned":   fixed expenses planned there,
         "spent":     daily expenses logged there}

    Always one dict per budget, in BUDGET_KEYS order, so the chart's
    x-axis and the legend never depend on what the user has typed.

    All three are read from the holders that own them - nothing is
    recalculated here, so this can never disagree with the Dashboard.
    """
    allocations = budget_settings.get_allocations()
    planned = fixed_expenses.get_totals_by_budget()
    spent = daily_expenses.get_spent_by_budget()
    return [
        {
            "key": key,
            "label": BUDGET_LABELS[key],
            "allocated": allocations[key],
            "planned": planned[key],
            "spent": spent[key],
        }
        for key in BUDGET_KEYS
    ]


# ---------------------------------------------------------------------------
# 5. THE STATISTICS - the plain-text numbers beside the charts
# ---------------------------------------------------------------------------

def month_key(date: dt.date = None) -> str:
    """Return the salary-cycle key "YYYY-MM" for the given day (today
    when omitted).

    Phase 8.1: this is NO LONGER necessarily the calendar month. It is
    the cycle the day falls in, answered by
    budget_settings.cycle_of() - the single "which month?" helper - and
    a cycle is named by the month it STARTS in. With the default start
    day of 1 the two answers are identical, so the default behaviour is
    byte-for-byte what it was before this phase.

    Daily expenses store their date as a "YYYY-MM-DD" STRING (Phase 6),
    so the window comparisons below still work by prefix/ordinal string
    order - no date parsing, no chance of a malformed stored date
    raising in the middle of a report.
    """
    return budget_settings.cycle_of(date)


def month_label(date: dt.date = None) -> str:
    """Human name of the salary cycle containing `date`, e.g.
    "November 2026" - for the caption.

    The START month's name, per the cycle naming rule (start day 10 ->
    the 10 Nov-9 Dec cycle is "November 2026").
    """
    return budget_settings.cycle_label(month_key(date))


def spent_this_month(date: dt.date = None) -> int:
    """Rupees spent in the salary cycle containing `date`.

    Scoped to the CURRENT cycle on purpose - that is the figure the
    "Statistics" idea asked for, and it is the one a user can act on.

    Phase 8.2 note: daily_expenses.get_total_spent() is windowed to
    this same current cycle too, so for `date = today` (what the
    dashboard shows) this figure and statistics()["total_spent"] are
    the SAME number - that equality is asserted in the Phase 8.2
    suite. For any OTHER date they differ on purpose: this function
    answers that historical cycle, while the dashboard always answers
    today's.

    Phase 8.1: the window comes from budget_settings.cycle_bounds() -
    the same helper the future history feature will use - instead of the
    calendar month's "%Y-%m" prefix. Start day 1 gives exactly the old
    1st-to-last-day window; start day 10 gives 10th-to-9th.
    """
    start, end = budget_settings.cycle_bounds(month_key(date))
    first, last = start.isoformat(), end.isoformat()
    return sum(
        row["amount"]
        for row in daily_expenses.get_expenses()
        if first <= (row["date"] or "") <= last
    )


def highest_spending_category() -> dict:
    """The single category the most money was logged under.

        {"label": "Subscriptions", "amount": 1100, "budget": "wants"}

    or {"label": None, "amount": 0, "budget": None} when nothing has
    been logged (the screen turns that into an em dash).

    Runs across ALL budgets - "highest-spending category" is a question
    about the whole month, not about one section. Ties resolve to
    whichever the tree walks first, which is stable and predictable.
    """
    best = None
    for key in BUDGET_KEYS:
        for name, amount in daily_expenses.get_spent_by_category(key).items():
            if amount > 0 and (best is None or amount > best["amount"]):
                best = {"label": name, "amount": amount, "budget": key}
    if best is None:
        return {"label": None, "amount": 0, "budget": None}
    return best


def statistics(date: dt.date = None) -> dict:
    """Every text figure the Statistics card shows, in one read.

    One dict so the screen makes exactly ONE pass over the holders and
    can never end up with a highest-category from one moment and a
    total from the next.

    Phase 8.2: "total_spent" and "remaining" come from the cascade and
    are therefore CURRENT-CYCLE figures, matching the Dashboard; only
    "month_total" carries its own window (see spent_this_month), and
    for today the two are equal. "entries" is the ledger's own count
    and stays all-time - it counts records, not money.

    Phase 8.3: "month_range" is the cycle's actual date range ("10 Nov
    – 9 Dec"), formatted by budget_settings.cycle_range() from the same
    cycle key as "month_name" - the two can therefore never name two
    different windows. The screen prints it under the month name so a
    shifted cycle cannot be mistaken for the calendar month.
    """
    cycle = month_key(date)
    total = daily_expenses.get_total_spent()
    remaining = daily_expenses.get_remaining_balance()
    highest = highest_spending_category()
    return {
        "highest_label": highest["label"],
        "highest_amount": highest["amount"],
        "highest_budget": highest["budget"],
        "month_total": spent_this_month(date),
        "month_name": budget_settings.cycle_label(cycle),
        "month_range": budget_settings.cycle_range(cycle),
        "total_spent": total,
        "remaining": remaining,
        "entries": daily_expenses.count(),
        "salary": budget_settings.get_salary(),
        "category_count": sum(
            len(category_settings.get_categories(key)) for key in BUDGET_KEYS
        ),
    }


# ---------------------------------------------------------------------------
# 6. THE HISTORY - one record per finished salary cycle
# ---------------------------------------------------------------------------

def cycle_history() -> list:
    """One record per salary cycle that has at least one expense logged.

    Phase 8.3 - the Reports screen's History tab. NEWEST cycle first:

        {"key":    "2026-09",      the cycle key, from cycle_of()
         "label":  "September 2026",   cycle_label(key)
         "range":  "1 Sep – 30 Sep",   cycle_range(key)
         "spent":  45000,          every expense dated inside that cycle
         "salary": 120000,         THAT cycle's salary, see below
         "saved":  75000,          salary - spent (negative = overspent)
         "salary_recorded": False} True  = the salary above came from the
                                     cycle_salary table (that cycle's
                                     own figure, recorded while it ran);
                                     False = no row on file, so it fell
                                     back to today's salary

    HOW CYCLES ARE FOUND - grouping, not windowing: the ledger is walked
    once, each row's stored "YYYY-MM-DD" date is turned back into a
    datetime.date (reading a date the app itself wrote - never any
    calendar maths) and handed to budget_settings.cycle_of(), the ONE
    "which cycle?" helper. The amounts are summed under that key. Since
    cycle_of() is the same helper the cascade names cycles with, history
    can never disagree with what the rest of the app calls a cycle, and
    because cycle_bounds() windows are contiguous each expense lands in
    exactly ONE record. Sorting the "YYYY-MM" keys backwards gives
    newest-first for free - the strings sort in month order.

    THE CURRENT CYCLE IS EXCLUDED, on purpose: it is still running, so
    it is not history. Its spending is already on the Statistics tiles,
    and a "Saved Rs. X" for a half-finished month would read as a fact
    about a month nobody has finished living yet.

    A malformed stored date (blank, or not ISO) is SKIPPED rather than
    allowed to raise: writing validates dates (see
    daily_expenses._normalise_date), so this is belt-and-braces - a
    report must never crash on one bad row.

    EACH CYCLE'S OWN SALARY (the 8.3 fix - this replaced the old
    "salary limitation" paragraph):
      `salary` comes from budget_settings.get_salary_for_cycle(key) -
      the figure that was ON FILE for that cycle - never from today's
      settings. So if the salary was 200,000 while a cycle ran and is
      150,000 now, that cycle's record still shows its saving against
      200,000, exactly as the acceptance test in the Phase 8.3 suite
      pins down.

      FALLBACK: cycles older than this feature have no row in the
      cycle_salary table (and a hand-ruined row behaves the same), so
      they fall back to the CURRENT salary - what the app can honestly
      know - and are marked salary_recorded = False. The flag is read
      from the table, never inferred by comparing values, because a
      recorded salary can legitimately equal today's; that is what lets
      the History footnote say "these few are measured at today's rate"
      instead of claiming it about every cycle.

      Recording itself lives in budget_settings, not here: set_salary()
      and even a normal get_salary() put the CURRENT cycle on file as a
      side effect, invisibly to every screen. This function only reads.

    READ-ONLY: reads the ledger, today's settings and the per-cycle
    salary table, and writes nothing itself. (The fallback path inside
    get_salary_for_cycle() may reinforce the CURRENT cycle's salary row
    inside budget_settings - never a past cycle's, never any money.)
    """
    current_key = budget_settings.cycle_of()
    totals: dict = {}

    for row in daily_expenses.get_expenses():
        try:
            day = dt.date.fromisoformat(row["date"] or "")
        except ValueError:
            continue                      # unplaceable row - skip, never raise
        key = budget_settings.cycle_of(day)
        totals[key] = totals.get(key, 0) + row["amount"]

    records = []
    # "YYYY-MM" strings sort in time order, so reverse() = newest first.
    for key in sorted(totals, reverse=True):
        if key == current_key:
            continue                      # still open - the stats show it
        spent = totals[key]
        # 8.3 fix: ask the holder for THIS cycle's salary, and whether it
        # is genuinely on file (the flag the footnote branches on). Both
        # calls are readers; neither ever writes this past key.
        recorded = budget_settings.has_salary_for_cycle(key)
        salary = budget_settings.get_salary_for_cycle(key)
        records.append({
            "key": key,
            "label": budget_settings.cycle_label(key),
            "range": budget_settings.cycle_range(key),
            "spent": spent,
            "salary": salary,
            "saved": salary - spent,
            "salary_recorded": recorded,
        })
    return records


# ---------------------------------------------------------------------------
# 6b. THE COMPARISON - history's own figures, two cycles side by side
# ---------------------------------------------------------------------------

def compare_cycles(keys) -> list:
    """One record per requested cycle, in the caller's order (Phase 8.4).

    THE COMPARE TAB'S DATA. `keys` is the list of cycle keys the user
    picked ("2026-10", "2026-09", ...); every key that names a FINISHED
    cycle with spending comes back as that cycle's own cycle_history()
    record with one extra field:

        {"key", "label", "range", "spent", "salary", "saved",
         "salary_recorded",        # copied verbatim from history
         "budgets": {"needs": 12000,   # NEW: what each budget
                      "wants":  8000,   # actually spent inside that
                      "savings": 5000}} # cycle (they add up to spent)

    EVERY SHARED FIGURE IS COPIED, NEVER RECOMPUTED. label, range,
    salary, spent, saved and salary_recorded come straight out of the
    records cycle_history() returns, so the Compare tab and the History
    tab can only ever show the same number for the same month - the
    whole point of the "the two views must not disagree" rule. (The
    record is spread in with **record, so a figure history gains later
    arrives here too, instead of silently going missing.)

    THE PER-BUDGET BREAKDOWN is the one thing history does not compute
    (it only totals a cycle), so this function adds it with ONE more
    pass over the ledger - grouped by budget_settings.cycle_of(), the
    same "which cycle?" helper history groups with, and never a window
    of its own (Phase 8.4's "no new date arithmetic" rule). Because it
    buckets the very rows the total was summed from, adding the three
    buckets always reproduces that record's "spent" - which the Phase
    8.4 suite pins down.

    KEYS THAT NAME NO FINISHED CYCLE ARE SKIPPED: the current cycle
    (still running, so not comparable), a cycle with no spending at
    all, or a typo. The screen only ever offers real history keys, so
    this is belt-and-braces, like the malformed-date skip in history.

    ORDER IS THE CALLER'S, not newest-first: the Compare tab reads its
    two dropdowns left to right, and this list is what puts them on the
    chart in that order. The same key twice simply comes back twice -
    harmless, and it saves the screen from a special case when both
    dropdowns land on the same month.

    READ-ONLY: cycle_history() and the ledger reader do all the work;
    this writes nothing itself (and inherits the one honest footnote
    about get_salary_for_cycle() reinforcing the CURRENT cycle's salary
    row, never a past one - see the module docstring).
    """
    # What history already knows about each requested cycle. One read of
    # history for the whole call - the shared figures can only be as
    # fresh as this single pass.
    known = {record["key"]: record for record in cycle_history()}

    wanted = list(keys) if keys else []
    wanted_set = set(wanted)

    # One grouping pass for the per-budget breakdown: every ledger row
    # whose date lands in a requested cycle is summed under its budget.
    # Same discipline as cycle_history() - parse the stored ISO date the
    # app itself wrote, ask cycle_of() which cycle it belongs to, skip
    # what cannot be parsed rather than raise.
    buckets: dict = {}
    for row in daily_expenses.get_expenses():
        try:
            day = dt.date.fromisoformat(row["date"] or "")
        except ValueError:
            continue                      # unplaceable row - skip, never raise
        key = budget_settings.cycle_of(day)
        if key in wanted_set:
            per_budget = buckets.setdefault(key, {b: 0 for b in BUDGET_KEYS})
            # .get() rather than []: a row with a budget outside the
            # three (which validation prevents) would land beside them
            # instead of crashing a report.
            per_budget[row["budget"]] = per_budget.get(row["budget"], 0) + row["amount"]

    # The empty breakdown a cycle with no rows in this pass would carry.
    # (In practice every history cycle HAS rows, so this is defensive.)
    empty = {b: 0 for b in BUDGET_KEYS}

    records = []
    for key in wanted:
        record = known.get(key)
        if record is None:
            continue                      # current / empty / unknown - skip
        # **record = every figure history computed, copied not reworked;
        # "budgets" is the single addition.
        records.append({
            **record,
            "budgets": dict(buckets.get(key, empty)),
        })
    return records


# ---------------------------------------------------------------------------
# 7. ONE SHOT - what the screen asks for when it draws
# ---------------------------------------------------------------------------

def report(budget=None, date: dt.date = None) -> dict:
    """Everything the Reports screen needs, gathered in one call.

    Grouped so a chart redraw reads the holders a bounded number of
    times per pass instead of once per widget: three matplotlib figures
    are rebuilt on every theme flip and on every resize, and each of
    those passes costs a handful of SELECTs.

    `budget` is the category chart's picker (None = show all).
    """
    return {
        "empty": not has_data(),
        "split": budget_split(),
        "categories": spending_by_category(budget),
        "comparison": planned_vs_actual(),
        "stats": statistics(date),
        # Phase 8.3: finished salary cycles for the History tab. Kept in
        # the bundle so the screen still makes ONE pass over the holders
        # per reload, exactly like every other figure it draws.
        "history": cycle_history(),
    }
