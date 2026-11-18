"""
dashboard_screen.py - the Dashboard screen (Phase 3: real settings).

WHAT CHANGED FROM PHASE 2
  * Salary and the three allocated amounts are no longer hardcoded -
    they are read from app/services/budget_settings.py, the shared
    holder the Settings screen writes to (see _load_from_settings).
  * The settings holder notifies us on save (subscribe), so new values
    appear here without main.py having to do anything.
  * The remaining balance number is colour-coded by how much of the
    salary is left (green / amber / red - see _remaining_color_key).

WHAT CHANGED IN PHASE 6 - the numbers are finally REAL (FIXED 2026-11-11)
  * The Phase 2/3 SPENT placeholder dict is GONE. Every spent figure now
    comes from daily_expenses.get_spent_by_budget() - the cascade, which
    counts DAILY expenses only: a fixed expense is the monthly PLAN, and
    a plan is never money spent (see daily_expenses.py and the plan
    section of fixed_expenses.py).
  * The salary card's remaining balance is
    daily_expenses.get_remaining_balance() = salary - daily spending, so
    logging a daily expense is the ONLY thing that moves it. Adding or
    editing a fixed expense changes nothing on this screen - which is
    exactly why the screen no longer subscribes to fixed_expenses.
  * PHASE 8.2 (2026-11-17): those same three reads (spent, remaining,
    over-budget) now count the CURRENT SALARY CYCLE only, so every
    figure here resets when the cycle rolls over. NOT ONE LINE of this
    screen changed for it - the window lives in daily_expenses, which
    is the whole point of keeping the maths in the holder. Only these
    comments were updated to say so.
  * The colour-coded balance uses that same corrected remaining
    (see _remaining_color_key / _load_from_settings).
  * The screen subscribes to TWO holders, because two things can move a
    number on this screen:
        budget_settings - a new plan (as before),
        daily_expenses  - logging / editing / deleting an expense.
    Each holder only notifies its own subscribers, so each gets its own
    subscribe() call. The dashboard never "listens" to anything else: it
    just re-reads the holders whenever told to, which is why logging an
    expense on another screen updates these cards while they are hidden.

WHAT CHANGED IN PHASE 7 - over-budget cards warn (warning 3)
  * When a budget's SPENT passes its ALLOCATION, its card now says so
    out loud instead of quietly showing "208% used" in the normal
    colour: the remaining figure, the percentage and the progress bar
    all turn DANGER red, the bar caps at 100% (a bar cannot draw 208%)
    while the percentage keeps the TRUE figure, and a short label
    ("Over by Rs. 26,000") appears above the bar. Healthy cards are
    untouched - this state is added ON TOP of the existing colour
    logic, never instead of it (the salary card's green/amber/red
    balance rules are unchanged).
  * The comparison itself is not done here: daily_expenses.
    get_over_budget() returns, per budget, allocated / spent / over /
    over_by, and this screen only paints what it says (comparison
    maths belongs in the holders).
  * refresh_theme() re-reads the stored overrun (refs["over_by"]) so
    the red state survives a dark/light flip - without that the flip
    would repaint the card back to normal and the warning would
    disappear until the next expense was logged.

CONTRACT WITH main.py (unchanged since Phase 1)
  * every colour / font / spacing / radius comes from app.core.theme
  * refresh_theme() re-applies the whole palette to EVERY widget here,
    so the sidebar's dark/light switch repaints the dashboard live
  * layout uses grid weights, so the cards stretch when the window resizes

WHAT THE SCREEN SHOWS (top to bottom)
  1. Greeting header    - time-of-day greeting ("Good morning" before 12 PM,
                          "Good afternoon" until 5 PM, "Good evening" after)
                          plus a dated subtitle line
  2. Salary card        - accent-coloured: salary + colour-coded balance
  3. Three budget cards - Needs / Wants / Savings, each with allocated,
                          spent, remaining and a progress bar - all REAL
  4. Add Expense button - opens the Daily Expenses screen. main.py passes
                          the callback (on_add_expense=...); building this
                          screen WITHOUT one (as a test does) leaves the
                          button harmless.
"""

import datetime as dt

import customtkinter as ctk

