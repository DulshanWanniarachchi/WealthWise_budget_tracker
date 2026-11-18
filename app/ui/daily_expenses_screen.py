"""
daily_expenses_screen.py - the Daily Expenses screen (Phase 6).

WHERE IT LIVES, AND WHY A SIDEBAR SCREEN (not a dialog)
  The Dashboard's "+ Add Expense" button opens THIS screen. Three
  reasons a screen won over a dialog:

    * this flow is a CRUD list - log, edit, delete, row by row - which
      is exactly the shape Categories (Phase 4) and Fixed Expenses
      (Phase 5) gave their own sidebar screens. A dialog would have to
      contain a scrollable list, an edit mode and a nested delete
      confirmation - a whole app inside a window that was designed for
      "Are you sure?";
    * main.py repaints every screen on a dark/light flip by walking
      self.screens. A CTkToplevel is not in that walk, so an open
      dialog would go stale the moment the switch is flipped (and
      CustomTkinter's toplevels start withdrawn and need their own
      grab handling);
    * a screen costs main.py exactly: one import, one nav tuple, one
      screens entry, one renumber of the rows below the nav - the same
      four-line bill Phases 4 and 5 paid.

  main.py wires the Dashboard button as
  DashboardScreen(..., on_add_expense=lambda: self.show_screen("daily")).

HOW THE LIST IS GROUPED: BY DATE, DESCENDING (the choice, and why)
  Day sections - "Today", "Yesterday", then full dates - each with its
  own subtotal, newest day first and newest expense first inside it.

    * a spending log is read as "what did I spend today / yesterday";
      that is the question people open this screen with, and grouping
      by budget would answer a question the Dashboard already answers
      on its three cards;
    * the budget is still on EVERY row - the chip leads with it - so
      grouping by day does not hide where the money came from;
    * the per-day subtotal is the local echo of the Dashboard: it sums
      the same ledger the cascade maths reads (see daily_expenses.py).

WHAT A ROW SHOWS:  Rs. 450   [Wants -> Movies]   note   Edit  Delete
  * amount first (it is the headline), aligned by ONE shared column
    width for the whole list - _align_amount_columns does for the
    amounts what the Fixed Expenses screen does for its names;
  * the chip is the FULL PATH: budget -> category -> sub-item, because
    the list is grouped by date and the row therefore has to say which
    pot it came from on its own. Uncategorised rows show the path in
    the warning colour with no fill - the same treatment (and contrast
    reasoning) as the Fixed Expenses screen;
  * the note is truncated at 60 characters for the row only; Edit shows
    the whole thing.

THE SUB-ITEM PICKER IS CONDITIONAL - same proven pattern as Phase 5:
  its own rows (3/4) under the main controls, HIDDEN with grid_remove
  while the selected category has no sub-items, "— None —" always first,
  and a hidden picker means "category level only".

DELETE CONFIRMS FIRST - the shared ConfirmDialog from app/widgets.

AUTO-CAPITALISE - the note field is bound with
  text_rules.bind_gentle_capitalise(): first letter up as the user
  types, the rest exactly as typed, new entries only. The HOLDER applies
  the same rule on add/update (see daily_expenses._clean_note), so the
  two can never disagree.

FORM STATE LIVES IN StringVars, NOT IN THE WIDGETS - widgets are
  destroyed on every rebuild (a rebuild is how refresh_theme() stays
  complete), the vars are not, so a rebuild never loses what the user
  typed. That is why the close/restore dance in _submit exists: a
  SUCCESS rebuilds the form (vars must already be blank), a REFUSAL
  does not (vars must be put back).
"""

import datetime as dt

import customtkinter as ctk

from app.core import theme, text_rules
from app.services import budget_settings, category_settings, daily_expenses
from app.widgets.confirm_dialog import ConfirmDialog

# ---------------------------------------------------------------------------
# CONTROL SIZES, IN PIXELS.
# Same precedent as the Settings / Fixed Expenses screens: control
# dimensions are not colours / fonts / spacing / radius, so they stay
# here and NOT in theme.py.
# ---------------------------------------------------------------------------
FIELD_H = 34          # entries and dropdowns share it, so the row lines up
BUTTON_W_PRIMARY = 132   # "Log expense" / "Save changes"
BUTTON_W_SECONDARY = 84  # "Clear" / "Cancel"
BUTTON_H = 34

NOTE_DISPLAY_MAX = 60    # characters shown in a row before it is cut

# Shown in the category dropdown when the selected budget has no
# categories at all. Selectable but never storable - submitting it makes
# the holder raise the real, more helpful error message.
NO_CATEGORIES = "No categories yet"

# Shown as the FIRST entry of the sub-item dropdown: the expense
# attaches at category level only (the default). Translated to None
# before it ever reaches the holder - the holder knows nothing about how
# a picker spells "none".
NO_SUB_ITEM = "— None —"


# ---------------------------------------------------------------------------
# SMALL HELPERS (module level: they need no screen state)
# ---------------------------------------------------------------------------

def _key_for_label(label: str) -> str:
    """Map a budget's display name back to its key.

    The pickers show "Needs" / "Wants" / "Savings" because that is what
    the user reads; the holder only accepts the keys.
    """
    for key in budget_settings.BUDGET_KEYS:
        if budget_settings.BUDGET_LABELS[key] == label:
            return key
    return budget_settings.BUDGET_KEYS[0]


