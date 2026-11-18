# Progress checkpoint — Budget Tracker

Last updated: **2026-11-18, after Phase 8.4 (monthly comparison — a read-only
Compare tab pairing two finished salary cycles side by side)**. Prior:
2026-11-18, after Phase 8.3 (monthly history archive +
date-range caption) + its two fixes (the History list's empty area now follows
the display mode; PER-CYCLE SALARY — history measures each past cycle against
its own recorded salary); 2026-11-18, after Phase 8.2 FIX (plan progress uses
the current cycle too); 2026-11-17, after Phase 8.2 (current-cycle spending /
the monthly reset) — note the
renumbering: the overspend-warnings phase previously logged as "Phase 7" is
**Phase 6.5** (corrected at the user's request), and the four in-memory holders
moving onto SQLite is the real Phase 7. Read this
when the user types `resume`. It is the whole state of the project in one page.

Loading this file is **read-only**: summarise where we are, then stop and wait for
the next prompt. No edits, no tests, no exploration until the user asks.

## Where we are

| Phase | Status |
|---|---|
| 1 — skeleton, theme, main.py, screens, db.py | ✅ done (before this log) |
| 2 — Dashboard static UI, hardcoded placeholders | ✅ done |
| 3 — Budget Settings & Allocation (real settings) | ✅ done |
| 4 — Categories & Subcategories (structure only) | ✅ done |
| 5 — fixed (recurring) monthly expenses, in-memory | ✅ done |
| 6 — daily expense entry, cascade maths, real dashboard figures (+ the same-day "fixed = plan" fix) | ✅ done |
| 6.5 — overspend & over-allocation warnings (display-only, three comparison reads) | ✅ done |
| 7 — **SQLite persistence**: all four holders on `data/budget.db`, zero screen changes | ✅ done |
| 8 — **Reports & charts**: read-only `reports.py` aggregation + the sidebar Reports screen (matplotlib donut / bars / comparison / stats) | ✅ done |
| 8.1 — **custom month start day (salary cycle)**: the 1–28 setting, the central cycle helper, the Settings control, Reports' "this month" moved onto it — *no history UI yet* | ✅ done |
| 8.2 — **current-cycle spending (the monthly reset)**: every "spent"/"remaining" figure counts only today's salary cycle, so each salary month resets; the dashboard follows with **zero dashboard code changes** | ✅ done |
| 8.2 fix — **plan progress uses the current cycle too**: `get_spent_against` / `get_plan_progress` windowed the same way, so Fixed Expenses and the Dashboard can no longer disagree about "Paid" | ✅ done |
| 8.3 — **monthly history archive + date-range caption**: `cycle_range()` under the "SPENT IN NOVEMBER" stat, `reports.cycle_history()` (finished cycles, newest first, current excluded, savings at today's salary with an honest footnote), and a third **History** tab — read-only, no new date arithmetic | ✅ done |
| 8.3 fix 2 — **per-cycle salary history (correct savings maths)**: a `cycle_salary` table auto-recorded on every salary set *and* on a normal read, `get_salary_for_cycle()` (current-salary fallback for pre-feature cycles), `cycle_history()` measuring each past cycle against its OWN salary + a `salary_recorded` flag, and a footnote that only claims today's rate for unrecorded cycles | ✅ done |
| 8.4 — **monthly comparison (the Compare tab)**: `reports.compare_cycles()` (history's per-cycle figures copied verbatim + a per-budget breakdown) and a fourth Reports tab — two dropdowns pick any finished cycles, a grouped matplotlib bar chart shows them side by side with a per-cycle salary line; read-only, no new date arithmetic | ✅ done |

Phase 6 built **daily expense entry and the cascade**: an in-memory
`daily_expenses` holder with validation, a fifth sidebar screen (nav key `daily`)
for logging/editing/deleting entries, and the Dashboard's placeholder `SPENT`
figures replaced by real computed ones (`spent = daily only`,
`remaining = allocation − spent` — corrected the same day by the **plan fix**,
see its own section: fixed expenses are the monthly plan and never enter any
figure). `theme.py` gained **no new values**; gentle
auto-capitalisation lives in the new `app/core/text_rules.py`.

**Phase 6.5** (renamed from "Phase 7" on 2026-11-11 — the user corrected the
numbering) added **three display-only warnings** (over-plan rows, plan-exceeds-
allocation per section, over-budget Dashboard cards) with the comparisons in the
holders (`get_plan_progress` state/over_by, `get_plan_vs_allocation`,
`get_over_budget`); no money maths moved and `theme.py` gained no new values —
see its own section below. Its files kept the names they were written under, so
they are still `p7_holder_test.py`, `p7_ui_test.py`, `p7_capture.py`,
`p7_verify.ps1`.

Phase 7 is **SQLite persistence**, now delivered: `budget_settings`,
`category_settings`, `fixed_expenses` and `daily_expenses` read and write
`data/budget.db` through the shared layer in `app/core/db.py`. Every public
function kept its exact name and signature and **not one line changed in any
screen** — see its own section below for the schema, the seeding rules, and why
the expense→category links deliberately stayed names instead of foreign keys.

Phase 8 is **Reports & charts**, now delivered: a new read-only service
`app/services/reports.py` holds every aggregation, and a new sidebar screen
`app/ui/reports_screen.py` draws it with matplotlib — a Needs/Wants/Savings
donut, a horizontal spending-by-category bar chart, a planned-vs-actual
comparison, and four text statistics, all themed light/dark from `theme.py`
(see its own section below). **`theme.py` gained NO new values.** `main.py`
was touched only to register the sixth screen (import, one `screens` entry,
one `nav_items` tuple, the sidebar row renumber that forces, and one docstring
line).

Phase 8.1 is **a custom month start day (the salary cycle)**, now delivered: a
stored day (1–28) in `budget_settings`, the cycle maths in that holder's own
section (`cycle_of` / `cycle_bounds` / `cycle_label` — a cycle is named by the
month it STARTS in), a dropdown on the Settings card, and Reports' "spent this
month" rewired onto it. The monthly-history *screen* is not part of it.
**Neither `main.py` nor `theme.py` changed** — see its own section below.

Phase 8.2 is **current-cycle spending (the monthly reset)**, now delivered: the
cascade in `daily_expenses.py` counts only expenses dated inside today's salary
cycle, so every "spent"/"remaining" figure resets when a cycle rolls over. One
private helper (`_cycle_window()`, a formatter over `budget_settings.
cycle_bounds()`) and one windowed iterator (`_spent_records()`) carry the whole
change — **no new date arithmetic anywhere, and no dashboard code change at
all**. Its **fix** (2026-11-18) then windowed `fixed_expenses`' plan reads too —
a monthly plan's "Paid" must mean "paid this cycle" — so the Fixed Expenses
screen and the Dashboard can no longer disagree; the plan-exceeds-allocation
warning was left alone (planned vs allocated involves no spending).
**Neither `main.py` nor `theme.py` changed** in either — see their own section
below.

Phase 8.3 is **monthly history archive + date-range caption**, now delivered: a
compact date-range line ("10 Nov – 9 Dec") under the cycle's month name on the
Reports stat, `reports.cycle_history()` grouping the whole ledger into finished
salary cycles (newest first, current cycle excluded; savings measured against
each cycle's OWN recorded salary since **fix 2 below** — originally today's,
honestly footnoted), and a third **History**
tab showing one card per finished cycle. **Read-only, no new date arithmetic,
and neither `main.py` nor `theme.py` changed** — see its own section below.

Phase 8.4 is **monthly comparison**, now delivered: `reports.compare_cycles()`
copies `cycle_history()`'s figures verbatim for any list of finished cycle keys
(plus a per-budget breakdown, so *where* spending differed is visible as well as
how much), and a fourth **Compare** tab on the Reports screen pairs two
finished cycles side by side — two dropdowns to pick them, a grouped matplotlib
bar chart, and a salary line quoting each cycle's own rate. **Read-only, no new
date arithmetic, and neither `main.py` nor `theme.py` changed** — see its own
section below.

## Architecture

```
main.py                     app shell, sidebar, show_screen(), theme toggle
                            [screen registration ONLY: Phases 4, 5, 6, 8]
app/core/theme.py           ALL colours/fonts/spacing/radii, LIGHT + DARK dicts,
                            mode state, accessors, palette-sync guard
app/core/db.py              Phase 7: THE shared database layer - file path,
                            one shared connection, PRAGMA foreign_keys, the
                            whole schema, and query()/execute()/meta helpers
                            every holder goes through (get_connection() still
                            hands main.py's probe a FRESH handle to close).
                            Phase 8.1: budget_settings gained its 6th column
                            (month_start_day, DEFAULT 1) + the idempotent
                            _migrate_budget_settings() ALTER for old files.
                            Phase 8.3 fix 2: the cycle_salary table
                            (cycle_key TEXT PK, salary INTEGER) - one row per
                            salary cycle; IF NOT EXISTS IS the whole
                            "migration" (a new TABLE needs no ALTER, unlike
                            the 8.1 column)
app/core/text_rules.py      gentle auto-capitalise: cap_first / bind helper (Phase 6)
app/ui/dashboard_screen.py  Dashboard (real, live figures since Phase 6)
app/ui/settings_screen.py   Budget Settings; Phase 8.1 added the "SALARY MONTH
                            STARTS ON" card (a 1-28 CTkOptionMenu saved by the
                            same Save button)
app/ui/categories_screen.py Categories (Phase 4)
app/ui/fixed_expenses_screen.py Fixed Expenses (Phase 5)
app/ui/daily_expenses_screen.py Daily Expenses (Phase 6)
app/ui/reports_screen.py    Reports (Phase 8): matplotlib donut, category bars,
                            planned-vs-actual comparison + four text statistics;
                            the ONLY file that talks to matplotlib, and it holds
                            no aggregation of its own (Phase 8.1 touched only
                            its comments - the caption text still comes from
                            reports.py's month_name). Phase 8.3: the THIRD tab
                            (History - plain widgets, no figures) and the
                            caption's second line, both fed from reports.py.
                            8.3 fix 2: _apply_history's footnote now BRANCHES
                            on the per-record salary_recorded flag (clean
                            "recorded automatically" text when every cycle's
                            salary is on file; the CURRENT-salary quote only
                            when unrecorded cycles are in the list)
                            Phase 8.4: the FOURTH tab (Compare) - two
                            CTkOptionMenu dropdowns over cycle_history's
                            labels (newest first, defaulting to the two
                            newest), a grouped matplotlib chart (one group
                            per cycle, bars in the budget accents, spent +
                            saved notes above each group), the per-cycle
                            salary line carrying the same honest footnote,
                            and the <2-finished-cycles note; the screen's
                            one new constant COMPARE_NOTE_WRAP lives here,
                            not in theme.py
app/services/budget_settings.py   settings holder, SQLite-backed since Phase 7
                                 + save subscription (owns BUDGET_ACCENTS
                                 since Phase 5). Phase 8.1: the
                                 month_start_day setting (get/set, 1-28,
                                 ValueError on anything else) AND - in its
                                 own section 5 - ALL of the salary-cycle
                                 logic: cycle_of / cycle_bounds / cycle_label.
                                 Phase 8.3: cycle_range() beside cycle_label -
                                 the compact "10 Nov - 9 Dec" caption format,
                                 formatting cycle_bounds() only. No other
                                 module may do month maths.
                                 8.3 fix 2: PER-CYCLE SALARY - the ONLY
                                 writer of cycle_salary
                                 (_record_cycle_salary: UPSERT, auto-fired
                                 from set_salary AND from a normal get_salary
                                 for cycle_of()) plus the readers
                                 get_salary_for_cycle (stored value, falling
                                 back to the current salary for pre-feature
                                 cycles) and has_salary_for_cycle (is a usable
                                 row actually on file?)
app/services/category_settings.py category tree holder, SQLite-backed since
                                 Phase 7 (one `categories` table, parent_id)
app/services/fixed_expenses.py    fixed-expense holder, SQLite-backed since
                                 Phase 7; owns the PLAN reads since the plan
                                 fix: _matches_plan, get_spent_against,
                                 get_plan_progress. Phase 8.2 FIX: those two
                                 now sum _daily_this_cycle() — current-cycle
                                 only, same lexicographic window as the
                                 cascade (its own _cycle_window(), asserted
                                 identical in phase8_2_test). The
                                 plan-exceeds-allocation read (3c) has no
                                 window and was untouched.
app/services/daily_expenses.py    daily-expense holder, SQLite-backed since
                                 Phase 7 + cascade helpers (DAILY-ONLY since
                                 the plan fix — it no longer imports
                                 fixed_expenses). Phase 8.2: the cascade is
                                 also CURRENT-CYCLE-ONLY — _cycle_window()
                                 formats budget_settings.cycle_bounds() into
                                 ISO strings and _spent_records() filters the
                                 ledger with `first <= date <= last`, so all
                                 seven cascade reads move together. Ledger
                                 reads (get_expenses, count,
                                 get_daily_totals_by_budget) stay all-time.
app/services/reports.py     Phase 8: THE read-only aggregation layer. has_data,
                            budget_split, spending_by_category, planned_vs_actual,
                            month_key/month_label/spent_this_month,
                            highest_spending_category, statistics, report. No
                            INSERT/UPDATE/DELETE anywhere — it reads the four
                            holders' public readers and returns plain dicts.
                            Phase 8.1: month_key/month_label/spent_this_month
                            no longer do date maths of their own - they call
                            budget_settings.cycle_of/cycle_bounds/cycle_label,
                            so "this month" IS the salary cycle.
                             Phase 8.2: NO code change here at all — the
                             cascade reads it calls are cycle-filtered now
                             too, so statistics()["month_total"] (its own
                             window) and ["total_spent"] (the cascade's) are
                             the SAME number for today's date.
                             Phase 8.3: cycle_history() (section 6) — one
                             record per FINISHED salary cycle, grouped via
                             cycle_of over the whole ledger, newest first,
                             current cycle excluded — plus
                             statistics()["month_range"] and
                             report()["history"]. The one reader that
                             deliberately looks BACK at every cycle.
                             8.3 fix 2: each record's salary/saved now come
                             from get_salary_for_cycle(key) and carry a new
                             salary_recorded flag (own figure vs the
                             current-salary fallback); still no SQL of its
                             own, still reads the holders' public readers
                             only
                             Phase 8.4: compare_cycles() (section 6b) — given
                             cycle keys, one record per cycle with history's
                             figures copied VERBATIM ({**record}, never
                             recomputed) + the per-budget breakdown; caller's
                             order honoured, current/unknown keys skipped,
                             no dedup, read-only
app/widgets/confirm_dialog.py     shared delete-confirm box (extracted Phase 5)
app/models/                      empty placeholder
data/budget.db              your REAL database, created by the app's first
                            launch (schema + seed rows land the moment
                            app/core/db.py is imported). It already holds real
                            data - salary 200,000; 19 categories; 3 plans;
                            2 expenses - and was last written 2026-11-11,
                            BEFORE Phase 8: every suite runs on a throwaway
                            file through the BUDGET_TRACKER_DB hook, so the
                            battery can never seed over or wipe it.
```

**Data flow:** Settings screen writes → `budget_settings` validates and notifies →
Dashboard's subscriber re-reads and repaints. Categories work the same way:
`categories_screen` writes → `category_settings` validates and notifies → the same
screen's `_reload()` rebuilds its list. Both holders are module-level state with
simple get/set functions, deliberately shaped so a later phase swaps the bodies for
SQLite queries without touching either screen — **that swap is Phase 7 and it is
done**: the functions still look and behave the same, but their bodies are SQL
through `app/core/db.py`. Setters raise `ValueError` as
defence-in-depth; the screen catches it and shows a friendly inline warning.
Fixed and daily expenses follow the identical loop (Phase 5 / 6), and `daily_expenses`
subscribes to `category_settings` for the same reconcile-on-delete dance, while the
Dashboard subscribes to `budget_settings` + `daily_expenses` only (the plan fix
removed its `fixed_expenses` subscription — plans never move a dashboard number).
The Fixed Expenses screen subscribes to all three (its plan bars repaint on daily
spending changes, even while hidden).

## Phase 4 — the category tree

**Choice: a separate sidebar screen**, not a section on Settings. Settings is an
atomic four-field form with one Save button; category management is independent
per-row CRUD that applies immediately. Folding it in would have doubled a 490-line
file and mixed two interaction models behind one Save button.

**Nesting is stored as a uniform node tree** — no privileged case for Subscriptions:

```python
_tree = {"needs": [{"name": "Rent", "items": []}, ...], ...}
# every node has "items" (usually empty); only the API is two levels deep
```

A node's **name is its identity**, which is safe *only* because validation rejects
duplicate names within the same parent (case-insensitive). That uniqueness rule is
what lets rename/delete look nodes up by name instead of an id.

API: `get_structure`, `get_categories`, `count_items`, `get_items`, `add_category`,
`rename_category`, `delete_category`, `add_item`, `rename_item`, `delete_item`,
`subscribe`. Deleting a category cascades to its sub-items (they live inside the
node). Renaming a node to its own name is a deliberate no-op (no notify).
`get_items(budget, category)` was added by the Phase 5 enhancement: the read
counterpart to `count_items` (that one says HOW MANY, this says WHICH), so the
holder and the screen never walk the tree themselves. Raises `ValueError` exactly
like `count_items`.

Seeded defaults (all removable): **Needs** — Rent, Groceries, Meat (Proteins),
Bills (Electricity + Water), Internet (Wifi + Mobile), Transport/Fuel. **Wants** —
Movies, Cosmetics, Shopping + Installment payments, Subscriptions (Google, YouTube,
Spotify/Apple Music, Netflix), Going out. **Savings** — Transfers (Trading etc),
Standing Orders, FD, Money Market/FI.

**Screen mechanics worth remembering:** `_reload()` is the *only* function that
creates row widgets, so `refresh_theme()` = recolour the static chrome + call
`_reload()` — every row is born painted in the active palette and cannot go stale.
A refused change stores nothing → notifies nothing → rebuilds nothing, which is
why the field the user was typing in survives an error untouched.

## Phase 5 — fixed (recurring) expenses

**Choice: a fourth sidebar screen**, nav key `fixed`, label "Fixed Expenses",
appended after Categories. Same reasoning as Phase 4 — Settings is one atomic form
with one Save button, Categories owns the tree, and fixed expenses are a flat CRUD
list of money records that only *point at* that tree. `main.py` gained an import,
one nav tuple, one `screens` entry, and a renumber of the sidebar rows below the
buttons (nav 2-5, spacer 6, appearance 7, switch 8, status 9, padding 10).

**Holder: `app/services/fixed_expenses.py`**, shaped like the other two — in-memory
module state, `ValueError` on every refusal, subscribe/notify, bodies swappable for
SQLite later. Validation lives in the holder, not the screen. Starts **empty** (no
seeded defaults).

API: `add_fixed_expense`, `update_fixed_expense`, `delete_fixed_expense`,
`get_expenses`, `get_expense`, `has`, `get_expenses_for`, `get_total`,
`get_totals_by_budget`, `count`, `reconcile`, `subscribe`, `_reset`.

**How an expense links to a category:** by *name inside a budget*, exactly as the
holder stores it — `{"name", "amount", "budget", "category", "sub_item"}`. The
screen renders the category as a chip. `sub_item` (added by the enhancement below)
is an optional sub-item name **inside that category**; `None` means category-level
attachment, which is the default and still the common case.

**When a linked category is deleted (or renamed) the expense SURVIVES and its
`category` becomes `None`.** It is never removed: money records must not vanish,
there is no database and no undo, and guessing which category a rename meant is
worse than dropping the link. `fixed_expenses` subscribes to `category_settings`
and `reconcile()` clears broken links, notifying only when it actually changed
something. The UI shows a **warning "Uncategorised" chip with no fill**, the row
still counts in its budget total (the budget link never breaks), and Edit → Save
re-attaches it. Since the enhancement, `reconcile()` checks the two links
independently — a broken **sub-item** link only clears `sub_item` and leaves the
category alone (rules below).

**Name is identity** for fixed expenses (global, case-insensitive uniqueness);
`update_fixed_expense(..., ignore=old_name)` allows rename-to-self.

**Form state lives in `ctk.StringVar`s**, not in the widgets: `_reload()` rebuilds
form *and* list on every change (the category dropdown is populated from
`category_settings`, which another screen can change at any moment). Vars outlive
the widgets, so a rebuild never loses typing; the close/restore dance blanks them
before a successful submit and puts them back after a `ValueError`.

**`ConfirmDialog` was extracted** to `app/widgets/confirm_dialog.py` (public, its own
`DIALOG_BUTTON_W=136` / `DIALOG_BUTTON_H=32`); `categories_screen.py` now imports it
instead of defining it. `BUDGET_ACCENTS` moved into `budget_settings.py` and
`categories_screen.py` re-exports it.

**No new `theme.py` values in Phase 5 — nor in the sub-item enhancement** — every
colour, font, spacing and radius the screen uses already existed (the new row
reuses `caption`, `text_secondary`, `surface`, `border`, `xs`, `md`, `sm`). Control
sizes (`FIELD_H`, `BUTTON_W_*`, `BUTTON_H`, `NO_CATEGORIES`, `NO_SUB_ITEM`) stay in
the screen file, per the established rule.

### Chip alignment (fixed on 2026-11-11)

Each expense row is its own frame with its own grid, so grid sized every row's name
column from *that row's* name — and the chip, gridded right after it, drifted with
it. Measured **50px of spread** across four rows (names/amounts/buttons were already
perfectly aligned).

Fix: `_build_list` collects every `(bar, chip_label)` and `_align_name_columns()`
reads the widest chip x in the list, then applies it as `minsize` on column 0 of
every row — the same way a table shares one column width across all rows. The slack
all goes into the **amount** column, so amounts stay hard right against the buttons
however long the names and category tags are. Nothing is clipped: no name can be
wider than the widest name.

Verified at **0px spread** by `p5_geometry.py` at both 1180x820 and the minimum
960x620, *and* by scanning the actual PNG screenshots for the chip fill colour —
all three filled chips sit at x=497 in both palettes.

### Phase 5 enhancement — the optional sub-item (2026-11-11)

A fixed expense may now point at **one sub-item** under its category
(`("wants", "Subscriptions", "Netflix")`), added without breaking anything that
already existed. No database, no `theme.py` changes, `main.py` untouched.

**Holder (`fixed_expenses.py`):** records gained `"sub_item"`; `add_fixed_expense`
and `update_fixed_expense` take an optional 6th argument `sub_item=None`.
Validation lives in the holder: `_resolve_sub_item()` accepts `None`/blank as
"category level", normalises case + whitespace to the tree's own spelling, and
raises `ValueError` (caught by the screen) when the sub-item does not exist under
that category in `category_settings` right now.

**`reconcile()` now runs 4 rules per record, in this order:**

1. category gone (deleted **or** renamed) → `category = None` **and**
   `sub_item = None` — a sub-item cannot outlive its parent. Counts 1 change.
2. category present, sub-item gone (deleted or renamed) → `sub_item = None`,
   **category untouched**. Counts 1 change.
3. both healthy → untouched.
4. already uncategorised → clear `sub_item` if it is somehow set (defensive; the
   mutators never store that pair).

Returns how many **records** moved (a record losing both links still counts once);
`_notify()` still only fires when that is not zero.

**Screen (`fixed_expenses_screen.py`):**

- **Own row, not a fifth control.** Probes (`p5_sub_probe2/3.py`) proved a fifth
  control on the existing row is unusable: grid *compresses* columns below their
  requested width instead of overflowing, crushing name/category to ~34 physical
  px. The picker is gridded on **rows 3/4 spanning columns 0..3** (the four field
  columns, never the button column), directly under the controls.
- **HIDDEN (`grid_remove`), not disabled** — a greyed-out dropdown would still
  claim a row and invite a dead click, and most categories have no sub-items, so
  the card keeps its old height (171 → 275 physical only when shown; verified both
  window sizes, row-2 controls byte-identical hidden vs shown).
- `_sync_sub_item_field()` is the single place that shows/hides; values are always
  `[NO_SUB_ITEM] + options` (`NO_SUB_ITEM = "— None —"`), so attaching at category
  level stays a positive choice.
- New `_on_category_changed()` (the category menu's `command`) re-reads the
  options exactly the way `_on_budget_changed` does; `_on_budget_changed` now ends
  by calling the same sync.
- The pick is **blanked after a successful add** (a sub-item names one specific
  thing) but budget/category stay kept; `_restore_form` puts it back on refusal.
- **List:** one chip reading `Category → Sub-item` (single chip, no alignment
  change — `p5_geometry` still reports 0px spread with mixed lengths).

**Tests:** `p5_holder` **137** (new sections 12-15: add with/without + validation,
edit transitions, the 4 reconcile rules, copied reads), `p5_ui` **15 sections**
(new: hide/show, options refresh, add with/without, edit preselect/change/clear,
holder refusal, `refresh_theme` coverage, end-to-end sub-item delete). New probe
`p5_sub_geom.py` (0 failures), new screenshots `p5_sub_add_dark.png` +
`p5_sub_edit_light.png`.

## Phase 6 — daily expenses & the cascade

**Choice: a fifth sidebar screen**, nav key `daily`, label "Daily Expenses",
appended after Fixed Expenses. A CRUD expense list matches Categories and Fixed
Expenses (one screen each), and a dialog would have fought `CTkToplevel` while
`main.py`'s theme walk only recolours `self.screens`. `main.py` gained exactly:
the `DailyExpensesScreen` import, `("daily", "Daily Expenses")` in `nav_items`,
`self.screens["daily"] = ...`, the dashboard's
`on_add_expense=lambda: self.show_screen("daily")` argument (its existing
"Add Expense" button now switches screens instead of doing nothing), a renumber
of the sidebar rows the fifth button forces (nav **2-6**, spacer **7**,
appearance **8**, switch **9**, status **10**, padding **11**), and a docstring
line listing the nav order. Nothing else.

**Holder: `app/services/daily_expenses.py`** — same shape as the other two:
module-level state, starts **empty** (no seeded defaults), every refusal raises
`ValueError`, notify only on real change, bodies swappable for SQLite later.
Validation lives in the holder, never in the screen. Record fields: `id`
(sequential from `_next_id`, mirroring a future rowid — the record's identity),
`amount` (whole rupees), `budget`, `category` (a name in `category_settings`),
`sub_item` (optional), `date` (ISO, defaults to today), `note` (optional).

API: `add_expense`, `update_expense`, `delete_expense`, `get_expenses`,
`get_expense`, `reconcile`, `subscribe`, `_reset`, plus the cascade helpers
(**all daily-only since the plan fix**):

- `get_spent_by_budget()` — **daily expenses only**; fixed expenses are the plan
  and never enter it (the old "fixed + daily" figure was the double-count bug)
- `get_spent_by_category(budget)` / `get_uncategorised_spent_by_budget()` — daily
  spent **per category**; roll-up identity asserted in tests: the two always sum
  to `get_spent_by_budget()[budget]`
- `get_total_spent()` — every daily expense, all budgets
- `get_remaining_by_budget()` / `get_remaining_balance()` — `allocation − spent`
  with spent daily-only, so **logging a daily expense is the only thing that
  reduces them**; a plan leaves both exactly where they were
- `get_daily_totals_by_budget()` — per-day subtotals for the list headers (same
  answer as `get_spent_by_budget()` now; kept as the explicit "what was logged" name)

**The cascade, stated plainly:** a logged expense adds to its category's daily
spent → its budget's spent → reduces that budget's remaining
(`allocation − spent`) → reduces the balance. **Fixed expenses are the monthly
PLAN, not spend** (corrected by the plan fix, see its section below): they are
*compared* against spending, never subtracted, so there is exactly **one**
`spent` number per budget and the rule is `remaining = allocation − daily`.
**There is no per-category allocation
in the model**, so the per-category helpers return *spent only* — remaining is
defined at the budget level (reported here because the phase asked). Reconcile
follows the fixed-expense pattern verbatim: a deleted or renamed category
(± sub-item) makes the record **uncategorised, never deleted** (same 4 rules,
`sub_item` cleared whenever its parent goes) — for plans a broken link only
stops the *comparison* (an uncategorised plan matches no spending); it never
moves money.

**Dashboard:** the `SPENT` constant is gone. Two subscriptions (`budget_settings`,
`daily_expenses`) repaint the cards, per-budget remaining, progress bars and
the colour thresholds (>50% good, 26–50% warn, ≤25% bad — unchanged) from live
daily-only figures. The old placeholder numbers (21,400 / 10,650 / 3,650 → 84,300 left) are
reproducible as real entries: `p6_dashboard_real.png` shows exactly those,
computed live — and stay exactly right after the plan fix, because that fixture
is all daily expenses.

**Entry UI:** amount, budget, category, **conditional sub-item** (rows 3/4,
`grid_remove`d unless the category has items — same pattern as the Phase 5
enhancement), date defaulting to today (**kept after submit** so back-filling
dates is easy; Clear/Cancel resets it to today), optional note. The list is
grouped **by date, descending** — "Today" / "Yesterday" / full-date headers with
a per-day subtotal, the budget on every row's chip (`Budget → Category →
Sub-item`, uncategorised = warning text with no fill, per the Phase 5 contrast
rule), note truncated at 60 chars. Delete goes through the shared
`ConfirmDialog`. `refresh_theme()` = recolour static chrome + `_reload()` (rows
born painted), same as every other screen.

**Gentle auto-capitalise — new `app/core/text_rules.py`:** `cap_first`
upper-cases the **first letter only** and touches nothing else —
`"netflix" → "Netflix"`, `"FD"` stays, `"Spotify/Apple Music"` untouched, and
`"iPhone" → "IPhone"` (the literal rule: first letter only; documented in the
module and asserted in the tests). `bind_gentle_capitalise` applies it per
keystroke and preserves the caret. Bound live in the daily screen **and** the
fixed screen (their note/name free-text fields) **and** enforced by the holders
themselves (`_clean_note`, `_clean_name`) — so it applies to **new entries only**;
nothing already stored is ever rewritten.

**Buttons moved to their own form row (row 7)** — measured at MIN_SIZE 960x620
in the real shell with `p6_geom.py`. With Clear/Log inline in a fixed fifth
column the four fields had ~467 physical px against ~700 requested: Tk grid
shares a **deficit** proportionally to the weights too, so the weight-2 category
column absorbed double the cut and landed at **82px** while its own text needed
117px (values clipped even for "Transport/Fuel"). With the buttons out of the
row the fields share the full form width (positive excess again): **amount 189 /
budget 189 / category 203 / date 190** physical, note and sub-item full width
813, no control under 60px, chip x spread **0px**, day headings
`Today / 2 expenses / Rs. 1,550` etc., edit outline `border=1 #6366F1` on the
edited row only. Form rows: 0 heading (span 4) | 1 captions | 2 controls |
3/4 sub-item (conditional) | 5/6 note | 7 buttons.
*Observation, out of scope, NOT fixed:* the Fixed Expenses screen has the same
grid maths — its two weight-2 columns sit at ~97px at min size (pre-existing
Phase 5 issue; reported only).

**`theme.py` was NOT touched in Phase 6 — no new values.** Every colour, font,
spacing and radius the screen uses already existed; the LIGHT/DARK import-time
guard still passes.

**Tests:** `p6_holder_test.py` (validation, cascade identities, reconcile,
roll-up identity, **plan reads + the full acceptance scenario**) and
`p6_ui_test.py` (empty state, add/edit/delete, conditional sub-item, date
grouping, refused amount keeps its text, `refresh_theme`
coverage, dashboard wiring, **plan rows showing 0% → 100% / ✓ Paid**) — both ALL
PASSED, and the full battery was re-run green after the plan fix (see below).
`phase3_test.py` now logs real expenses after building the dashboard
(expectations unchanged — they now prove live subscription); `p5_main_test.py`
expects five nav labels and the new sidebar row numbers. Seven screenshots via
`p6_capture.py` → `p6_verify.ps1` (BMP→PNG + pixel statistics), plus three more
via `p6_fix_capture.py` for the plan fix.

## Phase 6 FIX — fixed expenses are the PLAN, not spending (2026-11-11)

**The bug:** the cascade computed `spent = fixed + daily`, so a planned payment
was deducted twice — once as the plan from the moment it was entered, and again
as the day the money was actually logged. Fixed expenses are the user's
INTENDED spending per category; only daily expenses are actual money.

**The corrected model** (all maths in the holders, none in any screen):

- `spent` per budget / per category / total = **daily expenses only**.
  `daily_expenses._spent_records()` iterates the ledger and nothing else, and
  the module no longer imports `fixed_expenses` at all — the dependency runs
  one way (`fixed_expenses → daily_expenses`), keeping the import graph acyclic.
- `remaining = allocation − daily spent` (`get_remaining_by_budget`) and
  `balance = salary − daily spent` (`get_remaining_balance`). **Logging a daily
  expense is the only thing that reduces them**; adding/editing/deleting a plan
  moves no number anywhere. Colour thresholds unchanged, fed by the corrected
  remaining.
- **Plan reads live in `fixed_expenses.py`** (the plan belongs to it):
  `get_spent_against(name)` → int, and `get_plan_progress()` → one dict per plan
  `{name, budget, category, sub_item, planned, spent, progress (0..1 clamped),
  paid (spent ≥ planned)}`. Sum / division / clamp all happen there; the screen
  only paints what it gets. `planned == 0` reports 1.0 / paid (consistent with
  its own `spent >= planned` rule).
- **Matching rule (`fixed_expenses._matches_plan`, the only place it is
  defined):** a daily expense D counts toward plan P iff `D.budget == P.budget`
  AND `D.category == P.category` (casefold — both sides are stored in the
  tree's canonical spelling) AND either (a) P has no sub-item → **every** daily
  expense in that category counts, including ones logged against sub-items, or
  (b) P names a sub-item → only `D.sub_item == P.sub_item` counts (category-level
  daily spend does **not** pay a sub-item plan). A plan whose category link
  broke matches **nothing** (its spent reads 0 until re-attached); the daily
  money itself still counts as spending and still reduces the budget. Expenses
  in categories with no plan are never special-cased — they count like any other.
- **Display choice: the Fixed Expenses screen** (the offered option picked —
  and the "at minimum" requirement). Each expense row gained grid row 1: a
  `CTkProgressBar` spanning columns 0..2 + a **fixed-width** status label in
  column 3 (`✓ Paid` in `success` when covered, else `Rs. spent / Rs. planned`
  in `text_secondary`). Bar fill = `success` when paid, else the budget's
  `BUDGET_ACCENTS` accent; track = `surface`. Why here and not the Dashboard:
  plans are per fixed expense (category / sub-item) while Dashboard cards are
  per budget — the Dashboard would need an aggregation the model never defined,
  and this screen is where plans are managed. The screen gained a **third
  subscription** (`daily_expenses`) so bars repaint on spending changes even
  while hidden; per-row widget refs live in `self._plan_rows` for tests.
- **Dashboard dropped its `fixed_expenses` import and subscription** — plans
  cannot move a dashboard figure, so there is nothing for it to hear from.

**Acceptance test** (asserted in `p6_holder_test.py` §11 and `p6_ui_test.py`
§11): fixed Rent = 30,000 → salary 120,000, spent 0, balance **120,000
unchanged**; log a 30,000 daily expense under Needs→Rent → balance **90,000**
(down by exactly 30,000, once), needs spent 30,000 (not 60,000), and the Rent
plan reports `spent 30,000 / progress 1.0 / paid True` with its row reading
`✓ Paid`. The UI variant runs on a live ledger (before: Rs. 114,750; after the
30,000 entry: exactly Rs. 30,000 less, card +Rs. 30,000, bar 0.0 → 1.0 while
the screen is hidden).

**`main.py` unchanged; `theme.py` gained NO new values** (surface / success /
info / warning / text_secondary / caption fonts all existed). Reconcile
untouched — its tests still pass end to end.

**Screenshots:** `p6_fix_capture.py` → `p6_fix_plan_dark.png` /
`p6_fix_plan_light.png` (Rent PAID 30,000/30,000, Groceries partial
8,000/15,000 = 53%, Netflix unpaid 0/500) and `p6_fix_dash_plan.png` (Dashboard
with all plans present → Rs. 82,000 = 120,000 − 38,000 daily; pre-fix this read
Rs. 36,500). Verified numerically with `p6_fix_verify.ps1` (same converter +
pixel stats as `p6_verify.ps1`, filtered): dark and light show identical
geometry — 7,476 success px, 3,978 info px, 47 warn px (the wants section dot;
a 0%-filled bar shows only track).

## Phase 6.5 — overspend & over-allocation warnings (2026-11-11)

*(`p7_*` file names; renumbered from "Phase 7" on 2026-11-11 when the user
corrected the phase list — this is **not** the SQLite phase.)*

Three **display-only** warning behaviours; every comparison lives in the
holders and **no money calculation changed** (proven read-only in
`p7_holder_test.py` §4: spent / totals / remaining / balance byte-identical
before and after all three reads).

**Files changed:** `app/services/fixed_expenses.py`,
`app/services/daily_expenses.py`, `app/ui/fixed_expenses_screen.py`,
`app/ui/dashboard_screen.py`, plus `PROGRESS.md` and — in Temp — the two p6
assertions whose status format flipped "/" → "of", `run_all.ps1` (+2 suites)
and the new `p7_*` test/capture files. **`main.py` untouched; `theme.py`
untouched (NO new values).**

### The three comparison reads (all holders)

1. **`fixed_expenses.get_plan_progress()` — extended.** Every row now carries
   `state` (`under` / `met` / `over`, decided by spent vs planned HERE, §3b)
   and `over_by` (spent − planned when over, else 0). `paid` stays
   `spent >= planned` ("the plan is covered"); the screen keys off `state`
   only, so an over-plan row can never render as `✓ Paid`. `progress` remains
   clamped to 1.0 — an over bar shows FULL + danger, never >100%.
2. **`fixed_expenses.get_plan_vs_allocation()` — new (§3c).** Per budget:
   `{planned, allocated, exceeds, over_by}` = `get_totals_by_budget()` ×
   `budget_settings.get_allocations()`.
3. **`daily_expenses.get_over_budget()` — new (§6b).** Per budget:
   `{allocated, spent, over, over_by}` = `get_spent_by_budget()` ×
   `get_allocations()`.

### How each warning looks (existing theme keys only — nothing added)

- **Over-plan row (Fixed screen):** TWO stacked danger lines in the fixed-width
  status column — `Rs. 6,000 of Rs. 5,000` over `Over by Rs. 1,000` — plus the
  bar **capped at full and filled `danger`** (chosen over an overflow stub: a
  full red bar plus the exact overrun reads fastest in a fixed-width row).
  Under = `Rs. X of Rs. Y` in `text_secondary` with the budget-accent bar; met
  = `✓ Paid` in `success` with a success bar. Status format switched "/" →
  "of" everywhere (the prompt's example); `PLAN_STATUS_W = 168` comment
  updated, the two-line over block uses the same width so amounts stay aligned.
- **Plan-exceeds-allocation (Fixed sections):** amber `warning` line directly
  under the section header with the spec's exact wording —
  `Planned Rs. 40,000 exceeds the Rs. 24,000 allocated for Savings.` —
  rows shift one grid row down when present; refs in
  `self._allocation_warnings[budget]`. A warning, never a block (the plan row
  stays editable). The Fixed screen gained a **4th subscription**
  (`budget_settings`) so a salary/percentage change re-runs the comparison
  live (asserted: raise salary → warning clears; restore → returns).
- **Over-budget card (Dashboard):** remaining figure (`Rs. -6,000`),
  percentage (keeps the TRUE figure, `110% used`) and the bar all turn
  **danger**; the bar caps at 100% (`min(used,100)/100`, explicit); a
  `Over by Rs. 6,000` caption label appears above the bar — created ungridded
  in `_build`, gridded only while over, forgotten otherwise (healthy cards pay
  no dead space). The salary card's green/amber/red balance logic is untouched
  — this state is added ON TOP. `refresh_theme()` re-reads the stored
  `refs["over_by"]`, so a dark/light flip keeps the red instead of repainting
  it back to normal (asserted for both screens in `p7_ui_test.py`).

**theme.py: NO new values** — `danger` (#DC2626 light / #F87171 dark),
`warning` (#B45309 / #FBBF24) and the `body`/`caption`/`value` fonts already
existed in both palettes; the LIGHT/DARK import-time guard still passes.

**Tests:** `p7_holder_test.py` — **32 checks** (three states + over_by, both
new reads, exact-allocation and exact-spend boundaries, 0% allocation,
zero-plan edge, read-only §4) and `p7_ui_test.py` — **34 checks** (widget-level
acceptance a/b/c + the theme-flip danger guards), both ALL PASSED. The battery
was **16 suites, 0 failing** at this point (Phase 6's two
`"Rs. 0 / Rs. …"` status assertions updated to the "of" format); it is **18**
since Phase 7 added two more.

**Acceptance confirmed:** (a) plan 5,000 / spend 6,000 → row reads
`Rs. 6,000 of Rs. 5,000` + `Over by Rs. 1,000` in danger with a full danger
bar — not a clean `✓ Paid` (p7_holder §1 + p7_ui (a)); (b) 40,000 planned
under Savings vs 24,000 allocated → the amber warning line shows with the
exact wording (p7_holder §2 + p7_ui (b)); (c) needs spent 61,000 > 60,000 →
Dashboard card shows `Rs. -1,000` red, `102% used` red, capped danger bar and
`Over by Rs. 1,000` — not just a percentage (p7_holder §3 + p7_ui (c)).

**Screenshots:** `p7_capture.py` → `p7_verify.ps1` (BMP→PNG + pixel stats):
`p7_warn_fixed_dark.png` shows all three row states (green `✓ Paid`, red
two-line over-plan, amber under) plus the amber section warning in one shot;
`p7_warn_fixed_light.png` the same in light; `p7_warn_dash_over.png` the
Dashboard with Needs 66,000 vs 60,000 (`Rs. -6,000` red, `110% used` red,
`Over by Rs. 6,000`, full red bar; wants/savings untouched, bars all aligned —
the flexible spacer absorbed the extra label row). Pixel counts: fixed dark
8,577 danger + 8,513 success px, dashboard 3,800 danger px; avgLum 43/50 dark
vs 241.6 light. All three PNGs visually inspected.

## Phase 7 — SQLite persistence (2026-11-11)

All four holders moved off Python lists and onto `data/budget.db`. The goal was
"swap storage behind the existing doorways", and it held: **every public
function kept its exact name and signature, and NOT ONE LINE changed in any
screen, in `main.py`, or in `theme.py`.**

**Files changed — the entire phase:** `app/core/db.py` (rewritten: shared
connection + schema + query helpers) and the four holders
`app/services/{budget_settings,category_settings,fixed_expenses,daily_expenses}.py`.
Nothing else. Verified two ways: those five are the only project files written
after this phase began (file timestamps), **and** `phase7_db_test.py` §9 fails
if any file in `app/ui/` mentions `sqlite`, `db.query`, `db.execute` or
`_tree`.

**theme.py: NO new values** — every colour/font/spacing/radius still comes from
the palette dicts; the LIGHT/DARK import-time guard still passes.

### The schema (all `CREATE ... IF NOT EXISTS`, so fresh AND existing databases work)

| table | columns |
|---|---|
| `meta` | `key` TEXT PK, `value` TEXT — one-time decisions, chiefly `categories_seeded` |
| `budget_settings` | `id` INTEGER PK **`CHECK (id = 1)`**, `salary`, `needs`, `wants`, `savings` (NOT NULL) — exactly one row |
| `categories` | `id` INTEGER PK **AUTOINCREMENT**, `budget` TEXT NOT NULL, `parent_id` INTEGER **FK → `categories(id)` ON DELETE CASCADE**, `name` TEXT NOT NULL |
| `fixed_expenses` | `id` INTEGER PK **AUTOINCREMENT**, `name`, `amount`, `budget` (NOT NULL), `category`, `sub_item` (TEXT, `NULL` = broken link) + **UNIQUE `uq_fixed_name ON (name COLLATE NOCASE)`** |
| `daily_expenses` | `id` INTEGER PK **AUTOINCREMENT**, `amount`, `budget` (NOT NULL), `category`, `sub_item`, `date` TEXT `YYYY-MM-DD`, `note` TEXT NULL |

Plus `idx_categories_parent (parent_id)` and `idx_categories_budget (budget, parent_id)`.

**One table holds BOTH levels** of the tree: a sub-item is simply a row whose
`parent_id` points at its category. That mirrors the old "every node has
`items`" model exactly and would accept a third level with no schema change.
`budget` is written on every row (a child repeats its parent's) so `(budget,
name)` resolves a category in a single indexed lookup.

### ID foreign keys, or name-matching? — **names, deliberately**

Categories, sub-items, fixed expenses and daily expenses all got **real INTEGER
auto-increment primary keys** as asked. What was deliberately *not* converted is
the link between an expense and its category: `category` / `sub_item` remain
**TEXT columns holding names** (`NULL` = a broken link).

1. **The requirement settled it.** "The reconcile behaviour (deleted/**renamed**
   category → uncategorise) must still work." An id survives a rename, so an
   id-based FK would make the expense *follow* the category to its new name —
   the exact opposite of uncategorising.
2. **The existing tests assert that behaviour:** `p5_holder_test.py` §8
   ("renamed category also breaks the link") and `p6_holder_test.py` §5 (rule 1
   on a rename). An FK would fail both.
3. **Deleting behaves identically either way, but safer with names:** since no
   FK points at an expense, no cascade can ever reach one. Deleting a category
   removes that row and its sub-items (via `parent_id`'s `ON DELETE CASCADE`),
   while expenses pointing at it **keep their rows and their amounts** with a
   dangling name for `reconcile()` to set to `NULL`. **Money can never be
   cascade-deleted.** (With FKs + `ON DELETE SET NULL` rule 1 would have been
   satisfied by the database — but the rename rule could not have been
   satisfied at all.)

So: **ids for identity inside the tree, names for addressing across holders** —
the same convention `category_settings` has used since Phase 4. Moving to id
FKs later is an isolated change (two columns + `reconcile()`) if renames are
ever meant to follow instead of break.

### Seeding — once, and never again

- **Schema** — created at `db.py` import; an existing file is left alone.
- **`budget_settings`** — `_ensure_row()` writes 120,000 / 50/30/20 **only when
  no row exists**. Every later launch finds the row and does nothing, so a
  typed salary is never overwritten.
- **`categories`** — `_seed_if_new()` writes `DEFAULT_TREE` **only when the
  `meta` flag `categories_seeded` is absent AND the table is empty**, then sets
  the flag unconditionally. The emptiness check gives a new database its tree;
  the *flag* is what stops a user who deleted everything getting the defaults
  back — **empty stays empty**.
- **`fixed_expenses` / `daily_expenses` — never seeded.** They start empty and
  only ever hold what the user typed.
- Since seeding happens once and the holders only add/update/delete rows,
  **re-launching wipes nothing** — asserted in `phase7_db_test.py` §3 and proven
  across a real restart in the decisive test below.

### One layer, two connections (and why that is correct)

- The **shared** connection opens lazily, runs `PRAGMA foreign_keys = ON`
  (SQLite ships with FKs **off** — this is what makes `ON DELETE CASCADE`
  fire), creates the schema once, and serves every `db.query()` /
  `db.execute()`. **No holder ever calls `sqlite3.connect()`** — that is "one
  shared layer, not four connections".
- `get_connection()` still returns a **fresh** handle the caller owns, because
  `main.py` (uneditable) has opened, queried and **closed** it in
  `_probe_database()` since Phase 1. Handing out the shared connection would
  let that probe close it underneath every holder.

### Error rules — SQL must never crash the app

- **Writes raise `ValueError`**, which every screen already catches and shows
  as its inline warning — a failed save reads as an ordinary refusal, not a
  traceback.
- **Reads return `[]` / `None`.** Screens don't guard their reads (the
  Dashboard repaints on every notify), so raising there would take the window
  down; degrading to "no rows" keeps the UI painting.
- A schema-creation failure is swallowed at import so the app still starts.

### Test support — why the suites cannot wreck your data

Every suite calls `_reset()`, which on SQLite would mean **deleting your rows**.
`app/core/db.py` therefore honours an environment variable
**`BUDGET_TRACKER_DB`**, resolved before anything imports the app: `"fresh"`
(what everyone uses) gives that *process* its own throwaway file, a path names a
specific file, unset means the real `data/budget.db`. `run_all.ps1` sets it as a
second line of defence and every Temp suite/capture script sets it itself.
**Result: the battery never writes to it.** After all 20 suites its
`LastWriteTime` is still 2026-11-11 — days before Phase 8 ran.

Holder-side helpers exist for the same reason: `category_settings._reset()`
(restore the default tree) and `_replace_structure()` (swap the whole tree in
one go) — both **silent**, exactly like the `cs._tree = ...` assignments they
replaced, so they cannot trigger `reconcile()`. `daily_expenses._reset()` also
rewinds `sqlite_sequence`, because its ids are public and the suites expect the
next entry to come back as **id 1**.

### Tests & the decisive test

- **`phase7_db_test.py` — 183 checks, 0 failures.** Every table/column/PK/FK
  and the `CHECK (id = 1)`; `PRAGMA foreign_keys` on; one shared connection plus
  the `get_connection()` contract; all the seeding rules; the complete public
  API of all four holders frozen as an explicit allow-list of names + parameter
  lists (any accidental API change fails here, which is *why* no screen needed
  editing); real auto-increment ids; name-links + reconcile (rename →
  uncategorise, delete → uncategorise, money untouched); the unchanged
  validation surface; the error rules; and the no-storage-in-any-screen sweep.
- **`phase7_persist_test.py` — 29 checks, 0 failures — THE decisive test.**
  Writes salary **Rs. 97,500** with 55/25/20, the `Education` category, a
  `Prime Video` sub-item, a **Rs. 2,500 fixed expense** and **three daily
  expenses**; builds the **real app** (`main.BudgetTrackerApp`, which also runs
  `main.py`'s own database probe), reads the Dashboard's actual widgets,
  **destroys the window and closes the database**, then starts a **completely
  fresh interpreter** that rebuilds the app against the same file and compares
  every holder value and every Dashboard figure. All identical:
  salary `Rs. 97,500`, balance `Rs. 94,950`, Needs `Rs. 53,625` allocated /
  `Rs. 1,450` spent / `Rs. 52,175` remaining / `3% used`, Wants `Rs. 1,100`
  spent, Savings `Rs. 19,500` / `Rs. 0` — and the seed flag still `1`, so
  **nothing re-seeded and nothing was wiped**.
- **Full battery: `run_all.ps1` → 18 suites, `SUITES FAILED: 0 / 18`.**

The new suites are named `phase7_*` on purpose — `p7_*` was already taken by
Phase 6.5's warnings work.

## Phase 8 — Reports & charts (2026-11-16)

A new **read-only sidebar screen** that visualises the spending every other
screen has already logged. Nothing writes anything: the charts are a second
*view* over data that Settings / Categories / Fixed / Daily Expenses own.

**Files changed — the entire phase:**

| file | change |
|---|---|
| `app/services/reports.py` | **new** — every aggregation, read-only |
| `app/ui/reports_screen.py` | **new** — the screen; the only file that imports matplotlib |
| `main.py` | register the sixth screen (4 small edits, listed below) |
| `requirements.txt` | **new file** — pins `matplotlib==3.11.2` |
| `app/core/theme.py` | **NOT touched — NO new values** |

### `main.py` — exactly what changed (nothing else)

1. `from app.ui.reports_screen import ReportsScreen` (with a Phase 8 comment).
2. `"reports": ReportsScreen(self.content)` in `self.screens` — **no
   callbacks**, because the screen only ever reads.
3. `nav_items` gained `("reports", "Reports")`, appended **last** so the
   existing order is untouched.
4. The sidebar row map shifted by one for the extra button: nav buttons now
   occupy rows **2–7**, spacer **8** (`weight=1`), appearance caption **9**,
   theme switch **10**, status **11**, bottom padding **12** — comments updated
   to match. Plus the docstring's nav list now ends "Daily Expenses, Reports".

That is all. No behaviour, no colour, no layout logic moved.

### The data layer — `app/services/reports.py`

Read-only by construction: **no `INSERT` / `UPDATE` / `DELETE` anywhere**, and
it reads only the four holders' *public* readers (never their `_rows()` /
`_tree` internals). It returns plain dicts of numbers — **never colours** — so
the screen can paint them from `theme.py`.

| function | feeds |
|---|---|
| `has_data()` / `report(...)` | the empty-state gate |
| `budget_split()` | the donut: three rows in `BUDGET_KEYS` order, always present even at Rs. 0 |
| `spending_by_category(budget\|None)` | the bar chart; `None` = "All"; zeros dropped, sorted descending |
| `planned_vs_actual()` | the comparison: `allocated` (Settings) / `planned` (Fixed) / `spent` (Daily) per budget |
| `month_key()` / `month_label()` / `spent_this_month(date=None)` | the calendar-scoped month figure |
| `highest_spending_category()` | the top-category tile |
| `statistics()` | all four text tiles in one read, so they can never show two different moments |

Rules worth remembering: `budget_split` and `spent` follow the cascade and are
**current-cycle** since Phase 8.2; `statistics()["month_total"]` stays
**calendar-scoped** for the date it is given (the same number as the cascade
today only when the start day is 1). Same-named categories in two
budgets stay **two** rows and get their labels prefixed (`Needs  Other`) only
on collision. Money whose category was deleted/renamed appears as its own grey
**Uncategorised** row (`budget=None`) rather than vanishing — and because
`spending_by_category` already includes that row, the rows alone equal
`get_spent_by_budget()[budget]` (asserted; adding `get_uncategorised_...` on
top double counts).

### The charts — `app/ui/reports_screen.py`

- **Donut** — Needs / Wants / Savings in `info` / `warning` / `success`
  (through `budget_settings.BUDGET_ACCENTS`, so the three budgets wear the
  *same* colours as the Dashboard). Centre reads `Rs. … / spent`. The
  **legend carries the numbers** (`Needs Rs. 53,600 85%`) rather than wedge
  text: the budget accents are dark in LIGHT and bright in DARK, so no single
  palette key contrasts with both — legend text sits on `card_bg` instead.
  matplotlib's `pie()` **skips a zero-size slice**, so an all-zero budget
  simply has no wedge (the legend still lists it at Rs. 0).
- **Category bars — horizontal (`barh`)**, because names are long
  ("Shopping + Installment payments"); the money axis is X, the names are on
  the left, bars sorted biggest-first, value labels at each bar end.
  Uncategorised money is its own grey row.
- **Planned vs actual** — three series per budget: `Allocated` in
  `text_secondary`, `Planned (fixed)` in `accent`, `Spent` in the budget's
  accent, with an `under Rs. X` / `OVER by Rs. X` note above each group in
  `success` / `danger`.
- **Four text statistics** — top category (wears its budget accent), spent
  this month (of Rs. salary), total spent (N expenses logged), total remaining
  (green only when positive, red when not).
- **Layout** — a 4-column grid inside a `CTkScrollableFrame`: row 0 four stat
  tiles, row 1 donut (cols 0–1) + categories (cols 2–3), row 2 comparison
  (spanning 4), row 3 the empty card instead of rows 1–2.

### How the charts pick up the theme (the interesting part)

matplotlib defaults to its own **light** styling, so every element is set
explicitly:

- **`_apply_matplotlib_palette()` runs at the top of every single draw** and
  pushes ~15 `rcParams` from the active palette: figure/axes face, axes edge,
  body text, tick colours, grid, legend face/edge/label, plus `font.family` =
  `theme.FONT_FAMILY` and `font.size` = `theme.FONT_SPECS["caption"]`
  converted px→pt (12 px at 96 dpi → 9 pt).
- Per-data artists (wedges, bars, the over/under notes) then get
  `theme.color(...)` **individually**, because `rcParams` only covers
  matplotlib's own defaults.
- **`refresh_theme()` recolours every widget AND calls `_draw_all()`**, which
  rebuilds all three figures — that is the whole mechanism behind charts that
  follow the dark/light switch. `main.py` calls `refresh_theme()` only on the
  toggle (screens otherwise colour themselves in `__init__`), so this one
  method has to do both jobs.
- Font sizes come from `_pt()` / `_font()` reading `theme.FONT_SPECS`, so the
  charts' text is the same optical size as every label around them.

**No new `theme.py` values.** Chart colours resolve to keys that already
existed in both palettes: `card_bg`, `text`, `text_secondary`, `border`,
`info` / `warning` / `success`, `accent`, `danger`, `success`. The LIGHT/DARK
import-time guard still passes (asserted in `p8_ui_test.py` §9).

### The empty state

With no expenses logged the screen shows **one friendly card instead of three
blank charts**: headline *"No spending to report yet"*, body *"Log an expense
from the Daily Expenses screen and your charts will appear here. Your salary,
budgets and categories are already set up — only the spending is missing."*
The three chart cards are `grid_remove`d (not destroyed), the budget picker is
**disabled** (there is nothing to filter), **no figure is built at all**, and
the four statistic tiles still render with honest zeros / an em dash rather
than disappearing. Log one expense and the cards come back by themselves —
the screen subscribes to all four holders.

### Bugs found and fixed during bring-up

1. **`CTkFrame._draw` collision** — my draw method was named `_draw`, which
   `CTkFrame.__init__` calls as `self._draw(no_color_updates=True)` →
   `TypeError` at construction. Renamed to **`_redraw`** (and `_draw_all` is a
   different name, so it is safe).
2. **The `<Configure>` lambda dropped the event** — `lambda event, k=key:
   self._on_box_resized(k)` passed only the key, and the handler returns
   early when `event is None`, so charts never redrew on map/resize. Now
   forwards it: `self._on_box_resized(k, event)`.
3. **Never guard a redraw on `winfo_ismapped()`** — `ctk.set_appearance_mode()`
   (which `main.py` calls **before** walking the screens) transiently unmaps
   everything, so a "don't draw what nobody can see" guard skipped *exactly*
   the redraw a theme flip needs. `_draw_all()` now always redraws.
4. **Drawing before first layout pins the charts at 140 px** —
   `CTkScrollableFrame` sizes its inner window from the children's
   *requested* heights, so a canvas built while the box was still `1x1` would
   request 240×140 forever and the grid row weights would have nothing left to
   distribute. `_redraw()` now returns early when `box.winfo_width() <= 1`
   (never laid out); once laid out the size sticks even while unmapped, which
   is what lets a theme flip repaint.
5. **`bar` vs `barh`** — the first build used `axes.bar(...)` (vertical) with
   horizontal-chart maths, so `set_xlim(0, max*1.5)` crushed every bar into the
   far-left sliver. Fixed to `barh`. Note `barh(y, width, height=…)`'s second
   *positional* is the bar's length, so `width=0.62` collides with it — the
   thickness kwarg is **`height`**.
6. **`CTkSegmentedButton(dynamic_resizing=False)` clips its labels** — it
   calls `grid_propagate(False)`, freezing the widget at its 140 px default
   and rendering "Needs/Wants/Savings" as "leed/Van/aving". Removed; the value
   list never changes, so sizing to content cannot make the row jump.

### Tests, screenshots, requirements

- **`p8_holder_test.py` — 60 checks.** The empty gate, the donut split, the
  bar chart (single budget, "All", name collisions, uncategorised, zeros
  dropped), planned-vs-actual, statistics incl. calendar scoping, and a
  read-only proof (ledger / balance / plans / settings / tree byte-identical
  after every report call).
- **`p8_ui_test.py` — 95 checks.** Registration + the shifted sidebar rows,
  the empty state, real logged data producing three figures, every chart
  element matching the active palette, the dark↔light flip repainting the
  figures *and* the tick colours, `refresh_theme()` repairing vandalised
  widgets/figures, the picker filtering, the swap back to empty, and the
  structural rule that the screen contains no holder reads, no SQL and no
  hardcoded hex.
- **Battery: `run_all.ps1` → 20 suites, `SUITES FAILED: 0 / 20`.**
- **Screenshots:** `p8_capture.py` → `p8_verify.ps1` (BMP→PNG + pixel stats,
  no Pillow) → `p8_reports_{dark,light}.png` and
  `p8_reports_{empty_dark,empty_light}.png`. Dark vs light counts are nearly
  identical (`dkInfo 25008 ↔ ltInfo 25038`, `dkWarn 1618 ↔ ltWarn 1622`,
  `dkAccent 10953 ↔ ltAccent 10722`) — **the same chart elements in both
  palettes**; avgLum 46.0 dark vs 238.8 light. All four visually inspected.
- **`requirements.txt` is a new file** pinning `matplotlib==3.11.2`.
  **Deviation to note:** Pillow is installed as matplotlib's hard dependency
  but is deliberately **not** listed in `requirements.txt` (only matplotlib is
  pinned) — screenshots go through ctypes `PrintWindow` → BMP → PowerShell
  `System.Drawing` → PNG, so the project itself never touches Pillow.

### Gotchas this phase added

- **A Tk callback can fire after its widget is gone**: driving the forms and
  switching screens in the same tick makes CTk's internal
  `after(… focus_set)` raise `bad window path name …ctkentryN.!entry`.
  **Pre-existing** — `p7_capture.py` hits it too — harmless (the callback dies,
  Tk continues), reported not fixed.
- **`de._reset()` (and the other `_reset()` test hooks) deliberately do NOT
  `_notify()`** — they are silent fixtures. A UI test that empties the ledger
  must use the public `delete_daily_expense(id)` instead, or it is only
  testing its own stale cache.
- **`CTkSegmentedButton.set(value)` does not fire `command`** — only a real
  click does (`from_button_callback=True`). Tests that want the click path
  must pass that flag.

## Phase 8 FIX — Reports layout: filter, stat cards, tabs, donut (2026-11-17)

Four complaints. **Layout, sizing, padding and tab structure only** — no
computed figure, chart datum or statistic moved a rupee, `main.py` was not
touched, and **`theme.py` gained nothing**: every colour, font, spacing and
radius used below was already in it. **Files changed: `app/ui/reports_screen.py`
only.**

### 1. The filter now spans the content width — *even stretch* (the option picked)

Was: the segmented picker sized itself to its labels and sat bunched against
the right edge of its row.

Now: the caption `SHOW CATEGORIES FOR` keeps its own row (left-aligned,
unchanged) and the picker is gridded `sticky="ew"` into a single `weight=1`
column, so it runs edge to edge — **measured `x = 0` and
`right_edge == row width`: 1040 px at 1120×740, 840 px at 960×620.**

**Why even stretch rather than left-align-under-the-caption:** the picker is
the only thing on its row, so left-aligning it would leave a dead gutter on
the right while the four segments stayed at content width — cramped, just
moved. Stretching evenly gives All / Needs / Wants / Savings a quarter of the
row each, which mirrors the four stat cards directly above and makes the two
control bands read as one block.

### 2. Stat cards: `md / sm / md`, 136 px → 157 px tall

The tiles used `sm` above, `xs` between the lines and `xs` below — 12 / 6 / 10
logical of padding around three 28-logical labels, which is what pushed the
text into the border. Now it is **`md / sm / md`**, the same rhythm the chart
cards use: caption `pady=(md, 0)`, value `pady=(sm, 0)`, detail
`pady=(0, md)`.

Measured on the real screen: **card `h = 157`, `req = 157`, `top_gap = 20`,
`bottom_gap = 20`** (physical px), with each of the three labels at its full
35 px — nothing reaches a border, and the row cannot be squeezed because the
strip is gridded `sticky="ew"` and never `nsew`.

The tiles also now live in a **transparent strip frame with four weighted
columns**. Gridding them at screen columns 1–3 left those columns unweighted,
so Tk sized them from content and starved column 0 — the column carrying the
title, subtitle, filter *and* the whole tab view — down to 507 px. Inside the
strip every tile gets an equal share of the full content width.

### 3. Tabs: `CTkTabview`; stats + filter **stay above** the tabs

- `TAB_SPENDING = "Spending"` → the donut (`SPENDING SPLIT`) and the
  `SPENDING BY CATEGORY` bars side by side.
- `TAB_PLAN = "Plan vs Actual"` → the single `ALLOCATED VS SPENT` chart
  across the full width.
- `anchor="w"` so the tab bar starts at the left like a tab bar; the default
  tab is **Spending**, because the donut is the headline chart.
- The scrollable frame is gone. Rows are `0 title | 1 subtitle | 2 stats |
  3 filter | 4 tabview`, and **row 4 is the only weighted row** — so every
  pixel the window loses comes off the charts, never off the header (which is
  423 px tall at both window sizes).

**Where the stat cards and the filter went: they stayed above the tabs.**
Moving them into the Spending tab was evaluated and rejected — they would move
in *with* the donut, so the donut's height would not change by a single pixel,
the Plan vs Actual tab would get busier for nothing, and the picker would
disappear from a tab it never applied to in the first place. Above the tabs
both stay visible in both tabs, and the two tabs are purely about charts.

The chart cards are **permanent children of their tab frames**, gridded once in
`_build_charts()`; `_apply_state()` only toggles the tab view against the empty
panel with `grid_remove()`. It never moves a card, so a card keeps its size
across tab switches and theme flips.

### 4. The donut: a bigger box, a measured hole, a label that cannot crowd the ring

All three changes are sizing:

1. **The box gets the whole tab band.** With the scrollable frame gone, the
   donut's box is **475 × 319 px at 1120×740** and **375 × 169 px at the
   960×620 minimum**, and it belongs to the charts alone.
2. **The centre text is sized from the hole, in pixels.**
   `radius_px = min(pos.width*width, pos.height*height) / span` where
   `pos = axes.get_position()` — that call *forces* `apply_aspect()`, the only
   way to get the shrunken square box before the draw — and
   `span = axes.get_xlim()[1] - axes.get_xlim()[0]` = 2.5 (matplotlib's own
   `pie()` limits). Cross-checked against matplotlib's transform *after* the
   draw: **95.7 vs 95.7** at default and **40.5 vs 40.5** at minimum. The text
   block therefore lands centred in the ring (offset +4 px / +2 px, which is
   the block's own asymmetry).
3. **A fit guard with no size floor.** `reserve = min(spacing("sm"),
   hole*0.125)`, `room = hole - 2*reserve`,
   `money_px = min(theme amount size, room / (len*0.5))`, and
   `spent_px = min(theme caption size, money_px)` so the word is never larger
   than the number it labels. The fraction is the point: a fixed `sm` (20 px)
   is a comfortable sixth of the 134 px default hole but over a third of the
   57 px minimum hole, where it starves the headline for nothing. There is
   deliberately **no minimum size** — a floor puts the digits back into the
   ring, which is the very bug this replaced.

**Confirmed:** at 1120×740 the hole is **134 px** and `Rs. 63,200` renders at
**98 × 19 px** → **18 px clear on each side**, at full theme size with nothing
scaled. At the 960×620 minimum the hole is **56.7 px** and the label scales to
**41 × 9 px** → **8 px clear each side**: it fits, smaller, because the window
is 150 px shorter and the header is fixed.

The legend is unchanged on purpose: it measures **244 × 74 px at `ncol=1`**,
while `ncol=2` needs 487 px and `ncol=3` needs 723 px — both wider than the
475 / 375 px boxes — so three stacked rows is the only layout that fits, and
its band is reserved by `max(0.24, min(0.4, 66/height))`.

### Tests & screenshots after the fix

- **`p8_ui_test.py` → 103 checks (was 95), all pass.** Rebuilt for the tabs: it
  now opens the Reports screen itself (a `pack_forget()`ed screen is 1×1, so no
  box ever gets a `<Configure>` and no figure is ever built), asserts the
  Spending cards are mapped while the Plan card waits on its own tab, visits
  both tabs so all three figures exist, and proves the dark→light flip repaints
  the Plan tab's figure too.
- **`p8_holder_test.py` → 60 checks, all pass** — untouched, it references none
  of `_content`, `_tabs`, `_figures` or the scroll frame.
- **Battery `run_all.ps1` → `SUITES FAILED: 0 / 20`.**
- **8 screenshots**, BMP → PNG + pixel stats (no Pillow):
  `p8_reports_{empty_dark,dark,plan_dark,default_dark,min_dark,light,plan_light,empty_light}.png`.
  Dark avgLum 29.7–45.6, light 237.0–241.9; `dkInfo dkWarn dkSuccess dkAccent`
  appear in every dark shot and `ltInfo ltWarn ltSuccess ltAccent` in every
  light shot — **both palettes, both tabs**, all inspected by eye.

### Gotchas the fix added

- **`Axes.get_position()` is not a plain read** — it calls `apply_aspect()`
  first, which is what shrinks the subplots rectangle to the square an
  equal-aspect ring needs. Read it *before* `draw()` and you get the real box;
  matplotlib's own docstring says so.
- **A `wedge.get_path()` vertex probe measures nothing useful** for a ring (it
  reports ring = 1.00, hole = 0). Read `wedge.width` — it is literally the
  value `wedgeprops["width"]` was handed.
- **Weighting only the screen's column 0 is a trap** for anything gridded at
  columns 1–3: those columns are unweighted, so Tk sizes them from content and
  starves column 0. Any new band needs its own strip with its own weights.
- **Never guard a redraw on `winfo_ismapped()`.** `main.py` calls
  `refresh_theme()` only on a toggle, and CTk's `set_appearance_mode()`
  transiently unmaps everything first — the guard would skip exactly the
  redraw the flip exists to cause.
- **A hidden tab's box reports `winfo_width() == 1`** until it is visited.
  `_redraw()` returns early on that, and that is correct: visiting the tab is
  what produces its first `<Configure>` and therefore its real size. Once
  drawn, the size sticks while unmapped, so `refresh_theme()` still repaints
  the figure at the right size.

## Phase 8 FIX 2 — Reports grid lines too prominent in light mode (2026-11-17)

Styling only: **no chart data, no statistic, no layout and no line width
changed.** Files changed: `app/core/theme.py` (one new key) and
`app/ui/reports_screen.py` (two call sites).

### The diagnosis

Both bar charts drew their grid with `theme.color("border")`. A border is the
right colour for **one** outline — but repeated eight times across a plot it
reads as hard rules rather than a guide. Measured off the rendered PNGs:

| | grid colour | contrast vs its card |
|---|---|---|
| light mode | `#E2E5EB` on `#FFFFFF` | **1.262:1** ← the complaint |
| dark mode | `#2A2E37` on `#1C1F26` | 1.213:1 ← already fine |

So only light needed to move. (For scale: the near-universal `#EEEEEE`
chart grid on white is 1.161:1, and `surface` in light mode is 1.161:1 too —
so 1.262:1 really was a shade too heavy for a repeated line.)

### What changed

1. **New theme key `grid`, added to BOTH palettes** — the import-time guard
   `set(LIGHT) == set(DARK)` fails the app if only one side gets it:
   - **LIGHT `"grid": "#EDEFF4"` → 1.150:1** on the white card. A hair
     fainter than the `#EEEEEE` most charts use; still a line you can count
     a bar against, not a cage.
   - **DARK `"grid": "#2A2E37"` → 1.213:1** — deliberately *identical to this
     palette's `border`*, because dark already read correctly. The key exists
     on the dark side so the screen can ask for `"grid"` exactly once and let
     each mode answer with the value that is right for it.
   Rejected: reusing `surface` (light 1.161 is only a hair better, but dark
   `#23262E` would be 1.090:1 and the dark grid would vanish) and `bg`
   (light 1.090 is right, but dark `#121317` is *darker* than the card, which
   would flip dark mode's grid into a shadow line).

2. **`app/ui/reports_screen.py`, two sites, both now `theme.color("grid")`:**
   - `rcParams["grid.color"]` in `_apply_matplotlib_palette()` (the belt for
     any `axes.grid()` called without a colour),
   - `axes.grid(axis=..., color=..., linewidth=0.8)` in `_style_axes()` — the
     one that actually paints the line.
   `linewidth=0.8` is **kept**: the line was too *colourful*, not too thick,
   and holding the width means the two bar charts stay identical in both modes.

3. **Everything else stays on `border`** — figure edge, axes edge, spines,
   legend edge. Those are single outlines, which is exactly what that colour
   is for. The 360 px of `#E2E5EB` still present in the light category chart
   is the y-axis spine, and it should be there.

### Measured after, off the real screenshots

| chart | before | after |
|---|---|---|
| light comparison grid | `#E2E5EB` 1.262:1 | `#EDEFF4` **1.150:1** |
| light category grid | `#E2E5EB` 1.262:1 | `#EDEFF4` **1.150:1** |
| dark comparison grid | `#2A2E37` 1.213:1 | `#2A2E37` **1.213:1** (unchanged) |
| dark category grid | `#2A2E37` 1.213:1 | `#2A2E37` **1.213:1** (unchanged) |

**Styling only, proven numerically:** the light comparison chart's grid
occupies **exactly 4949 px before and after** — only the colour moved, not a
single line's position or length. The donut has no grid at all
(`axes.axis("off")`), so the two bar charts are the whole story.

**Theme flip:** `_style_axes()` runs on every draw, and `refresh_theme()`
ends in `_draw_all()`, so toggling repaints the grid along with everything
else. Asserted in the test (the line drawn *after* the toggle is compared
against the one captured *before* it, and must differ).

### Tests & screenshots

- **`p8_ui_test.py` → 116 checks (was 103), all pass** — 13 new grid checks:
  rcParams uses the new key; the key exists in both palettes; light grid is
  fainter than light border yet still ≥ 1.10:1; dark grid unchanged and still
  ≥ 1.10:1; the **drawn grid line artists** on both bar charts (rcParams can
  say one thing while the explicit `color=` says another); light's grid is a
  genuinely different value from light's border; and after the dark→light flip
  both rcParams and both charts' drawn lines followed.
- **`p8_holder_test.py` unchanged, `ALL PASSED`.**
- **Battery `run_all.ps1` → `SUITES FAILED: 0 / 20`.**
- **8 screenshots re-captured** (`p8_capture.py` + `p8_verify.ps1`): dark
  avgLum 29.7–45.6 with `dkInfo dkWarn dkSuccess dkAccent` present in every
  dark shot, light avgLum 237.0–241.9 with `ltInfo ltWarn ltSuccess ltAccent`
  in every light shot — both palettes, both tabs.

### Gotchas the fix added

- **The "screen hardcodes no colour" test greps the SOURCE for
  `#[0-9A-Fa-f]{6}`.** A comment that quotes the hex values fails it. Keep
  hex literals out of comments inside `app/ui/`.
- **Grid and axis spine legitimately share a colour**, so pixel-counting a
  plot area reports both in one bucket. Tell them apart by run length: the
  spine is one long line, the grid is many short ones.

## Phase 8 FIX 3 — the "grid lines" were segmented-button dividers (2026-11-17)

### The complaint

A second look at the same screen: *"the grid lines are still showing …
the change was needed for visible grid lines dividing the two buttons,
'Spending', 'Plan vs Actual' and the category buttons above them."*

So the lines being pointed at were **never** the matplotlib grid. They
were the 1 px vertical strokes between the values of the two segmented
controls on this screen:

| control | widget | the strokes |
| --- | --- | --- |
| budget filter | `CTkSegmentedButton` (`screen._picker`) | `All\|Needs`, `Needs\|Wants`, `Wants\|Savings` |
| tab bar | `CTkTabview._segmented_button` | `Spending\|Plan vs Actual` |

The FIX 2 matplotlib change stays — it was in the original brief and it
is a measured improvement — but it was not what the user was pointing
at, which is why it looked like a no-op.

### The diagnosis

Nobody draws that line. A `CTkSegmentedButton` is **not one widget**:
it is a ROW of separate `CTkButton`s, each with its own Tk canvas. Tk
paints a canvas's *background* wherever the widget's rounded rectangle
does not reach — and that includes the single pixel column where two
neighbouring canvases meet. The stroke is the **seam**.

And that background was never ours:

- The segments are built inside `CTkSegmentedButton.__init__`, before
  this screen ever passes `fg_color`, so `CTkBaseClass` seeds them via
  `_detect_color_of_master()` from CustomTkinter's **stock** theme
  (`CTkSegmentedButton.fg_color` = `#979DA2` light / `gray29` dark).
- `CTkSegmentedButton.configure(fg_color=…)` propagates **only
  `border_color`** to the segments, never `bg_color`
  (`ctk_segmented_button.py` L249–253).

Two independent measurements confirmed it exactly:

| screenshot | seam before | why |
| --- | --- | --- |
| light (captured after a dark→light toggle) | `#1C1F26` | stale **dark** `card_bg` |
| dark | `#4A4A4A` | Tk `gray29` = CTk's stock dark entry |

The live start-path probe (`p8_divider_probe.py`) reproduced all three
cases: light-from-birth `#979DA2`, dark-from-birth `gray29`,
dark→toggle-light `#1C1F26`.

### What changed — `app/ui/reports_screen.py` only

**No `theme.py` change: no new key was needed.** The seam has to match
the bar's own `fg_color`, and that is already `card_bg`.

1. `import tkinter as tk`.
2. A new private helper **`_paint_segment_seams(control)`**, called from
   `refresh_theme()` twice — straight after the picker's `configure()`
   and straight after the tab view's `configure()`, so `fg_color` is
   already the new palette when the helper reads it back.

The helper finds the bar (the control *is* the bar, or a
`CTkSegmentedButton` sits one level inside it), reads
`bar.cget("fg_color")`, and pushes that into every segment with
`segment.configure(bg_color=colour)`. `CTkBaseClass.configure` sets
`_bg_color` **and** calls `_draw()`, which repaints the canvas — so the
fix survives every later repaint, hover, resize and theme flip.

**Why `tk.Frame.winfo_children()` and not `control.winfo_children()`:**
`CTkTabview` *overrides* `winfo_children()` and deliberately strips its
segmented button out of the list, because it considers the bar part of
itself rather than a child. The unbound call returns Tk's real child
list, so the helper still touches **no private attribute** — no
`_buttons_dict`, no `_segmented_button`, no `_canvas`.

### Measured after, off the real screenshots

| seam | light before | light after | dark before | dark after |
| --- | --- | --- | --- | --- |
| `All\|Needs` | `#1C1F26` on white | flat `#FFFFFF` | `#4A4A4A` | flat `#1C1F26` |
| `Needs\|Wants` | `#1C1F26` | flat `#FFFFFF` | `#4A4A4A` | flat `#1C1F26` |
| `Wants\|Savings` | `#1C1F26` | flat `#FFFFFF` | `#4A4A4A` | flat `#1C1F26` |
| `Spending\|Plan vs Actual` | `#B1B2B4` | flat `#FFFFFF` | (grey) | flat `#1C1F26` |

Every gap is now one flat run of the bar's own colour: no stroke at any
seam, in either palette, on either control. Segment geometry is
untouched — the transitions still land on the same x (619 / 921 / 1222
in the filter, 464 in the tab bar), only the pixels *inside* the gap
changed.

### Tests & screenshots

- **`p8_ui_test.py` → 125 checks (was 116), all pass** — 9 new seam
  checks: both controls in three states (dark as the app starts, light
  after the dark→light flip, dark after flipping back), plus the
  vandalise/repair contract (paint a segment's canvas magenta and let
  `refresh_theme()` put `card_bg` back on both controls).
- **`p8_divider_probe.py`** — the 3-scenario start-path probe now
  reports `#FFFFFF` / `#1C1F26` for every segment in every scenario.
- **`p8_holder_test.py` unchanged, `ALL PASSED`.**
- **Battery `run_all.ps1` → `SUITES FAILED: 0 / 20`.**
- **8 screenshots re-captured** (`p8_capture.py` + `p8_verify.ps1`).

### Gotchas the fix added

- **`CTkFrame.winfo_children()` and `CTkTabview.winfo_children()` are
  overrides**, not Tk's. Both silently REMOVE their own internal canvas
  (the tab view also removes its segmented button). Anything hunting
  for a widget *inside* a CTk container must call
  `tkinter.Frame.winfo_children(widget)` unbound, or it will never see
  it — the tab bar was invisible to the first version of this fix.
- **`fg_color` and `bg_color` are not linked after construction.**
  Reconfiguring `fg_color` repaints the fill and the border but leaves
  `bg_color` — and therefore the canvas background — exactly where it
  was. Any CTk control whose look depends on both needs both set.

## Phase 8.1 — custom month start day (salary cycle) (2026-11-17)

**One setting, one helper, no history UI yet.** The user's salary month does not
have to be a calendar month: a stored day (1–28) says when each cycle begins, and
every "this month" figure in the app is now answered from that one place. The
monthly-history *screen* is explicitly **not** part of this phase.

### The setting — where it lives

- **`app/services/budget_settings.py`** (the holder) owns it:
  `DEFAULT_MONTH_START_DAY = 1`, `MONTH_START_DAY_MIN = 1`,
  `MONTH_START_DAY_MAX = 28`, `get_month_start_day()`, `set_month_start_day(day)`.
- Stored in the **same single `budget_settings` row** (id = 1) as salary and the
  three percentages — `_write_row` / `_read_row` now carry five values, and
  `set_salary` / `set_percentages` re-read the day before writing so none of the
  three can clobber another.
- `set_month_start_day()` **raises `ValueError`** for anything that is not a whole
  number in 1–28, and subscribes/notifies exactly like the other setters (the
  Dashboard's reload runs on a day change too).
- A corrupt stored value (hand-edited DB) makes the *getter* fall back to 1 rather
  than raising inside a report.

**29–31 are REFUSED, not clamped.** The cap is 28 because every month has a 28th;
a 29/30/31 start would silently mean "the last day of February" once a year. The
user gets `ValueError` with a message that says the range, and the Settings screen
shows the same 1–28 warning inline before any write.

### The cycle logic — one place only

Section 5 of `budget_settings.py` (sections renumbered: 6 = subscriptions,
7 = startup). It sits beside the setting it reads, so `reports.py` and the future
history feature import the holder rather than inverting the layering.

| helper | answers |
|---|---|
| `cycle_of(d) -> "YYYY-MM"` | which cycle the day `d` belongs to |
| `cycle_bounds(key) -> (start, end)` | first/last `date` of a cycle (`None` = today's) |
| `cycle_label(key) -> "November 2026"` | human name, for captions |
| `_shift_month` / `_cycle_month` / `_parse_cycle_key` | private plumbing |

- A cycle runs **start day → the day before the next start day** (start day 10,
  cycle `2026-11` = 10 Nov → 9 Dec). Windows are contiguous: no gap, no overlap,
  so a future history screen can tile every expense exactly once.
- **A cycle is NAMED BY THE MONTH IT STARTS IN.** `cycle_of(5 Dec 2026)` with start
  day 10 returns `2026-11`, and `cycle_label` says **"November 2026"** — because 5
  Dec sits in the cycle that began 10 Nov.
- Malformed keys (`"nonsense"`, `"2026-13"`, `42`) raise `ValueError` — a cycle key
  is data this module hands out, so a bad one is a caller bug.

### The database — `app/core/db.py`

- Schema: `month_start_day INTEGER NOT NULL DEFAULT 1` added to `budget_settings`.
- **`_migrate_budget_settings(connection)`** — `CREATE TABLE IF NOT EXISTS` cannot
  add a column to a table that already exists, so a Phase-7-era file needs one
  `ALTER`. Guarded by a `PRAGMA table_info` check (runs **at most once**, a second
  open is a no-op), called from `_ensure_schema()` before `commit()`. `DEFAULT 1`
  backfills every existing row with the old behaviour.

### The UI — `app/ui/settings_screen.py`

- New **"SALARY MONTH STARTS ON"** card at grid row 4 (message → row 5, save →
  row 6; row comment updated). Caption + helper line on the left
  ("The day your salary month begins - spending is grouped into months starting
  from this day."), a `CTkOptionMenu` of `"1"`…`"28"` pinned right.
- **Dropdown, not a text field:** the menu cannot offer an illegal value.
  `width=100, dynamic_resizing=False` so the box never changes size between 1
  and 28 (layout sizes, same precedent as the 200/70/140 inputs — not theme
  values). Same palette as every other control in the form.
- Saved by the **existing Save button** — the screen stays one atomic form. The
  day is parsed and range-checked *before* any write (a refusal cannot leave a
  half-saved form), then `set_month_start_day()` enforces the same rule again.
- `_reload_from_fields()` does `menu.set(str(day))` (there is no text cursor);
  `refresh_theme()` recolours card, caption, helper and all eight menu colours.
- Module docstring and the RULES list updated.

### Reports — the exact changes (`app/services/reports.py`)

| function | before | after |
|---|---|---|
| `month_key` | `today.strftime("%Y-%m")` | `budget_settings.cycle_of(date)` |
| `month_label` | `today.strftime("%B %Y")` | `budget_settings.cycle_label(month_key(date))` |
| `spent_this_month` | `row["date"].startswith(prefix)` | window compare against `cycle_bounds(...)` ISO strings |

`statistics()` and `report()` are **unchanged in shape** — they call these three, so
the Reports screen's caption (`SPENT IN NOVEMBER 2026`) and its four tiles follow
the cycle automatically. `app/ui/reports_screen.py` got **comments/docstring only**
(the caption line now says "salary cycle").

**Nowhere else in the app computes a month.** Grepped: `daily_expenses*` use
`date.today()` only as the *per-day* default for a new entry and for the
Today/Yesterday list grouping; `dashboard_screen.py` uses `datetime.now()` only for
the header greeting. Those are day-level and untouched.

### What did NOT change

- **`main.py` — untouched.** (`grep` for `cycle|month_start|salary` → no matches.)
- **`theme.py` — zero new values.** LIGHT and DARK still have identical key sets;
  the new card uses existing `surface`, `border`, `card_bg`, `text`,
  `text_secondary`, `accent_soft`, `body`, `caption`, `sm`/`md`/`lg`.

### Tests & screenshots

- **`phase8_1_test.py` — 7 sections, ALL PASSED**: the setting (default, both
  boundaries, 7 refusals, notify, persistence across a connection close, same-row
  proof, setters not clobbering each other) · the cycle logic (naming rule,
  boundaries, contiguity across three cycles, year rollover, leap-year February at
  start day 1, malformed keys, default-1 == calendar) · reports rewiring
  (`month_key`/`month_label`/`spent_this_month`/`statistics()` by cycle, and the
  default-1 answers) · a **Phase-7-shaped database** opened in a subprocess
  (salary 97,500 preserved, column added, value writable, migration idempotent) ·
  the Settings UI (28 values, Save writes, vandalised `set("99")` refused inline
  with nothing written, `refresh_theme` in both modes) · the Reports caption end
  to end · acceptance.
- **`phase7_db_test.py`** §2 column expectation now includes `month_start_day`.
- **Battery: `run_all.ps1` → 21 suites, `SUITES FAILED: 0 / 21`.**
- **Real database:** migrated on a **copy** of `data/budget.db` — row
  `(1, 200000, 50, 30, 20)` → `…, 10` with the column added and all 4 expenses
  untouched; the original file's timestamp never moved. Copy deleted.
- **Screenshots:** `p8_1_capture.py` → `p8_1_settings_{dark,light}.bmp` →
  `p8_1_verify.ps1` → PNGs, both visually inspected and pixel-verified
  (dark avgLum 31.7 — dkCard 526k / dkSurface 17k / dkBorder 10k / dkAccent 57k;
  light avgLum 236.4 — ltCard 784k / ltSurface 17k / ltBorder 10k / ltAccent 57k).

### Gotchas this phase added

- **PowerShell `-shl` truncates to the LEFT operand's type.** `($r -shl 16)` with
  `$r` a `[byte]` silently gives `0`, so every colour count came back empty while
  `avgLum` (which never shifts) looked perfect. Cast to `[int]` first — the same
  note already exists in `p8_verify.ps1`; a fresh copy of that script re-learned it.

## Current state of the money numbers

Defaults: salary **120,000**, Needs **50** / Wants **30** / Savings **20**.
Percentages must total **exactly 100** or Save disables and an inline warning shows.

Spent figures in the Dashboard are **computed live since Phase 6** —
`spent = daily` per budget, `remaining = allocation − spent` (**plan fix**:
fixed expenses are the plan and enter no figure anywhere — see the Phase 6 FIX
section). The old
Phase 2 placeholder values (21,400 / 10,650 / 3,650 → 35,700 total, 84,300 left)
are now exactly what you get by logging those amounts as real entries — the
placeholders were kept as the test fixture so the swap could be proven
identical. Roll-up identities asserted in `p6_holder_test.py`: per-category daily
spent + uncategorised daily spent = daily spent per budget (= the `spent` the
Dashboard shows).

Remaining-balance thresholds (unchanged since Phase 3): **>50% → good, 26–50% → warn,
≤25% → bad**, applied inside `refresh_theme()` and `_load_from_settings()`.

## Colour state — banner balance reds were SWAPPED on 2026-01-07

| key | LIGHT | DARK |
|---|---|---|
| `balance_good` | `#A7F3D0` mint (4.90:1) | `#4ADE80` (2.56:1) |
| `balance_warn` | `#FDE047` bright yellow (4.77:1) | `#FBBF24` (2.68:1) |
| `balance_bad` | **`#F87171`** (2.27:1) | **`#DC2626`** (1.08:1) |
| `danger` (validation, *not* the banner) | `#DC2626` | `#F87171` |

The two reds were exchanged between modes at the user's request; `danger` was left
alone because it is used on normal card backgrounds, not the purple banner.
Budget cards keep `info` / `warning` / `success` — untouched.

Known trade-off, already reported once: dark `#DC2626` measures **1.08:1** against
the `#6366F1` banner, the lowest of the six. It still reads because hue differs from
indigo. The user chose this explicitly; if they want more pop later, `#EF4444`
was suggested as a middle shade.

### Added in Phase 4 (delete-confirmation button)

| key | LIGHT | DARK | why |
|---|---|---|---|
| `text_on_danger` | `#FFFFFF` (4.83:1) | `#14161C` (6.54:1) | ink on the danger fill; flips because dark mode's `danger` is a light coral |
| `danger_hover` | `#B91C1C` (6.47:1) | `#EF4444` (4.81:1) | the deeper-on-hover step, mirroring `accent` / `accent_hover` |

Both pairs clear **4.5:1** in both modes and both states (verified by
`phase4_contrast.py`).

### Phase 5 added NO new `theme.py` values

Every colour the Fixed Expenses screen uses already existed (`bg`, `sidebar_bg`,
`card_bg`, `surface`, `border`, `accent`, `accent_hover`, `accent_soft`,
`accent_text`, `text_on_accent`, `info`, `warning`, `success`, `danger`,
`danger_hover`, `text_on_danger`, `text`, `text_secondary`), as did all spacing,
radii and fonts. The LIGHT/DARK import-time guard still passes unchanged.

**Phase 8.1 also added NO new `theme.py` values** — the salary-month card is built
entirely from `card_bg`, `surface`, `border`, `text`, `text_secondary`,
`accent_soft`, fonts `caption`/`body` and radii `sm`/`lg`, all of which already
existed. Guard still passes; `LIGHT` and `DARK` keep identical key sets.

## Phase 8.2 — current-cycle spending (monthly reset) (2026-11-17)

**The problem:** every "spent"/"remaining" figure in the app summed the daily
expenses table *forever*. On the first day of a new salary month the Dashboard
still showed last month's spending, and the balance stayed drained by money
that had already been spent a cycle ago.

**The rule now:** a figure called "spent" means **spent in the salary cycle
that contains today**; "remaining" means **this cycle's allocation − this
cycle's spending**. An expense dated outside today's cycle reduces nothing —
but it stays in the ledger exactly as before (listable, editable, deletable).

### The change is ONE window, applied in ONE place

`app/services/daily_expenses.py` (the only functional change of the phase):

```python
def _cycle_window() -> tuple:
    start, end = budget_settings.cycle_bounds()
    return start.isoformat(), end.isoformat()


def _spent_records():
    first, last = _cycle_window()
    for expense in _rows():
        date = expense["date"] or ""
        if first <= date <= last:
            yield expense["budget"], expense["category"], expense["amount"]
```

- **`_cycle_window()` is formatting, not date maths.** `cycle_bounds()` (Phase
  8.1) does all the calendar work; this only turns the two `datetime.date`
  values into the `"YYYY-MM-DD"` strings the table stores. No new date
  arithmetic exists anywhere in this phase.
- **The comparison stays lexicographic** — `first <= date <= last` on plain
  strings, the same style `reports.py` already used. `"YYYY-MM-DD"` sorts in
  day order, so no row is ever parsed and a malformed stored date cannot raise
  in the middle of a sum (defensive `or ""` makes it sort *before* every real
  date instead).
- **Re-read on every call, never cached** — asserted in `p8_2`: change the
  start day in Settings and `_cycle_window()` changes with it, even mid-run.

**All seven reads therefore filter, because all seven walk that one
iterator** (or call one that does):

| read | how it gets the window |
|---|---|
| `get_spent_by_budget()` | `_spent_records()` directly |
| `get_spent_by_category()` | `_spent_records()` directly |
| `get_uncategorised_spent_by_budget()` | `_spent_records()` directly |
| `get_total_spent()` | `_spent_records()` directly |
| `get_remaining_by_budget()` | allocation − `get_spent_by_budget()` |
| `get_remaining_balance()` | salary − `get_total_spent()` |
| `get_over_budget()` | `get_spent_by_budget()` vs `get_allocations()` |

Because the window is applied once, the four cascade identities still hold
exactly (per-category + uncategorised = per-budget; the three budgets' remaining
sum to the balance; `budget_split()` sums to `get_total_spent()`; `planned_
vs_actual().spent == get_spent_by_budget()`). The roll-up structure of the file
was not reorganised at all — only the iterator gained two lines.

### What deliberately stays ALL-TIME (the "kept both" answer)

| read | why it must see everything |
|---|---|
| `get_expenses()` | the Daily Expenses screen must list, edit and delete *older* entries |
| `count()` | same, plus `reports.has_data()` — a rolled-over cycle must not make the app look "empty" |
| `get_daily_totals_by_budget()` | the explicit "what did they log" read (no app consumer); its docstring now says it is **no longer identical to `get_spent_by_budget()`** |
| `fixed_expenses.get_spent_against()` / `get_plan_progress()` | **not any more** — they were all-time when this table was written; the 8.2 FIX windowed them too (next section) |

So one ledger row can be invisible to the Dashboard and still visible in the
list, in `count()` and in `get_daily_totals_by_budget()`. `p8_2` asserts
`get_daily_totals_by_budget() != get_spent_by_budget()` on purpose.

### The dashboard needed NO code change — and got none

`dashboard_screen.py` calls `get_remaining_balance()`, `get_spent_by_budget()`
and `get_over_budget()` and paints what they return. Those three now return
current-cycle numbers, so the screen's figures and its red/amber/green
colour-coding followed automatically. **Only three comments were edited** (the
module docstring's Phase-6 block, the salary-card comment, the budget-card
comment) so nobody reading the file would believe the old "every expense logged
so far" wording. Zero lines of logic changed; `refresh_theme()` covers the same
widget set as before, so a dark/light flip still keeps every colour correct
(asserted in `p8_2`).

The warnings follow the same way: the over-budget card reads `get_over_budget()`,
so a card that went over **last** cycle clears itself when the cycle rolls over,
and one that goes over **now** turns danger red with "Over by Rs. …" exactly as
before.

### Reports agrees with the dashboard now

`reports.py` needed no code change either. `statistics()["total_spent"]` and
`["remaining"]` come from the cascade; `["month_total"]` comes from
`spent_this_month()`, which computes its own window for the date it is given.
Both windows are `cycle_bounds()` for today, so **for today's date the two are
the same number** — asserted four ways in `p8_2` (month_total == total_spent ==
`get_total_spent()` == the sum of the Dashboard's three SPENT labels).
`spent_this_month(some_past_date)` still answers for *that* cycle, which is the
one thing the cascade cannot do.

### Fixed expenses, plan progress and reconcile

- **A plan is still never spending.** Adding a fixed expense changes no spent
  figure and no remaining figure — asserted directly in `p8_2`.
- **`reconcile()` walks the whole ledger, not the window.** `p8_2` deletes a
  category that an *out-of-cycle* expense still points at, and the link is
  repaired as always (the row is then uncategorised-but-present; the money
  never vanishes).
- **The plan reads were all-time when this phase shipped — fixed the next
  day, in the next section.**

### Phase 8.2 FIX — plan progress uses the current cycle too (2026-11-18)

**The bug:** Phase 8.2 windowed the cascade but left `get_spent_against()` /
`get_plan_progress()` summing every row ever, so the two screens disagreed —
the Fixed Expenses screen could show "✓ Paid" for a plan paid **last** cycle
while the Dashboard showed this month's spending as 0.

**A plan is MONTHLY, so "spent against it" and "Paid" mean "this cycle."**

**What changed — `app/services/fixed_expenses.py` only:**

- two private helpers, mirroring `daily_expenses`': `_cycle_window()` (three
  lines over `budget_settings.cycle_bounds()` — formatting, not date maths)
  and `_daily_this_cycle()` (the ledger filtered with the same lexicographic
  `first <= (d["date"] or "") <= last`).
- **`get_spent_against(name)`** sums `_daily_this_cycle()` instead of
  `get_expenses()`.
- **`get_plan_progress()`** starts from `daily = _daily_this_cycle()`, so every
  figure derived from it — `progress`, `paid`, `state`, `over_by` — resets with
  the cycle. The three-way state maths and `over_by` are unchanged; only the
  ledger they read narrowed.
- **`_matches_plan()` did NOT change** — it decides *which* plan an expense
  belongs to (budget + category + sub-item) and never had a date rule; the
  window is applied to the records handed *to* it.
- **`get_plan_vs_allocation()` (§3c) did NOT change** — it compares planned vs
  allocated, involves no spending, so it has no window. Its section header
  says so on purpose.

**Consistency grep:** the only consumers of `get_spent_against` /
`get_plan_progress` are `fixed_expenses_screen.py` (formats and paints only —
the maths stays in the holder) and the test suites. `reports.py` has no "paid"
or "progress" concept and the Dashboard has none either; nothing else in the
app matches spending against a plan.

**Asserted in `p8_2` [8]** (the prompt's exact scenario): start day 10 → cycle
10 Nov–9 Dec; a 30,000 Rent expense dated **2026-11-01** (previous cycle)
leaves `get_spent_against` 0, `paid` False, state `under`, the Dashboard at
needs-spent 0 / balance 120,000, and `spent == get_spent_by_budget()["needs"]`;
the same 30,000 dated **on the 10th** then pays it (`paid` True, state `met`,
both screens 30,000, balance 90,000) with §3c still reporting
`{planned: 30000, allocated: 60000, exceeds: False, over_by: 0}`. `p8_2` [4]
additionally asserts `fx._cycle_window() == de._cycle_window()` so the two
mirrored helpers cannot drift apart.

**Files touched:** `app/services/fixed_expenses.py` (the change),
`app/services/daily_expenses.py` (three stale comments only — the cascade
diagram and the "what stays all-time" bullet). **No screen, no `main.py`, no
`theme.py`, no new theme values** (LIGHT and DARK key sets unchanged — the
import guard still passes).

### `theme.py` and `main.py`

Neither touched. The phase needed no new colour/font/spacing/radius (LIGHT and
DARK keep identical key sets — the import guard still passes) and no screen was
added, removed or renamed.

### Numbers (default start day 1, today 2026-11-18 → cycle 1–30 Nov)

| ledger | counts as |
|---|---|
| 8,000 dated 2026-10-31 (last cycle) | **nothing** — invisible to every cascade figure |
| 1,500 dated 2026-11-01 (this cycle) | 1,500 spent, balance 118,500 |
| move the 1,500 into last cycle too | spent 0, balance **120,000** (full refill) |
| with start day 10 (cycle 10 Nov–9 Dec) | both of the above rows are now pre-cycle → spent 0; a new row dated 2026-11-10 counts |

## Phase 8.3 — monthly history archive + date-range caption (2026-11-18)

Three deliverables, all **read-only**: a date-range caption on the cycle stat, a
history aggregation in `reports.py`, and a History tab on the Reports screen.
**No new date arithmetic anywhere** — every window still comes from the Phase
8.1 helpers (`cycle_of` / `cycle_bounds` / `cycle_label`).

### 1. The date-range caption

- **New `budget_settings.cycle_range(key=None) -> str`**, sitting beside
  `cycle_label` in section 5: it FORMATS what `cycle_bounds()` returns —
  `"{d.day} {d.strftime('%b')}"` per end joined with an en dash — giving
  `"10 Nov – 9 Dec"`. Day without a leading zero ("9 Dec", not "09"); when a
  cycle crosses New Year the END gains its year (`"10 Dec – 9 Jan 2027"`),
  because the label beside it already carries the start month's year.
  Formatting only — the function contains no date computation at all.
- **`reports.statistics()` gained `month_range`**, derived from the SAME cycle
  key as `month_name` (the key is read once), so the two can never name two
  different windows.
- **The screen:** the existing caption label of the "SPENT THIS MONTH" tile now
  holds TWO lines — `SPENT IN NOVEMBER` / `10 Nov – 9 Dec`. One `configure()`,
  no new widget, no grid row, and the other three tiles stay single-line
  (asserted). `reports_screen.py` still contains no `strftime`: the string
  arrives formatted (asserted in `phase8_1_test` §6).

### 2. History data — `reports.cycle_history()` (section 6; `ONE SHOT` → 7)

- **How it groups:** walk `daily_expenses.get_expenses()` once (the ledger,
  all-time), turn each row's `"YYYY-MM-DD"` back into a `date` with
  `dt.date.fromisoformat` inside a try/except — reading a date the app itself
  wrote (the same reader `daily_expenses._normalise_date` uses); a malformed
  row is SKIPPED, never raised, so a report can never crash on one. Each date
  goes to `budget_settings.cycle_of()` and the amounts are summed under that
  key. Because `cycle_of` is the same helper the cascade names cycles with,
  history can never disagree with the rest of the app, and `cycle_bounds()`
  windows are contiguous so every expense lands in exactly ONE record.
  `sorted(keys, reverse=True)` — `"YYYY-MM"` strings sort in month order —
  gives **newest first**.
- **Returns** `{key, label (cycle_label), range (cycle_range), spent, salary,
  saved}`; `saved = salary − spent` may be NEGATIVE (an overspent cycle) and
  is never clamped — asserted: 200,000 spent vs 120,000 salary → −80,000.
- **The current cycle is EXCLUDED** — it is not finished; its figures are
  already on the stats tiles, and a "Saved Rs. X" for a half-lived month would
  read as a fact about a month nobody has finished living yet.
- **THE SALARY LIMITATION (handled honestly, as asked):** the app stores ONE
  salary — today's — so `salary` is `get_salary()` for EVERY record and
  `saved` is measured against it. A past cycle's saving is therefore honest
  arithmetic **at today's rate**, not necessarily what the user actually
  banked then; if the salary has changed since, every older figure is off by
  that difference. The cleaner alternative (a real per-cycle salary history)
  needs new storage, which this read-only phase deliberately does not add —
  propose it as its own change if wanted.
  **The exact wording shown to the user** — a footnote pinned under the History
  list (caption font, `text_secondary`), restated on every reload because it
  quotes the salary:

  > Saved = what you spent that cycle taken off your CURRENT salary
  > (Rs. 120,000). Only today's salary is stored - there is no salary history
  > - so past cycles are measured at today's rate.

  Per record the verdict is plain: `Saved Rs. X this cycle` (`success`) or
  `Overspent Rs. X this cycle` (`danger`).
- `report()` gained `"history": cycle_history()` so the screen still makes ONE
  pass over the holders per reload, exactly like every other figure it draws.

### 3. History UI — a third tab

- **`TAB_HISTORY = "History"`**, `TABS = (TAB_SPENDING, TAB_PLAN, TAB_HISTORY)`.
  A tab was chosen over a section because History is a different KIND of
  content (text records, unbounded height) from the two chart tabs, and the
  stats + filter stay visible above it either way.
- **The current cycle is EXCLUDED** (not marked "in progress") — the option
  picked; its spending is already the headline stat.
- One card per cycle in a `CTkScrollableFrame` (cycles accumulate forever):
  label + range + spent on the left, the verdict pinned right, `success` /
  `danger` from state, `card_bg` / `border` card. `_apply_history()` rebuilds
  the rows on every `_reload()` AND on every `refresh_theme()` — the verdict
  colours are state-derived, so a rebuild is the same "born painted" contract
  the other screens use — and restates the footnote. Empty state: **"No
  finished salary cycles yet"** + *"History appears once a salary cycle ends.
  Your current cycle is in the statistics above."*
- The tab has **no figure**, so none of the matplotlib machinery applies and
  `_draw_all()` is untouched. The scrollbar follows the other three lists'
  convention (`surface` / `text_secondary` / `text`).

### Files changed

`app/services/budget_settings.py` (`cycle_range`) · `app/services/reports.py`
(`month_range`, `cycle_history`, `report()["history"]`, docstrings) ·
`app/ui/reports_screen.py` (tab constant, two-line caption, `_build_history`,
`_apply_history`, a `refresh_theme()` block, docstrings/comments) ·
`PROGRESS.md` · temp tests. **`main.py` untouched (no `History` /
`cycle_range` token), `theme.py` untouched — NO new values** (every colour,
font, spacing and radius reused; the LIGHT == DARK import guard still passes).

### Tests

- **`phase8_3_test.py` — now 6 sections, 80 checks, ALL PASSED** (sections
  1–5 held 61 checks after the palette fix; fix 2 below added section 6's 17
  checks plus two footnote checks in §4 — see its Tests paragraph): cycle_range
  (start day 1 vs 10, cross-New-Year, follows the setting live) ·
  cycle_history (grouping, the exact record dicts, current excluded, overspent
  −80,000, three read-only proofs, current-only ledger → `[]`) · travel
  through `statistics()` / `report()` · the UI (two-line caption, three tabs,
  per-card texts + success/danger colours, footnote wording, light↔dark
  re-theme — now INCLUDING the list-background regression checks below —,
  empty state, read-only) · **the acceptance: start day 10 → October
  (spent 5,000 → saved 115,000) and September (spent 3,000 → saved 117,000) as
  two separate records, in the data AND on screen.**
- **Two older assertions re-expectationed** (they pinned what this phase
  deliberately changed, not behaviour drifting underneath): `phase8_1_test.py`
  §6 — the caption is now two lines (line 1 must still be exactly
  `SPENT IN {month}`, line 2 must equal `statistics()["month_range"]`); and
  `p8_ui_test.py` — the tab-bar seam check now counts **3** segments instead
  of 2 (all still `card_bg`, so no seam shows).
- **Battery `run_all.ps1` → 23 suites (new `p8_3` entry), `SUITES FAILED: 0 / 23`.**
- Date fixtures assume today is in November 2026 on/after the 10th — the same
  class of assumption the other Phase 6/8 suites make with their hardcoded
  2026-11 dates.

### 8.3 FIX — the History list's empty area kept the previous palette (2026-11-18)

**Symptom (user's screenshots):** the empty area of the History list — the
scrollable canvas below the first card — painted the OPPOSITE palette: white
in dark mode, black in light mode.

**Root cause (proven with a runtime probe, not guessed):**
`CTkScrollableFrame` paints its canvas and inner frame from
`_parent_frame.cget("bg_color")` at only three moments — construction,
`_set_appearance_mode`, and `configure(fg_color=...)`
(`ctk_scrollable_frame.py` lines 93-98 / 135-143 / 179-191). `main.py`
flips in three ordered steps (lines 347-373): `theme.set_mode()` →
`ctk.set_appearance_mode()` → `screen.refresh_theme()`. Step 2 fires the
scrollable frame's `_set_appearance_mode` while `_parent_frame` still holds
the OLD mode's colour, so the canvas is painted with the previous palette;
step 3 re-themes the tabview (which DOES update `_parent_frame.bg_color`
through the tab frame's child propagation) but never copies that value into
the canvas. Net effect: **the list's empty area is always one flip behind**
— flip to light and it goes black, flip back and it goes white (both
screenshots from one session).

**Why only this screen:** the other three lists (daily expenses, categories,
fixed expenses) pass `fg_color="transparent"` in their
`refresh_theme() → _list.configure(...)` — that kwarg runs the `fg_color`
branch of `CTkScrollableFrame.configure`, which recopies
`_parent_frame.bg_color` into canvas + inner frame. The Reports screen's
`_history_list.configure(...)` carried only the three scrollbar keys, so the
recopy never happened.

**The fix (one kwarg + a comment, `app/ui/reports_screen.py` only):**
`fg_color="transparent"` added to the existing `_history_list.configure(...)`
in `refresh_theme()` — placed after the tabview re-theme, so
`_parent_frame.bg_color` is already the new palette when the copy runs.
Keeps the design exactly as it was (transparent parent frame); adds no
widget, no colour, no theme.py value; `main.py` untouched.

**Verification:**
- Probe (`history_bg_probe.py`, temp dir) reads the canvas + inner frame in
  birth → light → dark: before the fix `#121317` after flipping to light and
  `#F4F5F8` after flipping back; after the fix both match
  `theme.color("bg")` in every state.
- `phase8_3_test.py` §4(e) now flips in main.py's exact three-step order and
  asserts canvas + inner-frame bg == `theme.color("bg")` in BOTH directions
  (**61 checks**). Removing the fix fails exactly those two checks with the
  reported colours (`('#121317', '#121317')` in light, `('#F4F5F8',
  '#F4F5F8')` in dark) — proven by a temporary-revert run.
- Battery `run_all.ps1` → `SUITES FAILED: 0 / 23`.

### 8.3 FIX 2 — per-cycle salary history (correct savings maths) (2026-11-18)

**The bug:** `reports.cycle_history()` measured EVERY past cycle's saving
against `budget_settings.get_salary()` — **today's** salary. Change the salary
next month and every older "Saved" figure silently moved with it (200,000 back
then became "saved 150,000 − spent" today).

**Storage (`app/core/db.py`, new table in `_SCHEMA`):**

```sql
-- one row per salary cycle: what the salary was WHILE that cycle ran
CREATE TABLE IF NOT EXISTS cycle_salary (
    cycle_key TEXT PRIMARY KEY,   -- "YYYY-MM", exactly what cycle_of() returns
    salary    INTEGER NOT NULL
);
```

**Migration: none beyond `IF NOT EXISTS`** — unlike a new COLUMN on an
existing table (which is why `_migrate_budget_settings()`'s ALTER exists), a
brand-new TABLE is created by the same statement for fresh AND existing
databases. Old files simply gain an empty table on next launch; rows appear as
the user lives through cycles with the feature installed. The single
`budget_settings` row, `get_salary()`/`set_salary()` and the CHECK(id=1)
design are all untouched — this is an additional record alongside them.

**Exactly when a cycle's salary is recorded** — one private writer in
`budget_settings.py` §3, `_record_cycle_salary(key, salary)` (UPSERT, key
validated with the existing `_parse_cycle_key`, failure swallowed because it
sits on the read path):

1. **on `set_salary()`** — after the settings row is stored, before `_notify()`
   (a subscriber redrawing history must see the fresh record). The key is
   `cycle_of()` = the CURRENT cycle, so changing the salary in a later month
   writes that new cycle's row and leaves the old cycle's row untouched.
2. **on a plain `get_salary()` read** — the same upsert of
   `cycle_of() → value just read`. That is how a user who upgrades mid-cycle
   gets the current cycle on file with **no new user action**: the first
   Dashboard repaint does it. The value read *is* the current salary for the
   current cycle by definition, so recording it is always true — and only the
   current cycle is ever written, so a fallback read for a past cycle never
   fabricates that past key's row.

**Readers (both public, in `budget_settings.py`):**

- `get_salary_for_cycle(key)` → the stored salary, **falling back to
  `get_salary()` (today's)** when there is no row (pre-feature months) or the
  stored value cannot be a salary (negative / non-integer — only reachable by
  hand-editing, since `set_salary()` refuses those; same rule as
  `get_month_start_day()`). It never writes the queried key.
- `has_salary_for_cycle(key)` → whether a USABLE row is actually on file.
  Needed because value comparison cannot tell "recorded 120,000" from "fell
  back to today's 120,000" — this is what keeps un-recorded cycles
  distinguishable. Both share `_stored_salary_for_cycle()` so they can never
  disagree about what "recorded" means.

**History (`reports.cycle_history()`):** per record, `salary`/`saved` now come
from `get_salary_for_cycle(key)`, and each record gained
`"salary_recorded": bool`. `statistics()["salary"]` (the tiles, the dashboard)
is untouched — still today's salary; current-cycle spending/remaining and the
dashboard changed nowhere.

**The footnote (`reports_screen._apply_history`) — now two branches** (rows
are read before the note; a record missing the flag counts as unrecorded, so
the note over-admits rather than lies):

- every record recorded (or no records at all):
  *"Saved = what you spent that cycle taken off the salary that cycle paid.
  Each cycle's salary is recorded automatically as you go, so every figure in
  this list is that cycle's own arithmetic."*
- any unrecorded record in the list:
  *"Saved = what you spent that cycle taken off the salary that cycle paid.
  Cycles from before salary history was recorded have no salary of their own
  on file — those are measured against your CURRENT salary (Rs. 120,000)."*

The old footnote claimed **ALL** cycles were measured at today's rate; now only
the un-recorded ones are said to be — and only when some exist.

**Acceptance confirmed (`phase8_3_test.py` §6):** set salary **200,000** →
log an expense dated in a past cycle → change salary to **150,000** (current
cycle) → the past cycle's record reads **salary 200,000 / saved 195,000,
`salary_recorded: True`** — NOT 150,000 / 145,000 — and October's stored row
is byte-identical after the change. Two variants: §6(d) always runs (October's
row written with the exact UPSERT `set_salary()` uses, standing in for "200k
was on file while October was current"); §6(e) runs the sequence **end to end
through the real `set_salary()`** with start-day time travel (start day =
today+1 drops today into October; moving it back to 10 turns October into
history) — guarded for `today.day <= 27` (prints SKIP otherwise; today is the
18th, so it ran and passed).

**Files changed:** `app/core/db.py` (table + comment) ·
`app/services/budget_settings.py` (module docstring; `_record_cycle_salary` +
`_stored_salary_for_cycle` in §3; `get_salary()` side effect; `set_salary()`
hook; `get_salary_for_cycle`, `has_salary_for_cycle`) ·
`app/services/reports.py` (`cycle_history()` salary + flag; PHASE 8.3,
READ-ONLY and THE SALARY docstrings rewritten) ·
`app/ui/reports_screen.py` (`_apply_history` footnote branch) ·
`PROGRESS.md` · temp tests. **`main.py` untouched; `theme.py` untouched — NO
new values** (the footnote reuses `text_secondary`; the LIGHT == DARK import
guard still passes).

**Tests:** `phase8_3_test.py` §6 — **17 new checks**: set-recording,
read-recording (DELETE the row → `get_salary()` restores it), stored-wins /
fallback / no-fabrication / hand-edited −5 row, both acceptance variants, both
footnote branches; plus **re-expectationed** (they pinned what this fix
deliberately changed): the two exact record dicts gained
`salary_recorded: False`, §4(d)'s footnote wording, §4(f)'s empty-state note
(an empty list is all-recorded → clean branch). Total now **6 sections, 80
checks**. `p8_holder_test.py` §6's "reports.py writes nothing" proof compares
holder VALUES (salary, allocations, ledger), never raw DB bytes — the
current-cycle auto-record does not disturb it, so no other suite needed
touching. Battery → **`SUITES FAILED: 0 / 23`.**

## Phase 8.4 — monthly comparison (the Compare tab) (2026-11-18)

A fourth **Compare** tab on the Reports screen: pick two finished salary cycles
and see them side by side — the same per-cycle figures the History tab shows,
read-only, built on `reports.cycle_history()` and the budget_settings cycle
helpers, with **no new date arithmetic anywhere**.

### 1. The comparison data — `reports.compare_cycles()` (section 6b)

- **Given cycle keys → one record per key:** `key`, `label`, `range`,
  `salary` (that cycle's own, via `get_salary_for_cycle`), `spent`, `saved`,
  `salary_recorded`, and the breakdown below. Every shared figure is **copied
  verbatim** from `cycle_history()` (`{**record}` — never recomputed), so
  History and Compare can never disagree about a month; the suite pins the
  equality field by field.
- **Per-budget breakdown: INCLUDED** (the prompt's optional ask) — `budgets`
  is a `{"needs": …, "wants": …, "savings": …}` dict per cycle, grouped with
  `budget_settings.cycle_of()` over the same `get_expenses()` pass
  `cycle_history()` uses, so the comparison shows *where* spending differed,
  not just the totals; the suite pins `sum(budgets) == spent` for every cycle.
- **Caller's order honoured, no dedup** — a real key asked for twice comes
  back twice (documented; it keeps the screen simple). The current cycle,
  unknown keys and empty/`None` input are skipped. Read-only: it writes
  nothing anywhere (ledger + settings snapshots compared before/after).

### 2. The Compare tab — `app/ui/reports_screen.py`

- **`TAB_COMPARE = "Compare"`** — the fourth segment on the existing
  `CTkTabview`, same pattern as History.
- **Two `CTkOptionMenu` dropdowns** — the choice over a multi-select:
  CustomTkinter has no multi-select control that matches this screen's look,
  so two menus with a **"vs"** label between them are the cleanest. Both are
  width 170 with `dynamic_resizing=False` and the Settings option-menu
  palette, both list every finished cycle's label from `cycle_history()`
  (newest first), and both default to the **two newest** cycles.
- **A grouped matplotlib bar chart** — the choice over a side-by-side table:
  it makes the *differences* jump out (one group per cycle, three bars per
  group in the budget accents `info`/`warning`/`success`, spent + saved
  annotated above each group in `text`/`success`/`danger` — an overspent
  cycle says **OVERSPENT Rs. …** in `danger` — and two-line x labels
  "label\nrange"). It follows the exact chart theming pattern the other
  figures use: `_apply_matplotlib_palette()` at the top of every draw,
  `_style_axes()`, the MONEY formatter, per-draw repaint on theme flip.
- **One salary caption line** above the card quoting each cycle's own rate —
  with the † "CURRENT salary" footnote whenever any selected cycle has no
  recorded salary (the same honest branch History's footnote uses).
- **Empty state:** fewer than two finished cycles → the body hides wholesale
  and a friendly note ("Nothing to compare yet / Comparing needs at least two
  finished salary cycles…") takes the tab; the salary line and comparison
  data are cleared so no stale chart can draw while the note is up.
- **`refresh_theme()`** re-applies the compare section (menus, captions, the
  card) and `_draw_all()` repaints the figure — every new widget and the
  chart re-theme on toggle, both directions.

### Files changed

`app/services/reports.py` (module docstring PHASE 8.4 paragraph;
`compare_cycles()`, section 6b) · `app/ui/reports_screen.py` (docstring,
`TAB_COMPARE`, `__init__` state, `_build` order, `_build_tabs`,
`_build_charts`' fourth card, `_build_compare`, `_reload`,
`_apply_compare`/`_fill_compare`/`_on_compare_changed`, `_draw_all`,
`_redraw`, `_draw_compare`, `refresh_theme`) · `PROGRESS.md` · temp tests.
**`main.py` untouched; `theme.py` untouched — NO new values** (the only new
constant is the screen's own layout value `COMPARE_NOTE_WRAP = 560`, inside
`reports_screen.py`).

### Tests

`phase8_4_test.py` — **9 sections, all passing**: exact record dicts +
verbatim reuse from `cycle_history()` + order/skip/no-dedup/read-only;
per-budget buckets and sums; recorded vs fallback salary (the 8.3 mechanism
feeding 8.4); the tab, the two-newest defaults, the chart's bars/annotations/
colours; a dropdown change redrawing just the compare chart (OVERSPENT danger
branch); the clean footnote once both salaries are on file; the theme flip
both directions (the repainted figure carrying fresh data); 1 → 0 → 2
finished cycles (note, recovery); guards. **Re-expectationed** (both pinned
what the phase deliberately changed): `phase8_3_test.py`'s tab-title
expectation (3 → 4, "Compare" last) and `p8_ui_test.py`'s tab-bar seam count
(`len(tabbar) == 3` → `4`). Registered `p8_4` in `run_all.ps1` → battery
**`SUITES FAILED: 0 / 24`.**

## Gotchas learned the hard way

- **Tk pack discipline:** packing a second screen into a container without
  `pack_forget()`ing the first leaves the second *unmapped*, and Tk then silently
  drops generated key events. Tests must mirror `main.py`'s `show_screen()`. This
  caused a long, misleading debugging detour in Phase 3 — the app was never broken.
- `widget.configure("key")` returns `None` on CTk widgets; use **`cget("key")`**.
- `CTkEntry.bind()` forwards to the inner entry and works; `CTkFrame.bind()` raises.
  `CTkEntry` accepts `justify` as a kwarg.
- `CTkProgressBar.set()` self-clamps to [0, 1].
- `event_generate("<KeyRelease>")` only delivers to a **focused, mapped** widget.
- Test teardown prints harmless `invalid command name ... after` noise from CTk's
  pending DPI/focus callbacks — cosmetic, not an app bug.
- Console is cp1252: printing emoji from a test script crashes. Avoid it.
  (Set `$env:PYTHONIOENCODING="utf-8"` first — then even `✓` is safe to print.)

### Phase 4 additions

- **CustomTkinter is v6.0.0.** `CTkButton` has `invoke()` but **no
  `hover_text_color`** — only `hover_color` (the face). So "highlight" is done
  with the face, never with the label.
- **A CTk widget hides an inner tkinter widget carrying the same text**
  (`CTkLabel`/`CTkButton` → inner `Label`). Walking a tree and reading
  `cget("text")` therefore counts every string **twice** and breaks any
  assertion that expects N. Fix: stop descending the moment a widget answers
  `cget("text")`.
- **`CTkScrollableFrame` overrides `grid()`/`pack()`** to forward to its own
  parent frame, and it *is* the canvas window its children are gridded onto.
  So `frame.grid_columnconfigure(0, weight=1)` on the scrollable frame itself
  is exactly what the cards need — no wrapper required.
- **`CTkToplevel` starts `withdrawn` on Windows**: it withdraws to repaint its
  titlebar colour and deiconifies on a *later* event-loop tick. Call
  `deiconify()` yourself, and only `grab_set()` once `winfo_viewable()` is true
  or the grab silently fails.
- **`event_generate("<Return>")` needs real focus first**: `entry.focus_set()`
  + `root.update()` before generating, or the event is dropped and the test
  reports a false failure.
- **`CTkEntry` stores its text on the inner entry** (`entry._entry`), so bind
  assertions must be read there — `entry.bind("<Return>")` alone returns
  something that reads as false.
- Screenshots of a freshly mapped window come out **all white**; pump
  `dialog.update()` ~30 times before `PrintWindow`.

### Phase 5 additions

- **`CTkLabel.width=` is honoured and scales with DPI** (200 → `reqwidth` 250 at
  125%); **`CTkFrame.width=` is ignored when the frame has children** (it shrinks
  to them). So a fixed-width *pill box* must be a grid `minsize`, not a frame's
  `width`.
- **`grid columnconfigure` has no `-width` query** — options are only `minsize`,
  `pad`, `uniform`, `weight`. To read a column back, measure a child's `winfo_x()`.
- **`winfo_reqwidth()` misses grid padding.** Re-reading the label's text width and
  adding `gap` by hand was 1px out (Tk scales the padding); measuring the *chip's*
  `winfo_x()` instead is exact, because that is literally the number that must match.
- **`update_idletasks()` before measuring geometry** — a widget only reports a real
  position after Tk has laid it out.
- **The image viewer went stale** mid-session and kept serving one old PNG for every
  path. Verify screenshots by **pixel statistics** instead: `System.Drawing` +
  `LockBits`, average luminance, and a colour scan for a known widget fill.
- `main.py` exposes `app.screens` (dict) and `app.show_screen(key)` — useful for
  probes that need the *real* shell rather than a bare screen.

### Phase 6 additions

- **Tk grid shares a DEFICIT proportionally to the weights, not just a surplus.**
  With controls requesting more than the row can hold, a `weight=2` column
  absorbs *double the cut* and can end up the **narrowest** column — the exact
  opposite of the intent. Measured: 1:1:2:1 over 467px with 700px requested →
  128/128/**82**/128. Only moving the buttons off the row restored positive
  excess. (Same maths explains the Fixed screen's ~97px weight-2 columns.)
- **`CTkOptionMenu` uses `dynamic_resizing`** — its requested width tracks the
  *current* value (`req` jumps 175 → 328 for "Shopping + Installment
  payments"), so a long value both needs more room and increases the pressure
  on its neighbours. Its inner label is `menu._text_label`.
- `geometry("960x620")` is interpreted in **logical** pixels by CTk v6 and
  lands at 1200 physical on the 125% display — a probe must read
  `app.winfo_width()` (1200) before comparing with physical widget widths.
- **`Select-Object -First N` kills the Python process** (exit -1, broken pipe)
  when a probe prints more lines than N — exit codes are only meaningful when
  the full output is consumed.
- **Plan fix gotchas (same day):** a `CTkProgressBar` is NOT an instance of
  `CTkFrame`, so the new row-1 bars don't disturb `_align_name_columns`'s
  `isinstance` filtering, and children-in-creation-order probes still see
  name/chip/amount first (create the progress widgets AFTER the row-0 ones).
  Spanning columns 0..2 is safe because column 2 is the row's only *weighted*
  column: grid takes any width variance from the slack column, never from the
  chips or the amount above. The status label needs a **fixed** `width=`
  (`CTkLabel` honours it and DPI-scales) — otherwise "✓ Paid" vs
  "Rs. 8,000 / Rs. 30,000" would make column 3 a different width per row and
  push each row's amount left by a different amount (`amt end spread` would
  stop being 0 px).
- **CustomTkinter's own focus bookkeeping** (`after(1, ...focus)` inside
  `ctk_tk.py`) can print `bad window path name` in the console when a capture
  script drives a form and switches screens within the same tick. No project
  code schedules focus via `after`; harmless (the callback dies, Tk continues),
  but it shows a traceback.

## Test/verify commands

```powershell
cd "C:\Users\diese\Budget Tracker\budget_tracker"
$env:PYTHONIOENCODING = "utf-8"
# Phase 1-3 regression (now also asserts the third screen + nav reachability)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase3_test.py"
# Phase 4: holder validation / tree API
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase4_holder_test.py"
# Phase 4: screen rendering, add/rename/delete, dialogs, theming
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase4_ui_test.py"
# Phase 4: WCAG check on the two new colour pairs
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase4_contrast.py"
# Phase 5: fixed-expense holder validation / reconcile / totals
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p5_holder_test.py"
# Phase 5: screen rendering, add/edit/delete, uncategorised, theming (13 sections)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p5_ui_test.py"
# Phase 5: the fourth screen wired into the real shell + sidebar renumber
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p5_main_test.py"
# Phase 5: WCAG pairs (0 failures; the 2 dark primary-button LOWs are Phase 3)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p5_contrast.py"
# Phase 5: row geometry probe - chip/name/amount spreads. Args: SIZE ["app"]
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p5_geometry.py" 960x620 app
# Phase 6: daily-expense holder validation / cascade maths / reconcile
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p6_holder_test.py"
# Phase 6: screen CRUD, date grouping, conditional sub-item, dashboard figures
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p6_ui_test.py"
# Phase 6: geometry probe - form widths, chip spread, day headers, edit outline
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p6_geom.py" 960x620 app
# Phase 6 FIX: plan screenshots (paid / partial / unpaid rows + dashboard w/ plans)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p6_fix_capture.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\diese\AppData\Local\Temp\opencode\p6_fix_verify.ps1"
# Phase 6.5 (files still named p7_*): the three warning comparison reads
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p7_holder_test.py"
# Phase 6.5: the three warnings on screen + the theme-flip danger guards
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p7_ui_test.py"
# Phase 6.5: warning screenshots (fixed dark/light + over-budget dashboard)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p7_capture.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\diese\AppData\Local\Temp\opencode\p7_verify.ps1"
# Phase 7: schema, seeding, frozen API, name-links + reconcile, error rules
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase7_db_test.py"
# Phase 7: THE decisive test - write data, close the app, reopen, compare
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase7_persist_test.py"
# Phase 8: the read-only reports layer (60 checks: split/bars/comparison/stats)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p8_holder_test.py"
# Phase 8: the Reports screen - empty state, real charts, theme flip (125 checks)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\p8_ui_test.py"
# Phase 8.1: month start day, salary cycles, Reports rewiring, DB migration (7 sections)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase8_1_test.py"
# Phase 8.2: the cycle filter on all seven cascade reads + plan reads (8 sections)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase8_2_test.py"
# Phase 8.3: date-range caption + cycle_history + the History tab (5 sections)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase8_3_test.py"
# Phase 8.4: compare_cycles + the Compare tab (9 sections)
.\.venv\Scripts\python.exe "C:\Users\diese\AppData\Local\Temp\opencode\phase8_4_test.py"
# WHOLE battery at once: one line per suite, exit code = number of failing suites
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\diese\AppData\Local\Temp\opencode\run_all.ps1"
```

Expected: phase3 → `ALL PHASE 3 TESTS PASSED` (exit 0); every other script →
`FAILURES: 0` (p5_holder → `PASSED: 137`; p6_holder, p6_ui, p7_holder, p7_ui and
`phase7_persist_test` → `ALL PASSED`; `phase7_db_test` → `PHASE 7 DB TEST: ALL
PASSED`; `p8_holder` → `PHASE 8 HOLDER TEST: ALL PASSED`; `p8_ui` → `PHASE 8 UI
TEST: ALL PASSED`; `phase8_1_test` → `PHASE 8.1 TEST: ALL PASSED`;
`phase8_2_test` → `PHASE 8.2 TEST: ALL PASSED`; `phase8_3_test` → `PHASE 8.3
TEST: ALL PASSED`; `phase8_4_test` → `PHASE 8.4 TEST: ALL PASSED`).
p5_contrast reports
`FAILURES (Phase 5 pairs): 0` plus `PRE-EXISTING (Phase 3 pairs): 2` — the two dark
`text_on_accent on accent` LOWs (4.47:1 / 3.61:1), excluded from its exit code.
`p5_geometry` should print `chip x spread : 0 px` and `amt end spread : 0 px`;
`p6_geom` should print `chip x spread : 0 px`, no control under 60px, and
category ≈203 physical px at 960x620. **`run_all.ps1` runs all 24 suites
(phase2_smoke → p8_4), one line each, exit code = failing suites — 0 after
Phase 8.4.** It also sets `BUDGET_TRACKER_DB=fresh` so a batch run can never
touch your real `data/budget.db` — verified after Phase 8: its last write is
still 2026-11-11, i.e. untouched by the battery.

Visual: run `p6_capture.py`, then `powershell -NoProfile -ExecutionPolicy Bypass
-File p6_verify.ps1` — it converts the `.bmp` outputs to PNG *and* prints the
pixel statistics (the viewer is stale) for
`p6_daily_{empty_dark,list_dark,error_dark,edit_dark,light,dialog}.png` +
`p6_dashboard_real.png`. Plan fix: `p6_fix_capture.py` + `p6_fix_verify.ps1` →
`p6_fix_plan_dark/light.png` (paid / partial / unpaid rows) and
`p6_fix_dash_plan.png`. Warnings: `p7_capture.py` + `p7_verify.ps1` →
`p7_warn_fixed_dark/light.png` (three row states + amber section warning) and
`p7_warn_dash_over.png` (over-budget card). Reports: `p8_capture.py` +
`p8_verify.ps1` → `p8_reports_{dark,light}.png` (donut + legend, horizontal
budget-coloured category bars, comparison with "under Rs." notes) and
`p8_reports_{empty_dark,empty_light}.png` (the friendly empty panel). After the
layout fix: `p8_capture.py` → **eight** shots, adding
`p8_reports_{plan_dark,plan_light}.png` (the Plan vs Actual tab in both
palettes), `p8_reports_default_dark.png` (1120×740) and
`p8_reports_min_dark.png` (960×620, where the donut label scales to fit).
Phase 8.1: `p8_1_capture.py` + `p8_1_verify.ps1` → `p8_1_settings_{dark,light}.png`
(the new salary-month card, dropdown holding "10"). Phase 8.2:
`p8_2_capture.py` + `p8_2_verify.ps1` → `p8_2_dashboard_{cycle,reset}.png` —
two real Dashboard shots (8,000 logged last cycle + 1,500 this cycle →
Rs. 118,500; then the 1,500 moved into last cycle → Rs. 120,000), converted and
**diffed pixel by pixel** (1,754 pixels changed) because the viewer is stale.
Older: `p5_capture.py` → `p5_fixed_*.png`;
`phase4_capture.py` → `p4_categories_*.png`; `balance_capture.py` +
`balance_sheet.ps1` → `balance_contact_sheet.png`.

Note: a `2>$null | Select-String` pipeline makes PowerShell report exit code 1 even
on success — an artifact of redirecting Tk's stderr, not a real failure. Check the
script's own `$LASTEXITCODE` instead.

## Open threads

- No pending bug reports. Phase 6 **+ the same-day plan fix + Phase 6.5
  (overspend warnings) + Phase 7 (SQLite) + Phase 8 (Reports & charts) +
  Phase 8.1 (salary cycle) + Phase 8.2 (monthly reset) + the 8.2 FIX (plan
  progress uses the cycle too) + Phase 8.3 (history + date caption) + its two
  FIXes (list background palette; per-cycle salary history) + Phase 8.4
  (monthly comparison)** verified
  by **24
  suites, all exit 0**
  (single batch via `run_all.ps1`): `phase2_smoke`,
  `phase3`, `phase4_holder`, `phase4_ui`, `phase4_contrast`, `p5_holder`,
  `p5_ui`, `p5_main`, `p5_contrast`, `p5_geometry`, `p5_sub_geom`,
  `p6_holder`, `p6_ui`, `p6_geom`, `p7_holder`, `p7_ui`, `phase7_db`,
  `phase7_persist`, `p8_holder`, `p8_ui`, **`p8_1`**, **`p8_2`**, **`p8_3`**,
  **`p8_4`** — and twenty-one
  screenshots: seven from
  `p6_capture.py` (`p6_verify.ps1`: empty state, Dashboard with real numbers,
  list, refused amount, edit mode, confirm dialog, light palette), three
  from `p6_fix_capture.py` (`p6_fix_verify.ps1`: paid/partial/unpaid plan rows
  in dark & light, Dashboard with plans present), three from
  `p7_capture.py` (`p7_verify.ps1`: warning rows + section warning dark/light,
  over-budget Dashboard card) and **four from `p8_capture.py`
  (`p8_verify.ps1`: Reports dark/light + the empty panel dark/light)**, plus
  **two from `p8_1_capture.py`** (`p8_1_verify.ps1`: the Settings screen's new
  salary-month card, dark and light) and **two from `p8_2_capture.py`**
  (`p8_2_verify.ps1`: the Dashboard with only this cycle's money, and the same
  Dashboard refilled after the reset).
- **Phase 8.2 touched NEITHER `main.py` NOR `theme.py`, and no screen's CODE.**
  The window lives in the holder, so the Dashboard, the warnings and Reports all
  followed without a single line of logic changing; only four *comments* were
  edited (three in `dashboard_screen.py`, plus docstrings in `daily_expenses.py`
  and `reports.py`) so the prose still matches the behaviour. LIGHT and DARK
  keep identical key sets — the import-time guard still passes.
- **The 8.2 FIX touched only `fixed_expenses.py` (the change) and comments in
  `daily_expenses.py`** — no screen, no `main.py`, no `theme.py`, no new theme
  values. Its consistency grep found no other "paid"/"progress" computation in
  the app, and **no other suite needed re-expectationing**: every other suite's
  plan fixtures are dated in the current cycle (today or Nov 2026) or carry no
  plan at all, so all 22 stayed green on the first run.
- **Two older suites had to be re-expectationed for Phase 8.2** (their fixtures
  encoded the old all-time rule, not the app changing underneath them):
  `p6_ui_test.py` — three balance assertions, because its fixture deliberately
  logs a 1,500 dated 2026-01-15 to prove date *grouping* in the list (that row
  is now correctly outside the cycle: 117,250 / 116,250 / 116,550 instead of
  115,750 / 114,750 / 115,050); and `p8_holder_test.py` — its fixture dated the
  Rent/Movies/FD rows in January 2026 to prove the split was all-time, so those
  rows moved to **today** (Groceries deliberately stays on last month's final
  day as the out-of-cycle control) and every sum built on them was recomputed
  (split 40,000/2,500/6,000; `month_total == total_spent == 49,700`;
  remaining 50,300; ledger proof 57,700; `spent_this_month(last month) ==
  8,000`). Both suites now document the cycle rule in their own comments.
- **Phase 8.3 touched NEITHER `main.py` NOR `theme.py`.** History is a third
  TAB inside the existing Reports screen, not a new screen, and every widget it
  draws reuses palette keys that already existed — LIGHT and DARK keep
  identical key sets (the import-time guard still passes).
- **Two older assertions were re-expectationed for Phase 8.3** — both pinned
  what the phase deliberately changed, not behaviour drifting underneath:
  `phase8_1_test.py` §6's exact caption string (the caption is now two lines:
  the month, then the date range) and `p8_ui_test.py`'s tab-bar seam count
  (2 → 3 segments; all still `card_bg`, so no seam shows in either palette).
  Everything else stayed green on the first run — including `p8_holder_test`,
  whose `report()` key check is a subset test, so `"history"` arriving is
  invisible to it.
- **Phase 8.4 touched NEITHER `main.py` NOR `theme.py`.** The Compare tab is
  a fourth segment on the existing Reports tab view — no new screen, no shell
  change — and every colour/font/spacing/radius on its widgets reuses keys
  that already existed (its one new value, `COMPARE_NOTE_WRAP = 560`, is a
  layout constant inside `reports_screen.py`, not in the theme); the chart
  follows the exact `_apply_matplotlib_palette()` + per-draw pattern the
  other figures use. LIGHT and DARK keep identical key sets — the import-time
  guard still passes.
- **Two older assertions were re-expectationed for Phase 8.4** — both pinned
  what the phase deliberately changed, not behaviour drifting underneath:
  `phase8_3_test.py`'s tab-title expectation (3 → 4 segments, "Compare"
  last) and `p8_ui_test.py`'s tab-bar seam count (`len(tabbar) == 3` → `4`;
  every segment still `card_bg`, so no seam shows in either palette).
  Everything else stayed green — including `p8_ui_test`'s chart-key checks,
  which only ever visit the Spending and Plan tabs, so the Compare figure
  never exists for them to see.
- **Phase 8.1 touched NEITHER `main.py` NOR `theme.py`.** The shell already had
  all six screens, and the new card needed no new colour/font/spacing/radius —
  LIGHT and DARK still carry identical key sets (the import-time guard still
  passes). The phase is one setting + one helper + one card + three Reports
  functions.
- **`main.py` WAS modified again in Phase 6** — now five screens. Only: the
  `DailyExpensesScreen` import, `("daily", "Daily Expenses")` in `nav_items`,
  `self.screens["daily"] = ...`, the dashboard's
  `on_add_expense=lambda: self.show_screen("daily")` argument, the sidebar
  renumber the fifth button forces (nav rows 2-6, spacer 7, appearance caption
  8, switch 9, status 10, bottom padding 11), plus a docstring line listing the
  nav order. Nothing else changed.
- **`main.py` WAS modified again in Phase 8 — the app now has SIX screens.**
  Only: the `ReportsScreen` import, `"reports": ReportsScreen(self.content)` in
  `self.screens` (no callbacks — the screen only reads), `("reports",
  "Reports")` appended last in `nav_items`, the sidebar renumber the sixth
  button forces (nav rows **2-7**, spacer **8**, appearance caption **9**,
  switch **10**, status **11**, bottom padding **12**), and the docstring's
  nav list. `phase3_test.py` and `p5_main_test.py` had their screen/nav/row
  expectations updated to match (they were the only two suites that asserted
  "five").
- **`app/core/theme.py` was NOT touched in Phase 5, Phase 6, the plan fix, Phase
  6.5, Phase 7, Phase 8, Phase 8.1, Phase 8.2, the 8.2 FIX, Phase 8.3 or Phase
  8.4.**
  No new values were needed in any of them (Phase 6.5 reused the existing
  `danger` / `warning` keys and `body`/`caption`/`value` fonts; Phase 7 added no
  UI whatsoever, so it needed no palette entries at all; Phase 8's charts
  resolve entirely to `card_bg` / `text` / `text_secondary` / `border` /
  `info` / `warning` / `success` / `accent` / `danger` / `success`; Phases 8.1,
  8.2 and the 8.2 FIX changed data and comments only — none of them added a
  widget at all; Phase 8.3 DID add widgets — the History cards and their
  footnote — but every colour/font/spacing/radius on them came from keys that
  already existed; Phase 8.4 likewise added widgets (the two dropdowns, the
  captions, the salary line and the underfilled note) with every visual value
  reused from existing keys, its one new constant being screen-local
  layout); the
  LIGHT/DARK import-time guard still passes. (`main.py` was likewise untouched
  by the plan fix, by Phase 6.5, by Phase 7, by Phase 8.1, by Phase 8.2, by
  the 8.2 FIX, by Phase 8.3 and by Phase 8.4.)
- **Observation, reported, NOT fixed (out of Phase 6 scope):** at MIN_SIZE
  960x620 the *Fixed* Expenses screen's two `weight=2` columns sit at ~97
  physical px — the same Tk grid deficit maths that hit the daily form (whose
  buttons-row fix is documented in the Phase 6 section). Pre-existing since
  Phase 5.
- `app/services/budget_settings.py` gained `BUDGET_ACCENTS` in Phase 5 (it used
  to live in `categories_screen.py`); that screen now imports it and re-exports
  it, so nothing else broke.
- `app/ui/categories_screen.py` was refactored in Phase 5 to import the shared
  `ConfirmDialog` instead of defining its own — behaviour unchanged, its own
  suite still green.
- **SQLite is DONE (Phase 7) — no longer a candidate.** All four holders read
  and write `data/budget.db` behind unchanged public APIs; the schema, the
  FK-vs-name decision, the seeding rules and the decisive close-and-reopen
  result are all in the Phase 7 section above. `data/budget.db` already holds
  your real data (last written 2026-11-11, i.e. before Phase 8) — every suite
  runs on a throwaway file through the `BUDGET_TRACKER_DB` hook, so nothing in
  the battery can seed over or wipe it. Next phase = whatever the user's next
  prompt asks; confirm scope with the user (they have always supplied the
  phase prompt verbatim).
- **`requirements.txt` is NEW (Phase 8) and pins only `matplotlib==3.11.2`.**
  **Pillow is installed** as matplotlib's hard dependency **but deliberately
  left out of `requirements.txt`** — screenshots go ctypes `PrintWindow` → BMP
  → PowerShell `System.Drawing` → PNG, so the project never imports it. If a
  future phase needs Pillow it must be added *then*, with a comment saying why.
- **Pre-existing, reported, NOT a Phase 8 regression:** driving the entry forms
  and switching screens within the same tick makes CustomTkinter's internal
  `after(… focus_set)` raise `bad window path name …ctkentryN.!entry`.
  `p7_capture.py` hits it on the Daily Expenses form and `p8_capture.py` on the
  Fixed Expenses one; both still complete and save their screenshots.
- **Known, pre-existing, not Phase 5's or 6's:** dark `text_on_accent on
  accent` measures **4.47:1** and on `accent_hover` **3.61:1** — below 4.5:1 on
  the primary Add/Save button. Present since Phase 3; reported, not yet changed.
- Nothing is committed — the folder is not a git repository.