from app.core import theme
# fixed_expenses is deliberately NOT imported here (plan fix): a fixed
# expense is the plan, never money spent, so it cannot move any number
# on this screen and the dashboard has nothing to hear from it.
from app.services import budget_settings, daily_expenses

# (display name, theme colour key, settings key) - this is UI mapping
# only: which label and accent each budget gets. The NUMBERS live in
# budget_settings (allocations) and daily_expenses (spend).
BUDGET_CARDS = (
    ("Needs",   "info",    "needs"),
    ("Wants",   "warning", "wants"),
    ("Savings", "success", "savings"),
)


def _header_texts(now: dt.datetime) -> tuple[str, str]:
    """Return (greeting, subtitle) for the given moment.

    The greeting follows the spec exactly:
        before 12:00       -> "Good morning"
        12:00 to 16:59     -> "Good afternoon"
        17:00 and later    -> "Good evening"
    The subtitle carries today's date so the header feels alive without
    reading any real budget data.
    """
    if now.hour < 12:
        greeting = "Good morning ☀️"
    elif now.hour < 17:
        greeting = "Good afternoon 🌤️"
    else:
        greeting = "Good evening 🌙"

    # "%d" would zero-pad the day ("07"), so build the date by hand.
    date_str = f"{now:%A}, {now.day} {now:%B} {now.year}"
    subtitle = f"{date_str} · Here's your monthly snapshot at a glance."
    return greeting, subtitle