def _category_options(budget: str) -> list:
    """The category names available under one budget, for a dropdown.

    Returns [NO_CATEGORIES] when the budget is empty, because a
    CTkOptionMenu with zero values cannot be opened at all and would
    look simply broken. Submitting the placeholder then produces the
    holder's proper "add one on the Categories screen first" message.
    """
    names = [node["name"] for node in category_settings.get_categories(budget)]
    return names or [NO_CATEGORIES]


def _sub_item_options(budget: str, category: str) -> list:
    """The sub-item names under one category, for a dropdown.

    Returns [] - never a placeholder - because an empty list is the
    SIGNAL the form acts on: no sub-items means the sub-item row is not
    shown at all (see _sync_sub_item_field).
    """
    if not category or category == NO_CATEGORIES:
        return []
    try:
        return category_settings.get_items(budget, category)
    except ValueError:
        # The category was deleted or renamed in another screen between
        # two rebuilds. The holder will report it properly on submit;
        # here we just have nothing to offer.
        return []


def _day_heading(iso_date: str) -> str:
    """Human heading for an ISO date: "Today" / "Yesterday" / full date.

    Built from dt.date.today() at CALL time, not cached: the app may be
    left open across midnight, and a heading that says "Today" about
    yesterday would be worse than a long date.
    """
    day = dt.date.fromisoformat(iso_date)
    today = dt.date.today()
    if day == today:
        return "Today"
    if day == today - dt.timedelta(days=1):
        return "Yesterday"
    # "%d" would zero-pad the day, so the date is built by hand - the
    # same trick the Dashboard's subtitle uses.
    return f"{day:%A}, {day.day} {day:%B} {day.year}"


def _group_by_day(expenses: list) -> list:
    """Sort newest-first and bundle into [(iso_date, [expense, ...]), ...].

    Sort key is (date, id) DESCENDING, so the newest DAY comes first and,
    within a day, the most recently LOGGED expense comes first - which is
    what "most recent first" means when you have just added one.
    """
    ordered = sorted(expenses, key=lambda e: (e["date"], e["id"]), reverse=True)
    groups: list = []
    for expense in ordered:
        if not groups or groups[-1][0] != expense["date"]:
            groups.append((expense["date"], []))
        groups[-1][1].append(expense)
    return groups


# ---------------------------------------------------------------------------
# THE SCREEN
# ---------------------------------------------------------------------------

