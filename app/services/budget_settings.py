

import datetime as dt

from app.core import db

# ---------------------------------------------------------------------------
# 1. DEFAULTS - what a brand-new user starts with.
# ---------------------------------------------------------------------------

DEFAULT_SALARY = 120_000          # monthly salary in rupees
DEFAULT_PERCENTAGES = {"needs": 50, "wants": 30, "savings": 20}

# the day each salary cycle begins. 1 = calendar months, so a
# user who never touches the setting gets exactly the behaviour the app
# had before this phase. The cap is 28 (not 31) on purpose: every month
# has a 28th, so one setting works for all twelve - a 29/30/31 start
# would silently mean "the last day of February" for one month a year.
# 29-31 are therefore NOT handled differently - they are refused, by
# set_month_start_day() below, with a message that says so.
DEFAULT_MONTH_START_DAY = 1
MONTH_START_DAY_MIN = 1
MONTH_START_DAY_MAX = 28

# The budgets, in the order both screens display them.
BUDGET_KEYS = ("needs", "wants", "savings")

# Display names for those keys, kept NEXT TO the keys so there is one
# canonical spelling. The Categories screen and the category holder's
# error messages read these; a screen may still map its own labels.
BUDGET_LABELS = {"needs": "Needs", "wants": "Wants", "savings": "Savings"}

# Which palette accent identifies each budget, kept with the keys and
# labels so the three "faces" of a budget live in ONE place. It matches
# the Dashboard's budget cards, so "Needs" keeps its colour identity from
# the Dashboard to Categories to Fixed Expenses.
BUDGET_ACCENTS = {"needs": "info", "wants": "warning", "savings": "success"}

# ---------------------------------------------------------------------------
# 2. MODULE STATE - only the subscription list is still held in memory.
#    The settings themselves live in the database now; nothing here is a
#    value the user can change, so there is nothing to persist.
# ---------------------------------------------------------------------------

_listeners: list = []  # callbacks to run after any successful change


# ---------------------------------------------------------------------------
# 3. STORAGE - the SQL statements the accessors share.
# ---------------------------------------------------------------------------

def _write_row(salary: int, needs: int, wants: int, savings: int,
               month_start_day: int) -> None:
    """Store the whole settings row (always the single row, id = 1).

    One statement for salary, percentages AND the month start day so the
    row can never be half-updated: either the new plan is in the database
    or nothing moved. The ON CONFLICT clause means this also works as an
    insert on a database that has no row yet.
    """
    db.execute(
        "INSERT INTO budget_settings "
        "(id, salary, needs, wants, savings, month_start_day) "
        "VALUES (1, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "  salary           = excluded.salary, "
        "  needs            = excluded.needs, "
        "  wants            = excluded.wants, "
        "  savings          = excluded.savings, "
        "  month_start_day  = excluded.month_start_day",
        (salary, needs, wants, savings, month_start_day),
    )


def _read_row():
    """The settings row as a dict, or None if there is no row (yet)."""
    return db.query_one(
        "SELECT salary, needs, wants, savings, month_start_day "
        "FROM budget_settings WHERE id = 1"
    )


def _ensure_row() -> None:
    """Seed the defaults on a database that has never been used.

    Called once, at import time. Two safety properties:

      * it only writes when NO row exists, so re-launching never
        overwrites a salary or percentages the user has set;
      * a failure is swallowed rather than raised - if the file is not
        writable the app still has to start, and every read below falls
        back to the same defaults, so the screens show sensible numbers
        instead of dying on import.
    """
    try:
        if _read_row() is None:
            _write_row(DEFAULT_SALARY,
                       DEFAULT_PERCENTAGES["needs"],
                       DEFAULT_PERCENTAGES["wants"],
                       DEFAULT_PERCENTAGES["savings"],
                       DEFAULT_MONTH_START_DAY)
    except ValueError:
        pass