class DashboardScreen(ctk.CTkFrame):
    """The landing screen: greeting, salary snapshot, budget cards."""

    def __init__(self, master, on_add_expense=None, **kwargs):
        # Start from the current palette instead of a hardcoded colour.
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)
        # Fraction of the salary still available (0.0 - 1.0). Written by
        # _load_from_settings(), read by refresh_theme() to colour the
        # remaining balance. Declared here so it always exists.
        self._remaining_ratio = 0.0
        # What the "+ Add Expense" button runs. main.py hands over
        # `lambda: self.show_screen("daily")`, so this screen never needs
        # to know how the shell navigates; a test that builds the screen
        # on its own passes nothing and the button stays harmless.
        self._on_add_expense_callback = on_add_expense
        self._build()
        # Fill the widgets with the holders' current numbers, then paint.
        self._load_from_settings()
        self.refresh_theme()
        # From now on, any change that can move a number here runs
        # _load_from_settings() again (each holder notifies its own
        # subscribers), so this screen is always up to date - including
        # while it is hidden behind another screen:
        #   budget_settings - a new plan (Phase 3);
        #   daily_expenses  - an expense was logged / edited / deleted
        #                     (Phase 6), or reconcile() relinked one.
        # No fixed_expenses subscription: plans never change a dashboard
        # figure (plan fix), so there is nothing for it to tell us.
        budget_settings.subscribe(self._load_from_settings)
        daily_expenses.subscribe(self._load_from_settings)

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        """Create the widgets once. Colours are applied in refresh_theme()."""
        pad = theme.spacing("lg")
        now = dt.datetime.now()
        greeting, subtitle = _header_texts(now)

        # One column fills the width. Row 4 (the budget cards) is the only
        # row allowed to grow, so cards absorb extra window height while
        # the header, salary card and button keep their natural size.
        #   rows: 0 greeting | 1 subtitle | 2 salary card
        #         3 heading  | 4 budget cards (weight 1) | 5 button
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # -- 1. greeting header --------------------------------------------
        self._greeting = ctk.CTkLabel(
            self,
            text=greeting,
            font=theme.font("title"),
            anchor="w",  # left-aligned, like a page heading
        )
        self._greeting.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._greeting_sub = ctk.CTkLabel(
            self,
            text=subtitle,
            font=theme.font("subtitle"),
            anchor="w",
        )
        self._greeting_sub.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # -- 2. salary summary card ----------------------------------------
        # Accent-filled so it reads as the most important object on screen.
        # border_width=0: the fill itself separates it from the background.
        self._salary_card = ctk.CTkFrame(
            self,
            corner_radius=theme.radius("lg"),
            border_width=0,
        )
        self._salary_card.grid(
            row=2, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("lg")),
        )
        # Column 0 takes the leftover width, so the right-hand block stays
        # pinned to the right edge however wide the window gets.
        self._salary_card.grid_columnconfigure(0, weight=1)
        self._salary_card.grid_columnconfigure(1, weight=0)

        # Left block: the salary itself.
        left = ctk.CTkFrame(self._salary_card, fg_color="transparent")
        left.grid(
            row=0, column=0, sticky="w",
            padx=(theme.spacing("lg"), theme.spacing("sm")),
            pady=theme.spacing("md"),
        )
        self._salary_caption = ctk.CTkLabel(
            left, text="TOTAL MONTHLY SALARY",
            font=theme.font("caption"), anchor="w",
        )
        self._salary_caption.pack(anchor="w")
        self._salary_amount = ctk.CTkLabel(
            left, text="",  # filled by _load_from_settings()
            font=theme.font("display"), anchor="w",
        )
        self._salary_amount.pack(anchor="w", pady=(theme.spacing("xs"), 0))

        # Right block: what is left. Same shape, right-aligned.
        right = ctk.CTkFrame(self._salary_card, fg_color="transparent")
        right.grid(
            row=0, column=1, sticky="e",
            padx=(theme.spacing("sm"), theme.spacing("lg")),
            pady=theme.spacing("md"),
        )
        self._salary_remaining_caption = ctk.CTkLabel(
            right, text="REMAINING BALANCE",
            font=theme.font("caption"), anchor="e", justify="right",
        )
        self._salary_remaining_caption.pack(anchor="e")
        self._salary_remaining_amount = ctk.CTkLabel(
            right, text="",  # filled (and colour-coded) by _load_from_settings()
            font=theme.font("display"), anchor="e", justify="right",
        )
        self._salary_remaining_amount.pack(anchor="e", pady=(theme.spacing("xs"), 0))

        # -- 3. section heading above the budget cards ---------------------
        # Uppercase caption, same style as the sidebar's "APPEARANCE".
        self._budgets_heading = ctk.CTkLabel(
            self,
            text="MONTHLY BUDGETS",
            font=theme.font("caption"),
            anchor="w",
        )
        self._budgets_heading.grid(
            row=3, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("sm")),
        )

        # -- 4. the three budget cards, side by side -----------------------
        # A transparent sub-frame with its own 3-column grid: the columns
        # share width equally (uniform=) and all grow with the window, so
        # the header rows above stay full-width instead of being squeezed
        # into one third of the screen.
        self._cards_row = ctk.CTkFrame(self, fg_color="transparent")
        self._cards_row.grid(
            row=4, column=0, sticky="nsew",
            padx=pad, pady=(0, theme.spacing("lg")),
        )
        for col in range(3):
            # uniform="budget" forces all three columns to the same width.
            self._cards_row.grid_columnconfigure(col, weight=1, uniform="budget")
        self._cards_row.grid_rowconfigure(0, weight=1)  # cards fill the height

        # Each builder returns the widget references refresh_theme() needs.
        self._budget_cards: list[dict] = []
        for col, (name, color_key, settings_key) in enumerate(BUDGET_CARDS):
            refs = self._build_budget_card(
                self._cards_row, name, color_key, settings_key
            )
            # sm gap between cards, flush against the right screen padding.
            refs["frame"].grid(
                row=0, column=col, sticky="nsew",
                padx=(0, theme.spacing("sm")) if col < 2 else 0,
            )
            self._budget_cards.append(refs)

        # -- 5. Add Expense button -----------------------------------------
        # Accent-filled primary action, full width. It OPENS the Daily
        # Expenses screen - main.py wired that up when it built this
        # screen (on_add_expense=...). Without a callback (a bare test
        # construction) the button simply does nothing.
        self._add_button = ctk.CTkButton(
            self,
            text="+  Add Expense",
            font=theme.font("section"),
            # CTA height as a sum of theme steps: xl (36) + sm (10) = 46.
            height=theme.spacing("xl") + theme.spacing("sm"),
            corner_radius=theme.radius("md"),
            border_width=0,
            command=self._on_add_expense,
        )
        self._add_button.grid(
            row=5, column=0, sticky="ew",
            padx=pad, pady=(0, pad),
        )

    def _build_budget_card(
        self,
        parent,
        name: str,
        color_key: str,
        settings_key: str,
    ) -> dict:
        """Build ONE budget card's widgets and return the refs that
        refresh_theme() and _load_from_settings() need.

        Row layout inside the card. Row 4 is an empty spacer with weight 1
        that pushes the progress bar to the bottom, so all three bars stay
        aligned even when the cards grow taller on window resize:

            0  ●  Needs              (colour dot + name)
            1  ALLOCATED            (small caption)
            2  Rs. 60,000           (big amount)
            3  SPENT / REMAINING    (two mini columns)
            4  <flexible spacer>    (weight 1 - absorbs extra height)
            5  36% used
            6  Over by Rs. 26,000   (danger - ONLY when over budget,
                                     gridded on demand by _load_from_
                                     settings, Phase 7)
            7  [====------] progress bar

        The amount rows are created EMPTY on purpose: every number is
        filled in by _load_from_settings() (at startup and after every
        change to the plan or to the expenses), so this builder only
        handles structure. What it does store in the returned dict:
          * color_key    - palette key that accents the card (info /
                           warning / success), re-read on theme flips
          * settings_key - which budget in the holder supplies numbers
                           (used by _load_from_settings to index both
                           the allocations and the spent figures)
          * over_by      - the card's overrun in rupees (0 = not over),
                           written by _load_from_settings() and re-read
                           by refresh_theme() so a theme flip keeps the
                           danger state (Phase 7)
        """
        pad = theme.spacing("md")  # inner padding of every budget card

        card = ctk.CTkFrame(
            parent,
            corner_radius=theme.radius("lg"),
            border_width=1,  # 1px outline, coloured in refresh_theme()
        )
        # Column 1 stretches so the name row can push against it.
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(4, weight=1)  # only the spacer row grows

        # Row 0: colour dot + card name.
        dot = ctk.CTkLabel(card, text="●", font=theme.font("section"), anchor="w")
        dot.grid(row=0, column=0, sticky="w", padx=(pad, 0), pady=(pad, 0))

        name_label = ctk.CTkLabel(card, text=name, font=theme.font("section"), anchor="w")
        name_label.grid(
            row=0, column=1, sticky="w",
            padx=(theme.spacing("xs"), 0), pady=(pad, 0),
        )

        # Rows 1-2: how much this budget owns.
        alloc_caption = ctk.CTkLabel(card, text="ALLOCATED", font=theme.font("caption"), anchor="w")
        alloc_caption.grid(
            row=1, column=0, columnspan=2, sticky="w",
            padx=pad, pady=(theme.spacing("md"), 0),
        )
        alloc_amount = ctk.CTkLabel(card, text="", font=theme.font("amount"), anchor="w")
        alloc_amount.grid(
            row=2, column=0, columnspan=2, sticky="w",
            padx=pad, pady=(theme.spacing("xs"), 0),
        )

        # Row 3: spent (left) and remaining (right). Both inner columns
        # have weight 1, so the two mini blocks hug the card's edges.
        # The values start empty - _load_from_settings() fills them.
        stats = ctk.CTkFrame(card, fg_color="transparent")
        stats.grid(
            row=3, column=0, columnspan=2, sticky="ew",
            padx=pad, pady=(theme.spacing("md"), 0),
        )
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)

        spent_caption = ctk.CTkLabel(stats, text="SPENT", font=theme.font("caption"), anchor="w")
        spent_caption.grid(row=0, column=0, sticky="w")
        spent_value = ctk.CTkLabel(stats, text="", font=theme.font("value"), anchor="w")
        spent_value.grid(row=1, column=0, sticky="w", pady=(theme.spacing("xs"), 0))

        remain_caption = ctk.CTkLabel(stats, text="REMAINING", font=theme.font("caption"), anchor="e", justify="right")
        remain_caption.grid(row=0, column=1, sticky="e")
        remain_value = ctk.CTkLabel(stats, text="", font=theme.font("value"), anchor="e", justify="right")
        remain_value.grid(row=1, column=1, sticky="e", pady=(theme.spacing("xs"), 0))

        # Row 5: percentage label (recoloured to the card's accent, or
        # to danger when the budget is over - see _load_from_settings).
        pct_label = ctk.CTkLabel(card, text="", font=theme.font("value"), anchor="w")
        pct_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=pad)

        # Row 6: the over-budget warning line ("Over by Rs. 26,000").
        # Phase 7 - created UNGRIDDED on purpose: _load_from_settings()
        # grids it only when the budget is actually over, and forgets it
        # otherwise, so the common case pays no dead space for a label
        # that says nothing. Colours live in both paint paths (it turns
        # danger either way; see refresh_theme).
        over_label = ctk.CTkLabel(
            card, text="", font=theme.font("caption"),
            text_color=theme.color("danger"), anchor="w",
        )

        # Row 7: the progress bar itself.
        #   height = the "sm" spacing step (10px) - no magic numbers
        #   corner_radius = half of that, so the ends come out pill-shaped
        #   bar width/height are stretched by the grid, and CTkProgressBar
        #   redraws itself on every <Configure> event (its base class
        #   binds one), so the bar follows the card when the window resizes.
        bar = ctk.CTkProgressBar(
            card,
            height=theme.spacing("sm"),
            corner_radius=theme.radius("sm") // 2,
            border_width=0,
            mode="determinate",
        )
        bar.grid(
            row=7, column=0, columnspan=2, sticky="ew",
            padx=pad, pady=(theme.spacing("xs"), pad),
        )
        # The fill value is NOT set here - _load_from_settings() computes
        # it (spent / allocated) so it tracks the user's real settings.

        return {
            # widgets refresh_theme() repaints:
            "frame": card,
            "dot": dot,
            "name": name_label,
            "alloc_caption": alloc_caption,
            "alloc_amount": alloc_amount,
            "spent_caption": spent_caption,
            "spent_value": spent_value,
            "remain_caption": remain_caption,
            "remain_value": remain_value,
            "percent": pct_label,
            "over_label": over_label,
            "bar": bar,
            # not widgets - configuration both methods re-read:
            "color_key": color_key,       # which palette key accents this card
            "settings_key": settings_key, # which budget supplies its numbers
            "over_by": 0, # 0 = not over budget; set by _load_from_
                          # settings() from get_over_budget(). refresh_
                          # theme() re-reads it so a dark/light flip
                          # keeps the danger state instead of wiping it.
        }

    # -- data ---------------------------------------------------------------

    def _load_from_settings(self) -> None:
        """Read the holders and put every number on the screen.

        Runs once at startup, then again whenever ANY holder this screen
        depends on notifies its subscribers: a new plan (budget_settings)
        or a logged / edited / deleted daily expense (daily_expenses).
        Both call this same method, because both move the same figures -
        and they do it even while this screen is hidden, so it is always
        ready to show. Fixed expenses are NOT one of them: they are the
        plan, and a plan never moves money (plan fix).
        """
        salary = budget_settings.get_salary()
        allocations = budget_settings.get_allocations()

        # -- salary card ---------------------------------------------------
        # REAL money: the cascade's top figure - salary minus this salary
        # cycle's daily expenses (Phase 8.2 window; it used to subtract
        # every expense ever logged). Fixed expenses never touch it; only
        # logging spending inside the current cycle can lower it (floored
        # at zero inside the holder; see daily_expenses.get_remaining_balance).
        remaining = daily_expenses.get_remaining_balance()

        self._salary_amount.configure(text=f"Rs. {salary:,}")
        self._salary_remaining_amount.configure(text=f"Rs. {remaining:,}")

        # Fraction of the salary still available (0.0 - 1.0). Stored for
        # refresh_theme(), which paints the balance green/amber/red from
        # it whenever the palette is (re)applied.
        self._remaining_ratio = (remaining / salary) if salary > 0 else 0.0
        self._salary_remaining_amount.configure(
            text_color=theme.color(self._remaining_color_key())
        )

        # -- budget cards --------------------------------------------------
        # Spent = daily expenses logged under this budget IN THE CURRENT
        # SALARY CYCLE (Phase 8.2; plans never enter it), read from the
        # cascade helper - never accumulated here, so every card can only
        # ever agree with the ledger the other screens write to, and the
        # whole row resets with the cycle without this loop changing.
        spent_by_budget = daily_expenses.get_spent_by_budget()
        # The over-budget COMPARISON also lives in a holder (Phase 7):
        # get_over_budget() says, per budget, whether spent passed the
        # allocation and by how much. This loop only paints what it is
        # told - the numbers above and the arithmetic below are all
        # unchanged; this adds the red state on top of them.
        over_by_budget = daily_expenses.get_over_budget()
        for refs in self._budget_cards:
            key = refs["settings_key"]
            allocated = allocations[key]
            spent = spent_by_budget[key]
            # Can go negative if the user shrinks a budget below what is
            # already spent against it - shown honestly (Rs. -1,200 is
            # information, not a bug).
            left = allocated - spent
            # Guard: a 0% budget divides by zero below.
            used = round(spent / allocated * 100) if allocated else 0

            # Phase 7: the over-budget state. over_by is stored on the
            # refs so refresh_theme() can re-apply the same red on a
            # dark/light flip (it repaints these three widgets too).
            over = over_by_budget[key]
            refs["over_by"] = over["over_by"]   # 0 = not over
            over_budget = over["over"]
            accent = theme.color(refs["color_key"])

            refs["alloc_amount"].configure(text=f"Rs. {allocated:,}")
            refs["spent_value"].configure(text=f"Rs. {spent:,}")
            refs["remain_value"].configure(
                text=f"Rs. {left:,}",
                # A negative remaining is exactly the over-budget case:
                # the figure turns danger instead of plain text.
                text_color=(theme.color("danger") if over_budget
                            else theme.color("text")),
            )
            refs["percent"].configure(
                # The TRUE figure stays on purpose (208% used is the
                # information the user needs) - only its colour turns
                # danger when the budget is over.
                text=f"{used}% used",
                text_color=(theme.color("danger") if over_budget
                            else accent),
            )
            # The bar is capped at 100% on purpose: a bar cannot draw
            # 208%, so it fills FULL and DANGER-red to say "past the
            # limit" (an overflow stub would need a second scale and
            # reads slower). The min() makes the cap explicit rather
            # than leaning on CTkProgressBar.set()'s own clamp.
            refs["bar"].set(min(used, 100) / 100)
            refs["bar"].configure(
                progress_color=(theme.color("danger") if over_budget
                                else accent),
            )
            # The short overrun label ("Over by Rs. 26,000"), gridded
            # into row 6 only while it has something to say; forgotten
            # otherwise so a healthy card pays no dead space for it.
            if over_budget:
                refs["over_label"].configure(
                    text=f"Over by Rs. {over['over_by']:,}")
                refs["over_label"].grid(
                    row=6, column=0, columnspan=2, sticky="w",
                    padx=theme.spacing("md"),
                    pady=(theme.spacing("xs"), 0),
                )
            else:
                refs["over_label"].grid_forget()

    def _remaining_color_key(self) -> str:
        """Palette key for the remaining-balance number, by how much of
        the salary is left (thresholds from the Phase 3 spec - UNCHANGED):
            above 50%   -> "balance_good" (green)
            50% to 26%  -> "balance_warn" (amber)
            25% or less -> "balance_bad"  (red)

        The keys are always balance_* - the ACTIVE PALETTE decides what
        they resolve to (see theme.py): light mode uses the banner-tuned
        mint / bright yellow plus the lighter #F87171 red, dark mode keeps
        the original green / amber and the deeper #DC2626 red (the two
        reds are deliberately swapped between the modes). Every call site
        is inside colour re-paints (_load_from_settings and
        refresh_theme), so the choice is re-made on each dark/light flip.
        """
        ratio = self._remaining_ratio
        if ratio > 0.50:
            return "balance_good"
        if ratio > 0.25:
            return "balance_warn"
        return "balance_bad"

    # -- behaviour ----------------------------------------------------------

    def _on_add_expense(self) -> None:
        """Run the "Add Expense" action wired up by main.py.

        main.py builds this screen as
        DashboardScreen(self.content, on_add_expense=lambda: self.show_screen("daily")),
        so pressing the button navigates to the Daily Expenses screen -
        the sidebar screen that owns the log, edit and delete flow (see
        app/ui/daily_expenses_screen.py for why a screen rather than a
        dialog). This screen never learns how the shell switches pages;
        it just calls what it was given.

        No callback (a test constructing the screen on its own) means
        the button is inert rather than an error.
        """
        if self._on_add_expense_callback is not None:
            self._on_add_expense_callback()

    # -- theming ------------------------------------------------------------

    def refresh_theme(self) -> None:
        """Re-read every colour from theme.py and apply it to this screen.

        Called once at startup and again each time the dark/light switch
        is flipped (main.py walks every screen and calls this), so every
        widget created in _build() must be configured here - anything
        missed keeps the old mode's colour.
        """
        # Screen background.
        self.configure(fg_color=theme.color("bg"))

        # Greeting: recompute the text too, so the greeting is still right
        # if the app is left open across noon / 5 PM, or after a toggle.
        greeting, subtitle = _header_texts(dt.datetime.now())
        self._greeting.configure(text=greeting, text_color=theme.color("text"))
        self._greeting_sub.configure(text=subtitle, text_color=theme.color("text_secondary"))

        # Salary card: accent background, white-ish text on top.
        # The two caption colours are the special "on accent" pair.
        self._salary_card.configure(fg_color=theme.color("accent"))
        self._salary_caption.configure(text_color=theme.color("text_on_accent_secondary"))
        self._salary_amount.configure(text_color=theme.color("text_on_accent"))
        self._salary_remaining_caption.configure(text_color=theme.color("text_on_accent_secondary"))
        # The remaining BALANCE is coloured by how much is left (green >
        # 50%, amber 50-26%, red <= 25%) via the balance_good/warn/bad
        # keys - each palette holds its own values for them (see theme.py:
        # banner-tuned mint/yellow + the lighter red in light, the original
        # green/amber + the deeper red in dark). Applying it here is what
        # makes the colour survive
        # a dark/light flip; _load_from_settings() applies the same rule
        # whenever the numbers themselves change.
        self._salary_remaining_amount.configure(
            text_color=theme.color(self._remaining_color_key())
        )

        self._budgets_heading.configure(text_color=theme.color("text_secondary"))

        # The three budget cards - same recipe, different accent per card.
        for refs in self._budget_cards:
            accent = theme.color(refs["color_key"])  # info / warning / success
            refs["frame"].configure(
                fg_color=theme.color("card_bg"),
                border_color=theme.color("border"),
            )
            refs["dot"].configure(text_color=accent)
            refs["name"].configure(text_color=theme.color("text"))
            refs["alloc_caption"].configure(text_color=theme.color("text_secondary"))
            refs["alloc_amount"].configure(text_color=theme.color("text"))
            refs["spent_caption"].configure(text_color=theme.color("text_secondary"))
            refs["spent_value"].configure(text_color=theme.color("text"))
            refs["remain_caption"].configure(text_color=theme.color("text_secondary"))
            # Phase 7 - the over-budget (danger) state must survive a
            # theme flip too: _load_from_settings() stored the card's
            # overrun in refs["over_by"] (0 = healthy), and the SAME
            # three widgets it reddens - remaining figure, percentage,
            # bar - are reddened here when it is set. Without this the
            # flip would repaint them back to plain text/accent and the
            # warning would silently vanish until the next expense.
            over = bool(refs.get("over_by"))
            danger = theme.color("danger")
            refs["remain_value"].configure(
                text_color=danger if over else theme.color("text"))
            refs["percent"].configure(
                text_color=danger if over else accent)
            refs["bar"].configure(
                fg_color=theme.color("surface"),          # the empty track
                progress_color=danger if over else accent,  # filled part
            )
            # The overrun label only exists while over, but its colour
            # is re-read here anyway - it is a widget created in _build,
            # and every widget gets its colour from this method.
            refs["over_label"].configure(text_color=danger)

        # Add Expense button: accent face, accent-hover on hover.
        self._add_button.configure(
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("text_on_accent"),
        )