class DailyExpensesScreen(ctk.CTkFrame):
    """Screen for logging one-off spending, and the cascade's feed."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)
        self._build()
        # Two subscriptions, on purpose:
        #   daily_expenses   - an expense was added / edited / deleted, or
        #                      reconcile() just uncategorised one;
        #   category_settings - the category tree changed, so the form's
        #                      dropdown options (and the chips in the
        #                      list) are now out of date.
        # The holders ignore duplicate registrations of the same callable.
        daily_expenses.subscribe(self._reload)
        category_settings.subscribe(self._reload)
        self.refresh_theme()   # paints the chrome AND builds form + list

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        """Create the static chrome once. Colours are applied in
        refresh_theme(); the form and the list are built by _reload()."""
        pad = theme.spacing("lg")

        # --- state, read by _reload() while it decides what to render -----
        self._message_kind = ""       # "" | "error" | "success"
        self._editing = None          # id of the expense being edited, or None
        self._dialog = None           # keeps a confirm box alive (no GC mid-air)

        # Form state. StringVars, not widget values: the widgets are
        # destroyed on every rebuild, the vars are not.
        self._amount_var = ctk.StringVar(value="")
        self._budget_var = ctk.StringVar(value=budget_settings.BUDGET_LABELS["needs"])
        self._category_var = ctk.StringVar(value="")
        self._sub_item_var = ctk.StringVar(value=NO_SUB_ITEM)
        # Default date = today, filled in on every clear as well - the
        # "date" the user most often means.
        self._date_var = ctk.StringVar(value=dt.date.today().isoformat())
        self._note_var = ctk.StringVar(value="")

        # The form widgets handlers need by reference (the rest are
        # built and forgotten by _build_form). Reassigned on every
        # rebuild. The sub-item pair starts as None because it is
        # created ungridded - _sync_sub_item_field() decides whether it
        # is on screen at all.
        self._amount_entry = None
        self._category_menu = None
        self._sub_item_caption = None
        self._sub_item_menu = None
        self._note_entry = None

        # One column fills the width; row 3 (the list) stretches.
        #   rows: 0 title | 1 subtitle | 2 form | 3 list (weight 1) | 4 message
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._title = ctk.CTkLabel(
            self, text="Daily Expenses",
            font=theme.font("title"), anchor="w",
        )
        self._title.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._subtitle = ctk.CTkLabel(
            self,
            text="What you spend day to day. Every entry reduces your "
                 "remaining balances immediately.",
            font=theme.font("subtitle"), anchor="w",
        )
        self._subtitle.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # The log/edit card. Static so it does not jump around between
        # rebuilds; its CONTENTS are rebuilt by _build_form().
        self._form = ctk.CTkFrame(
            self,
            corner_radius=theme.radius("lg"),
            border_width=1,
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._form.grid(
            row=2, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # The scrollable list holds either the empty state or one card
        # per day. The scrollbar is themed here so it does not fall back
        # to CustomTkinter's own grey.
        self._list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._list.grid(
            row=3, column=0, sticky="nsew",
            padx=pad, pady=(0, theme.spacing("md")),
        )
        # Children of a CTkScrollableFrame are gridded onto its inner
        # window, so this makes column 0 take the full usable width.
        self._list.grid_columnconfigure(0, weight=1)

        # Inline feedback. Always gridded (even when empty) so the layout
        # never jumps - same trick as the other screens.
        self._message = ctk.CTkLabel(
            self, text="", font=theme.font("body"),
            anchor="w", justify="left",
        )
        self._message.grid(
            row=4, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("sm")),
        )

    # -- state helpers ------------------------------------------------------

    def _set_message(self, text: str, kind: str) -> None:
        """Show (or clear) the inline message. kind: "" | "error" | "success"."""
        self._message_kind = kind
        self._message.configure(text=text)
        self._apply_message_style()

    def _apply_message_style(self) -> None:
        """Colour the message row from its kind. Called by _set_message()
        and by refresh_theme(), so a mode flip can never leave it stale."""
        colors = {
            "": theme.color("text_secondary"),
            "error": theme.color("danger"),
            "success": theme.color("success"),
        }
        self._message.configure(text_color=colors[self._message_kind])

    def _close_form(self):
        """Empty the editable fields and leave edit mode; return old state.

        Called BEFORE a change is attempted: a success notifies, which
        rebuilds the form while this handler is still running, and the
        rebuild must see the form as already reset.

        KEPT on purpose:
          * budget and category - people usually log several expenses to
            the same place, and re-picking every time is pure friction;
          * date - filling in a day's spending in one sitting (back-fill)
            is a normal use, and the field is visible, so the pick can
            never be a hidden trap. It is always re-shown, never guessed.
        BLANKED on purpose:
          * amount and note - they describe ONE expense each;
          * sub-item - it names one specific thing (Netflix, not
            Spotify), so carrying it over would file the next expense
            under the wrong one.
        """
        saved = (self._amount_var.get(), self._sub_item_var.get(),
                 self._note_var.get(), self._date_var.get(), self._editing)
        self._amount_var.set("")
        self._sub_item_var.set(NO_SUB_ITEM)
        self._note_var.set("")
        self._editing = None
        return saved

    def _restore_form(self, saved) -> None:
        """Put back what _close_form took - used only when the holder
        REFUSED the value, because a refusal never rebuilds anything and
        the live entries simply re-read the vars."""
        amount, sub_item, note, date, editing = saved
        self._amount_var.set(amount)
        self._sub_item_var.set(sub_item)
        self._note_var.set(note)
        self._date_var.set(date)
        self._editing = editing

    # -- rebuilding ---------------------------------------------------------

    def _reload(self) -> None:
        """Rebuild the form AND the list from the holders.

        This is the only place either is populated, which is what makes
        refresh_theme() complete by construction: every widget in here is
        born already painted in the active palette.
        """
        # An expense open for editing can be deleted from under us (only
        # ever from elsewhere - this screen's own delete clears the flag
        # first). Rather than leave a heading pointing at nothing, drop
        # back to "add" mode; the fields the user typed are untouched.
        if self._editing is not None and daily_expenses.get_expense(self._editing) is None:
            self._editing = None

        # --- form: its dropdown options come from category_settings -----
        for child in self._form.winfo_children():
            child.destroy()
        self._build_form()

        # --- list -------------------------------------------------------
        for child in self._list.winfo_children():
            child.destroy()
        self._build_list()

    def _build_form(self) -> None:
        """Fill the log/edit card.

        Grid, left to right:
            col 0 (weight 1)  amount
            col 1 (weight 1)  budget picker
            col 2 (weight 2)  category picker (longest names in the tree)
            col 3 (weight 1)  date

        Grid, top to bottom:
            row 0  heading
            row 1  field captions
            row 2  the four controls
            row 3  sub-item caption      } only while the selected
            row 4  sub-item picker       } category has sub-items
            row 5  note caption          } always
            row 6  note entry            }
            row 7  Clear/Cancel + Log/Save, right-aligned

        Rows 3/4 are created ungridded and shown or hidden by
        _sync_sub_item_field(), the single place that decides - so "show"
        and "hide" can never disagree about the grid options. The note
        and the sub-item rows span all four columns, so they line up
        with the controls above whatever the sub-item row is doing.

        WHY THE BUTTONS HAVE THEIR OWN ROW (measured at MIN_SIZE 960x620
        in the real shell, p6_geom.py)
          They used to sit inline at the end of row 2, in a fixed fifth
          column. That left the four fields only ~467 physical px
          against ~700 px they asked for - i.e. NEGATIVE excess space.
          Tk grid shares excess with the weights, and it shares a
          deficit the same way: the weight-2 category column absorbed
          twice the cut the others did and landed at 82px, while its
          own text ("Transport/Fuel") needed 117px - the current value
          was being clipped even for moderate names. (The Fixed Expenses
          screen has the same maths: its two weight-2 columns sit at
          ~97px at this size.)

          With the buttons moved out of the row, all four fields share
          the full form width (~784px against ~700px requested - POSITIVE
          excess again), so the weight-2 category column receives the
          largest share instead of the largest cut: ~217px at min size,
          and comfortably more at the default window size.

          Four controls on the row, exactly like the Fixed Expenses
          screen - a fifth one was measured in Phase 5 squeezing its
          neighbours to ~30px.
        """
        form = self._form
        pad = theme.spacing("md")
        gap = theme.spacing("xs")

        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(2, weight=2)
        form.grid_columnconfigure(3, weight=1)
        # No fifth column: the buttons moved to their own row (row 7) so
        # these four fields get the FULL form width - see the docstring
        # for the min-size measurement that forced the change.

        # --- row 0: what the card is doing right now ----------------------
        if self._editing is None:
            heading = "Log a daily expense"
        else:
            record = daily_expenses.get_expense(self._editing)
            heading = (f"Editing: Rs. {record['amount']:,} · {record['date']}"
                       if record else "Editing a daily expense")
        ctk.CTkLabel(
            form, text=heading,
            font=theme.font("section"), text_color=theme.color("text"),
            anchor="w",
        ).grid(
            row=0, column=0, columnspan=4, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("sm")),
        )

        # --- row 1: field captions ---------------------------------------
        captions = ("Amount (Rs.)", "Budget", "Category", "Date")
        for col, caption in enumerate(captions):
            left = pad if col == 0 else gap
            ctk.CTkLabel(
                form, text=caption,
                font=theme.font("caption"),
                text_color=theme.color("text_secondary"), anchor="w",
            ).grid(
                row=1, column=col, sticky="ew",
                padx=(left, gap), pady=(0, gap),
            )

        # --- row 2: the four controls -------------------------------------
        # Shared styling, so the entry and the pickers read as one family.
        field_style = dict(
            height=FIELD_H,
            corner_radius=theme.radius("sm"),
            font=theme.font("body"),
        )

        self._amount_entry = ctk.CTkEntry(
            form,
            textvariable=self._amount_var,
            fg_color=theme.color("surface"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text="0",
            placeholder_text_color=theme.color("text_secondary"),
            **field_style,
        )
        self._amount_entry.grid(
            row=2, column=0, sticky="ew",
            padx=(pad, gap), pady=(0, pad),
        )

        # Both pickers share this. The arrow is drawn in text_color over
        # the button_color square (CTkOptionMenu._draw), so border behind
        # text keeps it clearly visible in either palette.
        menu_style = dict(
            height=FIELD_H,
            corner_radius=theme.radius("sm"),
            anchor="w",
            fg_color=theme.color("surface"),
            button_color=theme.color("border"),
            button_hover_color=theme.color("accent_soft"),
            text_color=theme.color("text"),
            text_color_disabled=theme.color("text_secondary"),
            dropdown_fg_color=theme.color("card_bg"),
            dropdown_hover_color=theme.color("border"),
            dropdown_text_color=theme.color("text"),
            font=theme.font("body"),
            dropdown_font=theme.font("body"),
        )

        budget_labels = [budget_settings.BUDGET_LABELS[k]
                         for k in budget_settings.BUDGET_KEYS]
        # A var can hold something the list no longer contains (a rebuild
        # after a budget was renamed elsewhere, say). Fall back rather
        # than render a picker showing a value it cannot produce.
        if self._budget_var.get() not in budget_labels:
            self._budget_var.set(budget_labels[0])

        ctk.CTkOptionMenu(
            form,
            values=budget_labels,
            variable=self._budget_var,
            command=self._on_budget_changed,
            **menu_style,
        ).grid(
            row=2, column=1, sticky="ew",
            padx=(gap, gap), pady=(0, pad),
        )

        # Category options follow the SELECTED budget, so they are read
        # here (on every rebuild) and re-read by _on_budget_changed()
        # when the user switches budget without a rebuild.
        budget_key = _key_for_label(self._budget_var.get())
        options = _category_options(budget_key)
        if self._category_var.get() not in options:
            self._category_var.set(options[0])

        self._category_menu = ctk.CTkOptionMenu(
            form,
            values=options,
            variable=self._category_var,
            # Sub-items live INSIDE a category, so the second picker has
            # to follow this one (same relationship as budget -> category).
            command=self._on_category_changed,
            **menu_style,
        )
        self._category_menu.grid(
            row=2, column=2, sticky="ew",
            padx=(gap, gap), pady=(0, pad),
        )

        # The date, prefilled with today (the holder accepts the same
        # YYYY-MM-DD and rejects anything else with a readable message).
        self._date_entry = ctk.CTkEntry(
            form,
            textvariable=self._date_var,
            fg_color=theme.color("surface"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text="YYYY-MM-DD",
            placeholder_text_color=theme.color("text_secondary"),
            **field_style,
        )
        self._date_entry.grid(
            row=2, column=3, sticky="ew",
            padx=(gap, gap), pady=(0, pad),
        )

        # --- rows 3/4: the sub-item picker, built but NOT gridded -------
        # Both widgets are created on every rebuild so they are born
        # painted in the active palette (which is what keeps
        # refresh_theme() complete), then _sync_sub_item_field() decides
        # whether they appear. They span all four columns, exactly like
        # the note below them.
        self._sub_item_caption = ctk.CTkLabel(
            form, text="Sub-item (optional)",
            font=theme.font("caption"),
            text_color=theme.color("text_secondary"), anchor="w",
        )
        self._sub_item_menu = ctk.CTkOptionMenu(
            form,
            values=[NO_SUB_ITEM],
            variable=self._sub_item_var,
            **menu_style,
        )
        self._sync_sub_item_field()

        # --- rows 5/6: the note (optional), full field width -------------
        ctk.CTkLabel(
            form, text="Note (optional)",
            font=theme.font("caption"),
            text_color=theme.color("text_secondary"), anchor="w",
        ).grid(
            row=5, column=0, columnspan=4, sticky="ew",
            padx=(pad, gap), pady=(0, gap),
        )
        self._note_entry = ctk.CTkEntry(
            form,
            textvariable=self._note_var,
            height=FIELD_H,
            corner_radius=theme.radius("sm"),
            font=theme.font("body"),
            fg_color=theme.color("surface"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text="e.g. Weekly groceries",
            placeholder_text_color=theme.color("text_secondary"),
        )
        self._note_entry.grid(
            row=6, column=0, columnspan=4, sticky="ew",
            padx=(pad, gap), pady=(0, pad),
        )
        # GENTLE auto-capitalise while typing (see text_rules): the first
        # letter goes up, the rest stays exactly as typed. The holder
        # applies the same rule on the way in, so what is STORED matches
        # what is SEEN even if a future caller bypasses this field.
        text_rules.bind_gentle_capitalise(self._note_entry)

        # Buttons on their OWN row, right-aligned. Keeping them out of
        # the control row is what gives the four fields the full form
        # width at min size - see the _build_form docstring for the
        # measurement that forced this. Spanning all four columns means
        # the strip lines up with the note above it whatever the
        # sub-item row is doing.
        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(
            row=7, column=0, columnspan=4, sticky="e",
            padx=(gap, pad), pady=(0, pad),
        )

        if self._editing is None:
            secondary_text, primary_text = "Clear", "Log expense"
        else:
            secondary_text, primary_text = "Cancel", "Save changes"

        # Packed left in this order, so the primary action ends up on the
        # right: [secondary] [primary].
        secondary = ctk.CTkButton(
            buttons, text=secondary_text,
            width=BUTTON_W_SECONDARY, height=BUTTON_H,
            corner_radius=theme.radius("sm"), font=theme.font("button"),
            fg_color="transparent",
            hover_color=theme.color("surface"),
            text_color=theme.color("text_secondary"),
            command=self._cancel_form,
        )
        secondary.pack(side="left", padx=(0, gap))

        ctk.CTkButton(
            buttons, text=primary_text,
            width=BUTTON_W_PRIMARY, height=BUTTON_H,
            corner_radius=theme.radius("sm"), font=theme.font("button"),
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("text_on_accent"),
            command=self._submit,
        ).pack(side="left")

        # Enter submits from anywhere in the form. Bound to the two text
        # fields that hold free-form input, so it cannot fire while the
        # caret is in the list or on a button. The date box is NOT bound:
        # it is prefilled, and a half-typed date pressing Enter would
        # just produce a validation error the user did not ask for.
        self._amount_entry.bind("<Return>", lambda _e: self._submit())
        self._note_entry.bind("<Return>", lambda _e: self._submit())

    def _on_budget_changed(self, label: str) -> None:
        """The budget picker moved: the category picker must follow.

        Categories live inside a budget, so switching Needs -> Savings has
        to re-read the options. The current pick is kept when it happens
        to exist in the new budget, otherwise it falls back to the first
        one - which is also what heals a pick that no longer exists.

        The sub-item picker follows too, for exactly the same reason one
        level down: it re-reads its own options from whatever category
        the line above settled on.
        """
        options = _category_options(_key_for_label(label))
        if self._category_var.get() not in options:
            self._category_var.set(options[0])
        self._category_menu.configure(values=options)
        self._sync_sub_item_field()

    def _on_category_changed(self, category: str) -> None:
        """The category picker moved: the sub-item picker must follow.

        Same pattern as _on_budget_changed, one level down. CustomTkinter
        writes the new pick into _category_var BEFORE it calls this (see
        CTkOptionMenu._dropdown_callback), so the var and the `category`
        argument already agree by the time we sync - the sync reads the
        vars, which is the state the rest of the form reads too.

        Called only when the USER picks from the menu; programmatic
        changes (editing an expense, Clear) go through _reload(), which
        rebuilds the form and calls the same sync.
        """
        self._sync_sub_item_field()

    def _sync_sub_item_field(self) -> None:
        """Show the sub-item picker only for a category that HAS sub-items.

        The visibility rule for the whole feature:

          * category has sub-items  -> fill the dropdown with them (always
            led by NO_SUB_ITEM) and grid both widgets onto rows 3/4;
          * category has none       -> grid_remove() both and reset the
            pick to NO_SUB_ITEM.

        Hiding rather than disabling is deliberate: a greyed-out
        dropdown still claims a row and invites a click that cannot do
        anything, and most categories have no sub-items at all. grid_remove
        (not grid_forget) keeps the widgets alive, so the pair can simply
        be gridded again when the user moves back to a category that does
        have them.

        The pick is KEPT when it is still valid for the category now
        selected - that is what preselects the right entry when editing
        an expense - and otherwise falls back to NO_SUB_ITEM.
        """
        if self._sub_item_menu is None:
            return                      # form not built yet (defensive)

        options = _sub_item_options(_key_for_label(self._budget_var.get()),
                                    self._category_var.get())
        if not options:
            self._sub_item_var.set(NO_SUB_ITEM)
            self._sub_item_caption.grid_remove()
            self._sub_item_menu.grid_remove()
            return

        # The explicit "none" entry is ALWAYS the first option: attaching
        # at category level has to stay a positive choice even when the
        # category does have sub-items.
        values = [NO_SUB_ITEM] + options
        if self._sub_item_var.get() not in values:
            self._sub_item_var.set(NO_SUB_ITEM)
        self._sub_item_menu.configure(values=values)

        pad = theme.spacing("md")
        gap = theme.spacing("xs")
        # padx mirrors the control row (left `pad`, right `gap`), so this
        # row spans exactly the width of the four fields above.
        self._sub_item_caption.grid(
            row=3, column=0, columnspan=4, sticky="ew",
            padx=(pad, gap), pady=(0, gap),
        )
        self._sub_item_menu.grid(
            row=4, column=0, columnspan=4, sticky="ew",
            padx=(pad, gap), pady=(0, pad),
        )

    # -- the list -----------------------------------------------------------

    def _build_list(self) -> None:
        """Fill the scrollable area: the empty state, or one card per day."""
        expenses = daily_expenses.get_expenses()
        if not expenses:
            self._build_empty_state()
            return

        # Read once, then group: newest day first, newest expense first.
        rows = []
        for position, (iso_date, records) in enumerate(_group_by_day(expenses)):
            card, day_rows = self._build_day_card(iso_date, records)
            card.grid(
                row=position, column=0, sticky="ew",
                pady=(0, theme.spacing("md")),
            )
            rows.extend(day_rows)

        # One amount width for the whole list, not one per row.
        self._align_amount_columns(rows)

    def _build_empty_state(self) -> None:
        """One clean card when nothing has been logged yet."""
        pad = theme.spacing("lg")
        card = ctk.CTkFrame(
            self._list,
            corner_radius=theme.radius("lg"),
            border_width=1,
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        card.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            card, text="No expenses logged yet.",
            font=theme.font("section"), text_color=theme.color("text"),
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("xs")),
        )
        ctk.CTkLabel(
            card,
            text="Log what you spend as it happens - groceries, fuel, a "
                 "movie. Each one comes straight off your remaining "
                 "balances on the Dashboard.",
            font=theme.font("body"), text_color=theme.color("text_secondary"),
            anchor="w", justify="left", wraplength=560,
        ).grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, pad),
        )

    def _build_day_card(self, iso_date: str, records: list):
        """One day's card: header with its date and subtotal, then rows.

        The subtotal sums THIS DAY's expenses across all budgets - the
        local echo of the Dashboard's remaining balance, computed from
        the same records the cascade maths reads.

        Returns (card, rows) - rows as (bar, chip_label) pairs, the same
        shape the Fixed Expenses screen hands back, so _build_list can
        collect them all for column alignment.
        """
        pad = theme.spacing("md")
        gap = theme.spacing("xs")
        subtotal = sum(record["amount"] for record in records)

        card = ctk.CTkFrame(
            self._list,
            corner_radius=theme.radius("lg"),
            border_width=1,
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        card.grid_columnconfigure(0, weight=1)

        # --- header: date + count ... subtotal ---------------------------
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(pad, gap),
        )
        header.grid_columnconfigure(2, weight=1)   # pushes the subtotal right

        ctk.CTkLabel(
            header, text=_day_heading(iso_date),
            font=theme.font("section"),
            text_color=theme.color("text"), anchor="w",
        ).grid(row=0, column=0, sticky="w")

        count = len(records)
        ctk.CTkLabel(
            header,
            text=f"{count} {'expense' if count == 1 else 'expenses'}",
            font=theme.font("caption"),
            text_color=theme.color("text_secondary"), anchor="w",
        ).grid(
            row=0, column=1, sticky="w",
            padx=(theme.spacing("sm"), 0),
        )

        ctk.CTkLabel(
            header, text=f"Rs. {subtotal:,}",
            font=theme.font("value"), text_color=theme.color("text"),
            anchor="e",
        ).grid(row=0, column=3, sticky="e")

        # --- rows ---------------------------------------------------------
        rows = []
        for row, expense in enumerate(records, start=1):
            rows.append(self._build_expense_row(card, row, expense))
        return card, rows

    def _build_expense_row(self, master, row: int, expense: dict):
        """One expense: amount, path chip, note, Edit + Delete.

        Returns (bar, chip_label) so the caller can line every row's
        amount column up - see _align_amount_columns.
        """
        gap = theme.spacing("xs")
        pad = theme.spacing("md")
        expense_id = expense["id"]
        editing = (self._editing is not None and self._editing == expense_id)

        # The row being edited is outlined rather than filled, so it is
        # obvious which record the form above is about WITHOUT changing
        # the background the chip and text colours were checked against.
        # (One dict, not fg_color= plus **style: that would pass it twice.)
        style = {"fg_color": "transparent"}
        if editing:
            style = {
                "fg_color": theme.color("card_bg"),
                "border_width": 1,
                "border_color": theme.color("accent"),
            }

        bar = ctk.CTkFrame(
            master,
            corner_radius=theme.radius("sm"),
            **style,
        )
        bar.grid(row=row, column=0, sticky="ew", padx=pad, pady=(0, gap))
        # FOUR columns. Column 0 (amount) gets its minsize AFTER the
        # whole list is built - see _align_amount_columns: every row is
        # its own grid, so grid would otherwise give each row an amount
        # column as wide as its own figure, and the chip right of it
        # would start at a different x in every row.
        # All the slack goes into the NOTE column, so amounts stay hard
        # left and the buttons stay hard right however long the chip or
        # the note happens to be.
        bar.grid_columnconfigure(0, weight=0)   # amount, minsize set later
        bar.grid_columnconfigure(1, weight=0)   # chip, its own text width
        bar.grid_columnconfigure(2, weight=1)   # note: takes all slack
        bar.grid_columnconfigure(3, weight=0)   # buttons

        ctk.CTkLabel(
            bar, text=f"Rs. {expense['amount']:,}",
            font=theme.font("value"), text_color=theme.color("text"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, gap))

        chip_label = self._build_chip(bar, expense)
        chip_label.grid(row=0, column=1, sticky="w", padx=(0, gap))

        # The note is secondary information: truncated so a very long one
        # cannot widen this column until it squeezes the buttons. The
        # FULL text is always one Edit away.
        note_text = expense["note"] or ""
        if len(note_text) > NOTE_DISPLAY_MAX:
            note_text = note_text[:NOTE_DISPLAY_MAX - 1] + "…"
        ctk.CTkLabel(
            bar, text=note_text,
            font=theme.font("body"), text_color=theme.color("text_secondary"),
            anchor="w",
        ).grid(row=0, column=2, sticky="ew", padx=(0, gap))

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=3, sticky="e")
        self._action(actions, "Edit",
                     lambda i=expense_id: self._start_edit(i), "accent_text")
        self._action(actions, "Delete",
                     lambda i=expense_id: self._ask_delete(i), "danger")

        return bar, chip_label

    def _align_amount_columns(self, rows) -> None:
        """Give every row in the list the SAME amount-column width.

        Why it is needed: each expense row is a separate frame with its
        own grid, so grid sizes each row's amount column from that row's
        own figure ("Rs. 450" is narrower than "Rs. 12,450"). The chip is
        gridded immediately after it, so it drifted along with it - which
        reads as a ragged list.

        The fix is the one a table uses (and the same one the Fixed
        Expenses screen uses for its names): measure the chip's x - the
        number that has to match - in every row after Tk has laid them
        out, take the largest, and make every row reserve at least that
        much. Then column 0 is a constant and every chip starts on the
        same vertical line.

        Nothing is lost: no amount can be wider than the widest amount,
        so no row's figure is ever clipped.
        """
        if not rows:
            return
        self.update_idletasks()
        widest = max(chip.winfo_x() for _, chip in rows)
        if not widest:                      # nothing laid out yet
            return
        for bar, _ in rows:
            bar.grid_columnconfigure(0, minsize=widest)

    def _build_chip(self, master, expense: dict):
        """The path tag: budget -> category (-> sub-item).

        Normal: a filled pill in the accent pair (accent_soft /
        accent_text), which theme.py documents as a readable
        combination. It LEADS with the budget because this list is
        grouped by date - the row has to say which pot the money came
        from on its own:

            "Needs -> Transport/Fuel"
            "Wants -> Subscriptions -> Netflix"   (one pill, the arrow
                                                     is the hierarchy)

        Uncategorised: no fill at all, the path in the warning colour
        straight on the card. That is on purpose - warning text on the
        surface fill the pill would need measures below the 4.5:1 the
        project holds itself to, while warning on card_bg clears it
        comfortably in both palettes. It should look different anyway:
        it is the anomaly. An uncategorised expense has no sub-item
        either (the holder drops both links together), so this branch
        never needs one.
        """
        label = budget_settings.BUDGET_LABELS[expense["budget"]]
        category = expense["category"]

        if category:
            text = f"{label} → {category}"
            sub_item = expense["sub_item"]
            if sub_item:
                text = f"{text} → {sub_item}"
            return ctk.CTkLabel(
                master, text=text,
                font=theme.font("caption"),
                fg_color=theme.color("accent_soft"),
                text_color=theme.color("accent_text"),
                corner_radius=theme.radius("sm"),
                padx=8, pady=2,
            )
        return ctk.CTkLabel(
            master, text=f"{label} → Uncategorised",
            font=theme.font("caption"),
            fg_color="transparent",
            text_color=theme.color("warning"),
            padx=0, pady=2,
        )

    # -- actions ------------------------------------------------------------

    def _submit(self) -> None:
        """Log a new expense, or save the one being edited.

        Everything is read off the vars FIRST (the close step blanks
        them), then the form is put into its post-action shape, and only
        then is the holder asked. A refusal restores the state, so the
        open form keeps exactly what the user typed - the same
        close/restore dance the other screens use.
        """
        amount = self._amount_var.get()
        budget = _key_for_label(self._budget_var.get())
        category = self._category_var.get()
        sub_item = self._sub_item_var.get()
        date = self._date_var.get()
        note = self._note_var.get()
        editing_id = self._editing

        # The picker's "none" entry is a UI spelling, not data: the
        # holder is handed a real None so it stores a real None. When
        # the sub-item row is hidden the var has already been reset to
        # the placeholder by _sync_sub_item_field, so this line is also
        # what makes a hidden field mean "category level only".
        sub_item = None if sub_item == NO_SUB_ITEM else sub_item

        saved = self._close_form()

        try:
            if editing_id is None:
                new_id = daily_expenses.add_daily_expense(
                    amount, budget, category, sub_item, date, note)
            else:
                daily_expenses.update_daily_expense(
                    editing_id, amount, budget, category, sub_item, date, note)
                new_id = None
        except ValueError as exc:
            # Nothing was stored, so nothing was notified and no rebuild
            # happened: put the state back so the form still matches what
            # the user is looking at, and keep the caret in the field.
            self._restore_form(saved)
            self._amount_entry.focus_set()
            self._set_message(str(exc), "error")
            return

        # The holder already notified, so the form above is rebuilt and
        # empty. Land the caret in it so the next expense is one click
        # away, and say what changed. The message quotes the figure the
        # holder STORED (ids are handed back by add, so commas and
        # whitespace the user typed are already normalised).
        if new_id is None:
            message = "✓ Expense updated."
        else:
            record = daily_expenses.get_expense(new_id)
            message = (f"✓ Logged Rs. {record['amount']:,}."
                       if record else "✓ Expense logged.")
        self._set_message(message, "success")
        self._amount_entry.focus_set()

    def _cancel_form(self) -> None:
        """Clear / Cancel: empty the fields, leave edit mode, drop the
        message. The stored expenses are untouched - cancel is not undo."""
        self._close_form()
        # The date is the one field _close_form deliberately KEEPS (see
        # its docstring) - but Clear means "start over", so put today
        # back. Cancel does the same for symmetry.
        self._date_var.set(dt.date.today().isoformat())
        self._set_message("", "")
        self._reload()

    def _start_edit(self, expense_id: int) -> None:
        """Load one expense into the form and switch it to edit mode."""
        expense = daily_expenses.get_expense(expense_id)
        if expense is None:
            self._set_message(f"No daily expense with id {expense_id}.", "error")
            return

        # Point the pickers at the expense's OWN budget and category
        # first. Without this, editing only the amount of an expense
        # filed under Savings would quietly move it to whatever budget
        # the form happened to be showing.
        self._budget_var.set(budget_settings.BUDGET_LABELS[expense["budget"]])
        options = _category_options(expense["budget"])
        if expense["category"] in options:
            self._category_var.set(expense["category"])
        else:
            # Uncategorised: preselect the first real category so that
            # simply pressing Save re-attaches it.
            self._category_var.set(options[0])

        # ...and its sub-item, so the picker opens on the entry the
        # record already points at. NO_SUB_ITEM for a category-level
        # expense (and for an uncategorised one, whose sub-item link the
        # holder has already dropped with its category). _reload() below
        # rebuilds the form, and _sync_sub_item_field() keeps this value
        # only if it really exists under the category now selected.
        sub_item = expense["sub_item"]
        self._sub_item_var.set(sub_item if sub_item else NO_SUB_ITEM)

        self._amount_var.set(str(expense["amount"]))
        self._date_var.set(expense["date"])
        self._note_var.set(expense["note"] or "")
        self._editing = expense["id"]
        self._set_message("", "")
        self._reload()

    def _ask_delete(self, expense_id: int) -> None:
        """Open the confirmation dialog for one expense.

        Held on self so the dialog is not garbage-collected while open,
        and the sentence is built here (from the record itself) so the
        shared widget stays ignorant of daily expenses.
        """
        self._set_message("", "")
        expense = daily_expenses.get_expense(expense_id)
        if expense is None:
            self._set_message(f"No daily expense with id {expense_id}.", "error")
            return
        self._dialog = ConfirmDialog(
            self,
            title="Confirm delete",
            message=(f"Delete the expense of Rs. {expense['amount']:,} "
                     f"on {expense['date']}?\n\nThis cannot be undone."),
            on_confirm=lambda: self._confirm_delete(expense_id),
        )

    def _confirm_delete(self, expense_id: int) -> None:
        """Actually remove the expense - only ever reached from the dialog.

        Deleting RAISES spent back up (the cascade runs the other way),
        so every subscriber - the Dashboard included - recomputes when
        the holder notifies. The form is reset ONLY if the expense being
        deleted is the one open for editing; deleting something else must
        not wipe what the user is currently typing.
        """
        was_editing = (self._editing is not None and self._editing == expense_id)
        saved = self._close_form() if was_editing else None

        try:
            daily_expenses.delete_daily_expense(expense_id)
        except ValueError as exc:
            if saved is not None:
                self._restore_form(saved)
            self._set_message(str(exc), "error")
            return

        self._set_message("✓ Expense deleted.", "success")

    # -- shared row button --------------------------------------------------

    def _action(self, master, text, command, color_key, width=84):
        """Create one small ghost button and pack it into `master`.

        Ghost style (transparent face, colour in the label) keeps a row of
        two buttons from shouting; the face only appears on hover.
        `color_key` is a palette key, not a hex value. Deliberately the
        same treatment the Categories and Fixed Expenses screens give
        their row buttons.
        """
        button = ctk.CTkButton(
            master, text=text,
            width=width, height=26,
            corner_radius=theme.radius("sm"), font=theme.font("caption"),
            fg_color="transparent",
            hover_color=theme.color("surface"),
            text_color=theme.color(color_key),
            command=command,
        )
        button.pack(side="left", padx=(0, theme.spacing("xs")))
        return button

    # -- theming ------------------------------------------------------------

    def refresh_theme(self) -> None:
        """Re-read every colour from theme.py and apply it to this screen.

        main.py calls this once at startup and again on every dark/light
        flip. The static chrome is recoloured here; the form and the list
        are rebuilt by _reload(), so every widget in them is recreated
        already painted in the active palette - nothing can be missed.
        That covers EVERY widget this screen creates: title, subtitle,
        form card, list frame, message row (chrome, recoloured) plus the
        form's entries/pickers/buttons, the day cards, rows, chips, notes
        and Edit/Delete buttons (reborn by _reload).
        """
        self.configure(fg_color=theme.color("bg"))
        self._title.configure(text_color=theme.color("text"))
        self._subtitle.configure(text_color=theme.color("text_secondary"))
        self._form.configure(
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._list.configure(
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._apply_message_style()
        self._reload()