def _record_cycle_salary(cycle_key: str, salary: int) -> None:
    """Put `salary` on file for the cycle named `cycle_key`.

    THE ONE WRITER of the cycle_salary table - every other function in
    the app only reads it, and no screen knows it exists. An UPSERT:
    the first time a cycle is seen its row is created, a later read in
    the same cycle refreshes that same row, and - the whole point of
    the fix - a cycle that is already history is never touched, because
    both callers below only ever pass cycle_of() (the CURRENT cycle).
    Changing the salary in a new month therefore writes the new
    cycle's row and leaves the old cycle's figure exactly as it was.

    WHY THE KEY IS VALIDATED HERE
      cycle_of() always returns a well-formed "YYYY-MM", so in normal
      use this check never fires; it exists so a caller bug cannot
      poison the table with junk keys that get_salary_for_cycle() would
      then silently fail to look up.

    BEST-EFFORT ON PURPOSE: any failure (a database that cannot be
    written, that malformed key) is swallowed rather than raised,
    because this runs on the READ path too - get_salary() is called on
    every Dashboard repaint, and a history row that failed to record
    must degrade to the documented fallback (get_salary_for_cycle()
    falls back to the current salary) instead of breaking a screen.
    """
    try:
        _parse_cycle_key(cycle_key)
        db.execute(
            "INSERT INTO cycle_salary (cycle_key, salary) VALUES (?, ?) "
            "ON CONFLICT(cycle_key) DO UPDATE SET salary = excluded.salary",
            (cycle_key, salary),
        )
    except ValueError:
        pass


def _stored_salary_for_cycle(cycle_key: str):
    """The salary on file for `cycle_key`, or None when there is no
    USABLE row - the shared reader behind get_salary_for_cycle() and
    has_salary_for_cycle(), so both agree on what "recorded" means.

    None means either "never recorded" (a cycle from before this
    feature) or "recorded value that cannot be a salary" - negative or
    not a whole number, which set_salary() refuses to write, so it can
    only get there by someone editing the database by hand. Same rule
    as get_month_start_day()'s impossible stored value: treat it as
    absent and let the caller fall back, rather than push nonsense
    into a report.

    A malformed cycle_key simply matches no row (SELECT finds nothing)
    and returns None - reading is deliberately forgiving, unlike the
    setters, so a report can never crash on a key.
    """
    row = db.query_one(
        "SELECT salary FROM cycle_salary WHERE cycle_key = ?", (cycle_key,)
    )
    if row is None:
        return None
    salary = row["salary"]
    if not isinstance(salary, int) or isinstance(salary, bool) or salary < 0:
        return None
    return salary


# ---------------------------------------------------------------------------
# 4. ACCESSORS - the API both screens use (and the only way in/out).
# ---------------------------------------------------------------------------

def get_salary() -> int:
    """Return the current monthly salary (rupees, whole number).

    Falls back to DEFAULT_SALARY if the row is missing - the same value
    _ensure_row() would have written, so a degraded read looks exactly
    like a brand-new user rather than showing Rs. 0.

    SIDE EFFECT (Phase 8.3 fix): a normal read also puts the salary on
    file for the cycle containing TODAY (upsert cycle_of() -> the value
    just read). That is how a user who upgrades mid-cycle gets the
    current cycle recorded without ever opening Settings - the first
    Dashboard repaint does it. The value read IS the current salary for
    the current cycle by definition, so recording it is always true,
    and it can only ever write the CURRENT cycle: a read that falls
    back through here for some past cycle still never fabricates a row
    for that past key (see get_salary_for_cycle()). Recording is
    best-effort and never raises - this function sits on the repaint
    path.
    """
    row = _read_row()
    salary = row["salary"] if row else DEFAULT_SALARY
    _record_cycle_salary(cycle_of(), salary)
    return salary


def set_salary(amount: int) -> None:
    """Store a new monthly salary. Raises ValueError if it is not a
    non-negative whole number."""
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
        raise ValueError(f"Salary must be a non-negative whole number, got {amount!r}.")
    pcts = get_percentages()
    _write_row(amount, pcts["needs"], pcts["wants"], pcts["savings"],
               get_month_start_day())
    # Phase 8.3 fix: the new salary belongs to the cycle it takes
    # effect in, so put it on file BEFORE notifying - a subscriber that
    # redraws history the moment settings are saved must see the fresh
    # record. Only the CURRENT cycle is written (cycle_of()); past
    # cycles keep their own rows untouched.
    _record_cycle_salary(cycle_of(), amount)
    _notify()


def get_salary_for_cycle(cycle_key: str) -> int:
    """The salary that was in effect during the cycle `cycle_key`.

    the reader reports.cycle_history() uses so each
    past cycle's saving is measured against ITS OWN salary instead of
    today's. Returns the figure in the cycle_salary table for that key.

    FALLBACK: cycles from before this feature have no row on file (and
    a row wiped by hand behaves the same), so the CURRENT salary is
    returned - the same "missing value looks like a brand-new user"
    rule get_salary() uses, so history stays usable instead of showing
    Rs. 0. Because that fallback is indistinguishable by value alone
    (a recorded salary can legitimately equal today's), callers that
    must be honest about WHICH case they are in - the Reports footnote
    - also ask has_salary_for_cycle().

    READING NEVER WRITES THE QUERIED KEY: only get_salary()'s side
    effect records, and it records cycle_of() (the current cycle), so
    asking about a past cycle can never put a fabricated figure on file
    for it - at most it reinforces the current cycle's own row.
    """
    stored = _stored_salary_for_cycle(cycle_key)
    return get_salary() if stored is None else stored


def has_salary_for_cycle(cycle_key: str) -> bool:
    """True when `cycle_key`'s salary is genuinely ON FILE.

    The honest companion to get_salary_for_cycle(): that function
    always returns a usable figure (falling back to today's salary),
    which makes an unrecorded cycle look exactly like a recorded one
    whose salary happens to match today's. This answers the question
    behind the fallback - "is this that cycle's OWN salary, or today's
    standing in for it?" - so cycle_history() can flag each record
    (record["salary_recorded"]) and the footnote only claims today's
    rate for the cycles where it is true.

    Shares its definition of "recorded" with get_salary_for_cycle() via
    _stored_salary_for_cycle(): a missing row OR a hand-edited
    impossible value both count as not recorded.
    """
    return _stored_salary_for_cycle(cycle_key) is not None


def get_percentages() -> dict:
    """Return {'needs': int, 'wants': int, 'savings': int} as a COPY.

    A copy on purpose: mutating the returned dict must not silently
    change the stored settings. There is nothing behind it to mutate any
    more (the values come straight out of a row), but the contract is
    kept because callers were written against it.
    """
    row = _read_row()
    if row is None:
        return dict(DEFAULT_PERCENTAGES)
    return {key: row[key] for key in BUDGET_KEYS}


def set_percentages(needs: int, wants: int, savings: int) -> None:
    """Store new budget percentages.

    Raises ValueError unless every value is 0-100 AND the three add up
    to exactly 100 (the core rule of the Settings screen).
    """
    values = {"needs": needs, "wants": wants, "savings": savings}
    for name, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
            raise ValueError(f"Percentage for {name!r} must be 0-100, got {value!r}.")
    total = needs + wants + savings
    if total != 100:
        raise ValueError(f"Percentages must total 100, got {total}.")
    _write_row(get_salary(), needs, wants, savings, get_month_start_day())
    _notify()


def get_month_start_day() -> int:
    """The day of the month each salary cycle starts on (1-28).

    Phase 8.1. Falls back to DEFAULT_MONTH_START_DAY (1 = calendar
    months) when the row is missing, exactly like get_salary() falls
    back to the seeded salary - a degraded read looks like a brand-new
    user rather than crashing a screen.

    A stored value outside 1-28 can only get there by someone editing
    the database by hand (set_month_start_day() refuses it), and it is
    treated the same way: fall back to the default instead of letting
    impossible date maths raise inside a report.
    """
    row = _read_row()
    day = row["month_start_day"] if row else None
    if (not isinstance(day, int) or isinstance(day, bool)
            or not MONTH_START_DAY_MIN <= day <= MONTH_START_DAY_MAX):
        return DEFAULT_MONTH_START_DAY
    return day


def set_month_start_day(day: int) -> None:
    """Store the day the salary month begins on. Phase 8.1.

    Raises ValueError unless `day` is a whole number from 1 to 28. The
    cap is deliberate: the 28th exists in EVERY month, so one setting
    always names a real date - a 29/30/31 start would fall off the end
    of February every year. 29-31 are therefore refused rather than
    clamped, so the user is told instead of silently getting 28.
    """
    if not isinstance(day, int) or isinstance(day, bool):
        raise ValueError(f"Month start day must be a whole number, got {day!r}.")
    if not MONTH_START_DAY_MIN <= day <= MONTH_START_DAY_MAX:
        raise ValueError(
            f"Month start day must be {MONTH_START_DAY_MIN}-"
            f"{MONTH_START_DAY_MAX} (every month has that day), got {day}."
        )
    pcts = get_percentages()
    _write_row(get_salary(), pcts["needs"], pcts["wants"], pcts["savings"], day)
    _notify()


def get_total_percentage() -> int:
    """Convenience for the Settings screen's live total row."""
    return sum(get_percentages().values())


def get_allocations() -> dict:
    """Return the allocated amount for every budget:
    salary x percentage / 100.

    Integer division on purpose - rupees are whole numbers here. When
    the salary does not divide evenly the last rupee may be dropped;
    that only affects the display figures (real maths comes later).
    """
    salary = get_salary()
    percentages = get_percentages()
    return {key: salary * percentages[key] // 100 for key in BUDGET_KEYS}


# ---------------------------------------------------------------------------
# 5. SALARY CYCLES - the ONE answer to "which month is this day in?"
#    (Phase 8.1)
#
#    WHY THIS LIVES HERE, IN ONE PLACE
#      Every screen that has ever said "this month" must say the same
#      thing about it. The start day is a SETTING, so the logic built on
#      it sits beside the setting: reports.py, and later the monthly
#      history feature, call these three functions instead of doing date
#      arithmetic of their own. Calendar-month code should no longer
#      exist anywhere outside this section.
#
#    THE SHAPE OF A CYCLE
#      A cycle runs from the start day of one month to the day before
#      the start day of the next. Start day 10, cycle "2026-11" runs
#      10 Nov 2026 -> 9 Dec 2026 (30 days; cycle lengths vary between
#      28 and 31 with the calendar, which is expected).
#
#    THE NAMING RULE - A CYCLE IS NAMED BY THE MONTH IT STARTS IN
#      An expense dated 5 Dec with start day 10 belongs to the cycle
#      that began 10 Nov, so it is "November" - cycle_of() returns
#      "2026-11", never "2026-12". With the default start day of 1 the
#      start month and the containing month are the same month, which is
#      why the default behaves exactly like the old calendar months.
# ---------------------------------------------------------------------------

def _shift_month(year: int, month: int, delta: int) -> tuple:
    """(year, month) moved by `delta` whole months, rolling the year."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _cycle_month(d: dt.date) -> tuple:
    """The (year, month) whose start day contains `d`.

    The whole rule in one line: days ON or AFTER the start day belong
    to THIS month's cycle, days before it belong to the previous
    month's. Start day 1 makes the first branch always true, i.e.
    calendar months.
    """
    if d.day >= get_month_start_day():
        return d.year, d.month
    return _shift_month(d.year, d.month, -1)


def _parse_cycle_key(key: str) -> tuple:
    """Turn a cycle key ("YYYY-MM") into (year, month).

    Raises ValueError on anything else - a cycle key is data this module
    hands out, so a malformed one means a caller bug, and refusing it
    here beats a confusing datetime error deeper down.
    """
    try:
        year_text, month_text = str(key).split("-")
        year, month = int(year_text), int(month_text)
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"Cycle key must look like 'YYYY-MM', got {key!r}.")
    if not 1 <= month <= 12:
        raise ValueError(f"Cycle key month must be 01-12, got {key!r}.")
    return year, month


def cycle_of(d: dt.date = None) -> str:
    """Which salary cycle the day `d` belongs to, as a "YYYY-MM" key.

    `d` defaults to today. THIS IS THE NAMING FUNCTION: the key is the
    month the cycle STARTS in, so with start day 10,

        cycle_of(dt.date(2026, 12, 5))  ->  "2026-11"

    because 5 Dec sits in the cycle that began 10 Nov. Callers that need
    the window itself use cycle_bounds(cycle_of(d)).
    """
    today = d or dt.date.today()
    year, month = _cycle_month(today)
    return f"{year:04d}-{month:02d}"


def cycle_bounds(key: str = None) -> tuple:
    """The (first day, last day) dates of the cycle named `key`.

    `key` is a "YYYY-MM" cycle key from cycle_of(); None means "the
    cycle containing today". Returns two `datetime.date` objects:

        start day 10, cycle_bounds("2026-11")
            -> (date(2026, 11, 10), date(2026, 12, 9))

    The end is the day BEFORE the next cycle starts - the two windows
    are therefore contiguous with no gap and no overlap, which is what
    lets a history screen tile every expense exactly once.

    Raises ValueError for a malformed key (see _parse_cycle_key).
    """
    day = get_month_start_day()
    if key is None:
        year, month = _cycle_month(dt.date.today())
    else:
        year, month = _parse_cycle_key(key)
    start = dt.date(year, month, day)
    next_year, next_month = _shift_month(year, month, 1)
    # -1 day: the cycle ends where the next one begins. day is at most
    # 28, so the next start date always exists and this never needs to
    # care about short months.
    end = dt.date(next_year, next_month, day) - dt.timedelta(days=1)
    return start, end


def cycle_label(key: str = None) -> str:
    """Human name of a cycle, e.g. "November 2026" - for captions.

    `key` is a "YYYY-MM" cycle key from cycle_of(); None means the cycle
    containing today. The label is the START month's name, following the
    naming rule - "November" for the 10 Nov -> 9 Dec cycle.
    """
    if key is None:
        key = cycle_of()
    year, month = _parse_cycle_key(key)
    return dt.date(year, month, 1).strftime("%B %Y")


def cycle_range(key: str = None) -> str:
    """Compact date range of a cycle, e.g. "10 Nov – 9 Dec" - for captions.

    Phase 8.3. The Reports screen's "SPENT IN NOVEMBER" tile names the
    cycle's month, which is ambiguous the moment the start day shifts the
    window: "November" could mean 1-30 Nov or 10 Nov - 9 Dec. This hands
    the caption the exact days instead.

    Built entirely on cycle_bounds(): the two dates it returns are
    FORMATTED here, never computed - day without a leading zero (so it
    reads "9 Dec", not "09 Dec", matching how the app writes dates in
    prose) and the month abbreviated. No date arithmetic lives in this
    function at all.

    No year is printed while both ends share one, because the label
    beside this always carries "Month YYYY" already (cycle_label). When a
    cycle crosses New Year - start day 10 makes the December cycle run
    10 Dec -> 9 Jan - the END gains its year, so "9 Jan" can never be
    misread as January of the wrong year.

    `key` follows the same convention as cycle_label(): a "YYYY-MM" key,
    or None for the cycle containing today.
    """
    start, end = cycle_bounds(key)
    text = f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')}"
    if start.year != end.year:
        text += f" {end.year}"
    return text


# ---------------------------------------------------------------------------
# 6. SUBSCRIPTIONS - the "settings changed" broadcast.
# ---------------------------------------------------------------------------

def subscribe(callback) -> None:
    """Register a zero-argument callback to run after every successful
    set_salary()/set_percentages()/set_month_start_day() call.

    The Dashboard passes its reload method here once, at startup. The
    screen lives as long as the app, so there is nothing to unsubscribe.
    """
    if callback not in _listeners:
        _listeners.append(callback)


def _notify() -> None:
    """Run every subscriber. Called only AFTER a value was stored
    successfully, so listeners always read a valid state."""
    for callback in _listeners:
        callback()


# ---------------------------------------------------------------------------
# 7. STARTUP - seed a brand-new database before anyone reads from it.
# ---------------------------------------------------------------------------

_ensure_row()
