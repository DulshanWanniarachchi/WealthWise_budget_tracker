
import customtkinter as ctk

from app.core import theme, text_rules
# daily_expenses is here ONLY to repaint the plan progress bars: actual
# spending lives in that holder, and these rows show spending against
# the plan (see PLAN PROGRESS in this docstring).
from app.services import (budget_settings, category_settings,
                          daily_expenses, fixed_expenses)
from app.widgets.confirm_dialog import ConfirmDialog

# ---------------------------------------------------------------------------
# CONTROL SIZES, IN PIXELS.
# Same precedent as the Settings screen's input widths and main.py's
# sidebar width: control dimensions are not colours / fonts / spacing /
# radius, so they stay here and NOT in theme.py.
# ---------------------------------------------------------------------------
FIELD_H = 34          # entries and dropdowns share it, so the row lines up
BUTTON_W_PRIMARY = 132   # "Add expense" / "Save changes"
BUTTON_W_SECONDARY = 84  # "Clear" / "Cancel"
BUTTON_H = 34

# The plan-status label in row 1 of every expense row gets ONE width for
# the whole list. Its strings vary hugely ("✓ Paid" vs "Rs. 8,000 of
# Rs. 30,000" vs the two-line over-plan block), and the label shares a
# grid column with the Edit/Delete buttons - without a fixed width each
# row's column 3 would be a different size and every row's amount above
# would sit on its own right-hand line. 168 comfortably fits "Rs.
# 999,999 of Rs. 999,999" at the caption font (measured with the probe)
# and still leaves the buttons the wider of the two, as they are today.
# The over-plan block is two labels of this same width stacked in a
# transparent frame, so it costs no extra column width either.
PLAN_STATUS_W = 168

# Shown in the category dropdown when the selected budget has no
# categories at all. It is selectable but never storable - submitting it
# makes the holder raise the real, more helpful error message.
NO_CATEGORIES = "No categories yet"

# Shown as the FIRST entry of the sub-item dropdown: the expense
# attaches at category level only, which is the default and the most
# common choice. The screen translates it to None before it ever reaches
# the holder - the holder knows nothing about how a picker spells "none".
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

    Unlike _category_options this returns [] - never a placeholder -
    because an empty list is the SIGNAL the form acts on: no sub-items
    means the sub-item row is not shown at all (see
    _sync_sub_item_field). [] also covers the "No categories yet"
    placeholder and a category that has since vanished elsewhere, both
    of which are equally "nothing to pick from here".
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


# ---------------------------------------------------------------------------
# THE SCREEN
# ---------------------------------------------------------------------------

class FixedExpensesScreen(ctk.CTkFrame):
    """Screen for the money that repeats every month."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)
        self._build()
        # Four subscriptions, on purpose:
        #   fixed_expenses  - an expense was added / edited / deleted, or
        #                     reconcile() just uncategorised one;
        #   category_settings - the category tree changed, so the form's
        #                     dropdown options (and the chips in the list)
        #                     are now out of date;
        #   daily_expenses  - spending changed, so the plan progress bars
        #                     and the Paid/Over readouts in row 1 of every
        #                     row have to move (plan fix). It fires even
        #                     while this screen is hidden, so the bars are
        #                     right the moment the user comes back;
        #   budget_settings - the ALLOCATION changed (Phase 7), so a
        #                     section's "planned exceeds allocated"
        #                     warning has to re-appear or disappear.
        # The holder ignores duplicate registrations of the same callable.
        fixed_expenses.subscribe(self._reload)
        category_settings.subscribe(self._reload)
        daily_expenses.subscribe(self._reload)
        budget_settings.subscribe(self._reload)
        self.refresh_theme()   # paints the chrome AND builds form + list

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        """Create the static chrome once. Colours are applied in
        refresh_theme(); the form and the list are built by _reload()."""
        pad = theme.spacing("lg")

        # --- state, read by _reload() while it decides what to render -----
        self._message_kind = ""       # "" | "error" | "success"
        self._editing = None          # name of the expense being edited, or None
        self._dialog = None           # keeps a confirm box alive (no GC mid-air)
        # Plan-progress widget refs, rebuilt from scratch with every list
        # rebuild: {expense name: {"bar": CTkProgressBar, "status": label,
        # "over_status": label or None}} - over_status is the second
        # danger line ("Over by Rs. ...") shown only on an over-plan row.
        # The tests read these to assert paid/progress/overrun without
        # going on a widget hunt; nothing in the UI needs them (the list
        # is rebuilt, never patched in place).
        self._plan_rows = {}
        # Same idea for the per-section "planned exceeds allocated"
        # warning: {budget: label or None}, rebuilt with the list.
        self._allocation_warnings = {}

        # Form state. StringVars, not widget values: the widgets are
        # destroyed on every rebuild, the vars are not.
        self._name_var = ctk.StringVar(value="")
        self._amount_var = ctk.StringVar(value="")
        self._budget_var = ctk.StringVar(value=budget_settings.BUDGET_LABELS["needs"])
        self._category_var = ctk.StringVar(value="")
        # Starts on the placeholder: a new expense attaches at category
        # level until the user says otherwise.
        self._sub_item_var = ctk.StringVar(value=NO_SUB_ITEM)

        # The form widgets handlers need by reference (the rest are
        # built and forgotten by _build_form). Reassigned on every
        # rebuild. The sub-item pair starts as None because it is
        # created ungridded - _sync_sub_item_field() decides whether it
        # is on screen at all.
        self._name_entry = None
        self._category_menu = None
        self._sub_item_caption = None
        self._sub_item_menu = None

        # One column fills the width; row 3 (the list) stretches.
        #   rows: 0 title | 1 subtitle | 2 form | 3 list (weight 1) | 4 message
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._title = ctk.CTkLabel(
            self, text="Fixed Expenses",
            font=theme.font("title"), anchor="w",
        )
        self._title.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._subtitle = ctk.CTkLabel(
            self,
            text="Your monthly plan. Log spending on Daily Expenses to cover each one.",
            font=theme.font("subtitle"), anchor="w",
        )
        self._subtitle.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # The add/edit card. Static so it does not jump around between
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

        # The scrollable list holds either the empty state or the three
        # budget sections. The scrollbar is themed here so it does not
        # fall back to CustomTkinter's own grey.
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
        # never jumps - same trick as the Settings and Categories screens.
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
        """Blank the editable fields and leave edit mode; return old state.

        Called BEFORE a change is attempted: a success notifies, which
        rebuilds the form while this handler is still running, and the
        rebuild must see the form as already reset. Budget and category
        picks are deliberately KEPT - people usually add several expenses
        to the same budget, and re-picking it every time is pure friction.

        The SUB-ITEM pick is deliberately NOT kept: unlike a budget or a
        category, a sub-item names one specific thing (Netflix, not
        Spotify), so carrying it over would silently file the next
        expense under the wrong one. The category it belongs to stays, so
        the user only has to choose the sub-item again.
        """
        saved = (self._name_var.get(), self._amount_var.get(),
                 self._sub_item_var.get(), self._editing)
        self._name_var.set("")
        self._amount_var.set("")
        self._sub_item_var.set(NO_SUB_ITEM)
        self._editing = None
        return saved

    def _restore_form(self, saved) -> None:
        """Put back what _close_form took - used only when the holder
        REFUSED the value, because a refusal never rebuilds anything and
        the live entries simply re-read the vars."""
        name, amount, sub_item, editing = saved
        self._name_var.set(name)
        self._amount_var.set(amount)
        self._sub_item_var.set(sub_item)
        self._editing = editing

    # -- rebuilding ---------------------------------------------------------

    def _reload(self) -> None:
        """Rebuild the form AND the list from the holders.

        This is the only place either is populated, which is what makes
        refresh_theme() complete by construction: every widget in here is
        born already painted in the active palette.
        """
        # --- form: its dropdown options come from category_settings -----
        for child in self._form.winfo_children():
            child.destroy()
        self._build_form()

        # --- list -------------------------------------------------------
        for child in self._list.winfo_children():
            child.destroy()
        self._build_list()

    def _build_form(self) -> None:
        """Fill the add/edit card.

        Grid, left to right:
            col 0 (weight 2)  name
            col 1 (weight 1)  amount
            col 2 (weight 1)  budget picker
            col 3 (weight 2)  category picker
            col 4 (fixed)     Clear/Cancel + Add/Save
        The button column is FIXED so switching between add and edit mode
        does not resize the four fields under the user's cursor.

        Grid, top to bottom:
            row 0  heading
            row 1  field captions
            row 2  the four controls + the buttons
            row 3  sub-item caption      } only while the selected
            row 4  sub-item picker       } category has sub-items
        Rows 3 and 4 are created ungridded and shown or hidden by
        _sync_sub_item_field(), which is the single place that decides -
        so "show" and "hide" can never disagree about the grid options.
        """
        form = self._form
        pad = theme.spacing("md")
        gap = theme.spacing("xs")

        form.grid_columnconfigure(0, weight=2)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(2, weight=1)
        form.grid_columnconfigure(3, weight=2)
        form.grid_columnconfigure(4, weight=0,
                                  minsize=BUTTON_W_SECONDARY + gap + BUTTON_W_PRIMARY)

        # --- row 0: what the card is doing right now ----------------------
        if self._editing is None:
            heading = "Add a fixed expense"
        else:
            heading = f"Editing: {self._editing}"
        ctk.CTkLabel(
            form, text=heading,
            font=theme.font("section"), text_color=theme.color("text"),
            anchor="w",
        ).grid(
            row=0, column=0, columnspan=5, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("sm")),
        )

        # --- row 1: field captions ---------------------------------------
        captions = ("Fixed expense name", "Amount (Rs.)", "Budget", "Category")
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

        # --- row 2: the four controls + the buttons ----------------------
        # Shared styling, so the entry and the pickers read as one family.
        field_style = dict(
            height=FIELD_H,
            corner_radius=theme.radius("sm"),
            font=theme.font("body"),
        )

        # The name. focus_set() after a successful add lands here.
        self._name_entry = ctk.CTkEntry(
            form,
            textvariable=self._name_var,
            fg_color=theme.color("surface"),
            border_width=1,
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text="e.g. Rent",
            placeholder_text_color=theme.color("text_secondary"),
            **field_style,
        )
        self._name_entry.grid(
            row=2, column=0, sticky="ew",
            padx=(pad, gap), pady=(0, pad),
        )
        # GENTLE auto-capitalise while typing (see text_rules): first
        # letter up as the user types, the rest exactly as typed - the
        # same binding the Daily Expenses note field uses. The holder
        # applies the same rule on add/update (_clean_name), so stored
        # data matches what the user SAW even if a future caller skips
        # this field.
        text_rules.bind_gentle_capitalise(self._name_entry)

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
            row=2, column=1, sticky="ew",
            padx=(gap, gap), pady=(0, pad),
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
            row=2, column=2, sticky="ew",
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
            # to follow this one - the same relationship budget -> category
            # already has (see _on_budget_changed).
            command=self._on_category_changed,
            **menu_style,
        )
        self._category_menu.grid(
            row=2, column=3, sticky="ew",
            padx=(gap, gap), pady=(0, pad),
        )

        # --- rows 3/4: the sub-item picker, built but NOT gridded -------
        # Both widgets are created on every rebuild so they are born
        # painted in the active palette (which is what keeps
        # refresh_theme() complete), then _sync_sub_item_field() decides
        # whether they appear. It spans columns 0..3 - the four FIELD
        # columns, never the button column - so the row lines up with
        # the fields above and the Clear/Add buttons stay where they are.
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

        # Buttons, right-aligned at the end of the control row.
        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(
            row=2, column=4, sticky="e",
            padx=(gap, pad), pady=(0, pad),
        )

        if self._editing is None:
            secondary_text, primary_text = "Clear", "Add expense"
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

        # Enter submits from anywhere in the form. Bound to the two
        # text fields only, so it cannot fire while the caret is in the
        # list or on a button.
        self._name_entry.bind("<Return>", lambda _e: self._submit())
        self._amount_entry.bind("<Return>", lambda _e: self._submit())

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
        anything, and most categories have no sub-items at all - they
        should get the card exactly as tall as it was before this
        feature. grid_remove (not grid_forget) keeps the widgets alive,
        so the pair can simply be gridded again when the user moves back
        to a category that does have them.

        The pick is KEPT when it is still valid for the category now
        selected - that is what preselects the right entry when editing
        an expense - and otherwise falls back to NO_SUB_ITEM, which is
        also what heals a pick that belonged to the previous category.
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
        # padx mirrors the control row: the name entry starts at `pad`
        # and the category picker ends `gap` before the button column,
        # so this row spans exactly the width of the four fields above.
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
        """Fill the scrollable area: the empty state, or three sections."""
        if fixed_expenses.count() == 0:
            self._plan_rows = {}        # no rows exist, so no refs either
            self._allocation_warnings = {}
            self._build_empty_state()
            return

        # Read ONCE and hand to every section, so the plan progress and
        # the plan-vs-allocation comparison are all taken from the same
        # instant - a notification arriving mid-rebuild would otherwise
        # show two different clocks in the same list. The comparison
        # entry also carries the section's header total (planned), so
        # there is no separate totals read to disagree with it.
        plans = {p["name"]: p for p in fixed_expenses.get_plan_progress()}
        compare = fixed_expenses.get_plan_vs_allocation()
        self._plan_rows = {}            # every row re-registers below
        self._allocation_warnings = {}  # ...and so does every warning
        rows = []
        for row, budget in enumerate(budget_settings.BUDGET_KEYS):
            section, section_rows = self._build_section(
                budget, plans, compare[budget])
            section.grid(
                row=row, column=0, sticky="ew",
                pady=(0, theme.spacing("md")),
            )
            rows.extend(section_rows)

        # One name width for the whole list, not one per row.
        self._align_name_columns(rows)

    def _build_empty_state(self) -> None:
        """One clean card when the user has not added anything yet."""
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
            card, text="No fixed expenses yet.",
            font=theme.font("section"), text_color=theme.color("text"),
            anchor="w",
        ).grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("xs")),
        )
        ctk.CTkLabel(
            card,
            text="Rent, subscriptions, SIPs - anything that repeats every "
                 "month. Add the first one using the form above.",
            font=theme.font("body"), text_color=theme.color("text_secondary"),
            anchor="w", justify="left", wraplength=560,
        ).grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, pad),
        )

    def _build_section(self, budget: str, plans: dict, entry: dict):
        """Build one budget's card: header, optional warning, then rows.

        `plans` is get_plan_progress() keyed by expense name; `entry`
        is this budget's slice of get_plan_vs_allocation() - both
        passed in (rather than re-read per section) so one rebuild
        shows one instant. entry["planned"] doubles as the header's
        total (same holder, same instant, by construction).
        """
        pad = theme.spacing("md")
        label = budget_settings.BUDGET_LABELS[budget]
        expenses = fixed_expenses.get_expenses_for(budget)
        total = entry["planned"]

        card = ctk.CTkFrame(
            self._list,
            corner_radius=theme.radius("lg"),
            border_width=1,
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        card.grid_columnconfigure(0, weight=1)

        # --- header: accent dot + budget + count ... total ---------------
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("sm")),
        )
        header.grid_columnconfigure(3, weight=1)  # pushes the total right

        ctk.CTkLabel(
            header, text="●", font=theme.font("section"),
            text_color=theme.color(budget_settings.BUDGET_ACCENTS[budget]),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text=label, font=theme.font("section"),
            text_color=theme.color("text"), anchor="w",
        ).grid(
            row=0, column=1, sticky="w",
            padx=(theme.spacing("xs"), 0),
        )

        count = len(expenses)
        ctk.CTkLabel(
            header,
            text=f"{count} fixed {'expense' if count == 1 else 'expenses'}",
            font=theme.font("caption"),
            text_color=theme.color("text_secondary"), anchor="w",
        ).grid(
            row=0, column=2, sticky="w",
            padx=(theme.spacing("sm"), 0),
        )

        ctk.CTkLabel(
            header, text=f"Rs. {total:,}",
            font=theme.font("value"), text_color=theme.color("text"),
            anchor="e",
        ).grid(row=0, column=4, sticky="e")

        # --- the plan-exceeds-allocation warning (Phase 7, warning 2) ----
        # The COMPARISON was made by the holder (entry["exceeds"], from
        # get_plan_vs_allocation) - this block only paints it. A WARNING,
        # never a block: planning more than the allocation is allowed,
        # it just gets said out loud. Amber ("warning"), not red: no
        # money has actually gone wrong yet - red is reserved for real
        # overruns (over-plan rows, over-budget cards).
        #
        # next_row is the cursor for everything below: when the warning
        # is present the expense rows start one grid row lower. (The
        # empty-state and this label can't actually coexist - an empty
        # section plans Rs. 0, which can't exceed any allocation - but
        # the cursor keeps the row maths honest regardless.)
        next_row = 1
        warn = None
        if entry["exceeds"]:
            warn = ctk.CTkLabel(
                card,
                text=(f"Planned Rs. {entry['planned']:,} exceeds the "
                      f"Rs. {entry['allocated']:,} allocated for {label}."),
                font=theme.font("body"),
                text_color=theme.color("warning"),
                anchor="w", justify="left",
            )
            warn.grid(
                row=1, column=0, sticky="ew",
                padx=pad, pady=(0, theme.spacing("sm")),
            )
            next_row = 2
        self._allocation_warnings[budget] = warn

        # --- rows ---------------------------------------------------------
        # A budget with nothing under it says so, rather than showing an
        # empty card - and the total above still reads Rs. 0 correctly.
        if not expenses:
            ctk.CTkLabel(
                card, text=f"No fixed expenses under {label} yet.",
                font=theme.font("body"),
                text_color=theme.color("text_secondary"), anchor="w",
            ).grid(
                row=next_row, column=0, sticky="ew",
                padx=pad, pady=(0, theme.spacing("xs")),
            )
            return card, []

        rows = []
        for row, expense in enumerate(expenses, start=next_row):
            rows.append(self._build_expense_row(card, row, expense,
                                                plans.get(expense["name"])))

        return card, rows

    def _build_expense_row(self, master, row: int, expense: dict,
                           plan: dict = None):
        """One expense: name, category chip, amount, Edit + Delete - and
        under them, the plan progress bar with its THREE-state readout
        (under / met / over).

        `plan` is this expense's entry from
        fixed_expenses.get_plan_progress(): planned/spent/progress/paid,
        plus the holder-decided state and over_by. This method paints
        them and does NO arithmetic of its own (the maths lives in the
        holder, per the plan fix - and the over/under/met comparison is
        there too, never here).

        Returns (bar, chip_label) so the caller can line every row's
        name column up - see _align_name_columns.
        """
        gap = theme.spacing("xs")
        pad = theme.spacing("md")
        name = expense["name"]
        editing = (self._editing is not None
                   and self._editing.casefold() == name.casefold())

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
        # FOUR columns, and column 0 is the odd one: it gets its minsize
        # AFTER the whole list is built (see _align_name_columns). Every
        # row is its own grid, so grid would otherwise give each row a
        # name column as wide as that row's own name - and the chip,
        # which sits immediately after it, would start at a different x
        # in every row (it did: 50px apart). Reserving the widest name in
        # the list for all of them puts every chip back on one line.
        #
        # All the slack goes into the AMOUNT column, so the amounts stay
        # hard right against the buttons however long the names and the
        # category tags happen to be.
        bar.grid_columnconfigure(0, weight=0)   # name, minsize set later
        bar.grid_columnconfigure(1, weight=0)   # chip, its own text width
        bar.grid_columnconfigure(2, weight=1)   # amount: takes all slack
        bar.grid_columnconfigure(3, weight=0)   # buttons

        name_label = ctk.CTkLabel(
            bar, text=name,
            font=theme.font("body"), text_color=theme.color("text"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="w", padx=(0, gap))

        chip_label = self._build_chip(bar, expense)
        chip_label.grid(row=0, column=1, sticky="w", padx=(0, gap))

        ctk.CTkLabel(
            bar, text=f"Rs. {expense['amount']:,}",
            font=theme.font("value"), text_color=theme.color("text"),
            anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=(0, theme.spacing("sm")))

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=3, sticky="e")
        self._action(actions, "Edit",
                     lambda n=name: self._start_edit(n), "accent_text")
        self._action(actions, "Delete",
                     lambda n=name: self._ask_delete(n), "danger")

        # --- row 1 of this frame: plan progress + status (plan fix) -------
        # Fixed expenses are the PLAN; the actual money arrives as daily
        # expenses on another screen (see THE PLAN section of
        # fixed_expenses.py). This line shows how much of THIS plan the
        # spending has covered, and paints the THREE states the holder
        # decided (Phase 7 - overspend warnings):
        #
        #   under  "Rs. 0 of Rs. 30,000"  secondary text, budget accent bar
        #   met    "✓ Paid"               success text + success bar
        #   over   "Rs. 6,000 of Rs. 5,000" + "Over by Rs. 1,000"
        #          both DANGER text, FULL danger bar - never a clean tick
        #
        # Layout, both widgets chosen together with the four columns
        # configured above:
        #   * the bar SPANS columns 0..2. Column 2 is this grid's only
        #     weighted column, so every pixel of width the span needs
        #     comes out of the slack column - the chips and the amounts
        #     in row 0 do not move by a pixel;
        #   * the status sits in column 3 (the buttons' column) at a
        #     FIXED width, because "✓ Paid", "Rs. 8,000 of Rs. 30,000"
        #     and the over-plan block are wildly different strings and a
        #     varying column 3 would push each row's amount left by a
        #     different amount. The over-plan block is a small frame
        #     holding TWO stacked labels of that same width, so even it
        #     keeps column 3 (and therefore every amount) exactly where
        #     the other rows put it; only the over rows grow taller.
        #
        # The plan fallback is purely defensive: _build_list reads the
        # plans from the same _expenses list this row came from, so the
        # entry cannot be missing. If it somehow were, "full plan,
        # nothing spent" is the honest state to show.
        plan = plan or {"planned": expense["amount"], "spent": 0,
                        "progress": 0.0, "paid": False,
                        "state": "under", "over_by": 0}
        state = plan["state"]        # "under" | "met" | "over" (holder)
        # Fill: danger when OVER-plan (the bar is capped at full by the
        # holder's clamped progress, so "full + red" is the clearest
        # over-signal a fixed-width row can show - an overflow stub
        # would need a second scale and reads slower); success when the
        # plan is exactly met; until then the budget's own accent, so
        # the bar matches this section's header dot. Track = surface,
        # same pairing the Dashboard's bars use - all from theme.py.
        fill_key = {"over": "danger", "met": "success"}.get(
            state, budget_settings.BUDGET_ACCENTS[expense["budget"]])
        plan_bar = ctk.CTkProgressBar(
            bar,
            height=theme.spacing("sm"),
            corner_radius=theme.radius("sm") // 2,
            border_width=0,
            mode="determinate",
            fg_color=theme.color("surface"),
            progress_color=theme.color(fill_key),
        )
        plan_bar.set(float(plan["progress"]))   # holder's 0..1 as-is
        plan_bar.grid(
            row=1, column=0, columnspan=3, sticky="ew",
            padx=(0, theme.spacing("sm")),
            pady=(gap, pad),
        )

        over_status = None
        if state == "over":
            # TWO stacked danger lines: the pair the warnings spec asked
            # to see ("Rs. 6,000 of Rs. 5,000") over the headline delta
            # ("Over by Rs. 1,000"). Both at the standard fixed width,
            # both in the danger colour - overspending must never be
            # mistakable for the green tick two rows up.
            status_box = ctk.CTkFrame(bar, fg_color="transparent")
            status_box.grid(row=1, column=3, sticky="e", pady=(gap, pad))
            status_box.grid_columnconfigure(0, weight=0)
            status = ctk.CTkLabel(
                status_box,
                text=f"Rs. {plan['spent']:,} of Rs. {plan['planned']:,}",
                font=theme.font("caption"),
                text_color=theme.color("danger"),
                anchor="e", width=PLAN_STATUS_W,
            )
            status.grid(row=0, column=0, sticky="e")
            over_status = ctk.CTkLabel(
                status_box,
                text=f"Over by Rs. {plan['over_by']:,}",
                font=theme.font("caption"),
                text_color=theme.color("danger"),
                anchor="e", width=PLAN_STATUS_W,
            )
            over_status.grid(row=1, column=0, sticky="e")
        elif state == "met":
            # Cleanly covered: exactly the plan, nothing past it.
            status = ctk.CTkLabel(
                bar, text="✓ Paid",
                font=theme.font("caption"),
                text_color=theme.color("success"),
                anchor="e", width=PLAN_STATUS_W,
            )
            status.grid(row=1, column=3, sticky="e", pady=(gap, pad))
        else:
            # In progress: actual of planned, secondary text colour.
            status = ctk.CTkLabel(
                bar, text=f"Rs. {plan['spent']:,} of Rs. {plan['planned']:,}",
                font=theme.font("caption"),
                text_color=theme.color("text_secondary"),
                anchor="e", width=PLAN_STATUS_W,
            )
            status.grid(row=1, column=3, sticky="e", pady=(gap, pad))

        # Published for the tests (see the _plan_rows comment in _build);
        # rebuilt from scratch alongside this list on every _reload.
        # over_status is None except on an over-plan row.
        self._plan_rows[name] = {"bar": plan_bar, "status": status,
                                 "over_status": over_status}

        return bar, chip_label

    def _align_name_columns(self, rows) -> None:
        """Give every row in the list the SAME name-column width.

        Why it is needed: each expense row is a separate frame with its
        own grid, so grid sizes each row's name column from that row's
        own name. The chip is gridded immediately after the name, so it
        drifted along with it - the four test rows measured 50px apart,
        which reads as a ragged list.

        The fix is the one a table uses: find the row whose name column
        came out widest and make every row reserve at least that much.
        Then column 0 is a constant, the chip's x is a constant, and a
        short name simply has a little empty space to its right - which
        is exactly what makes the chips line up.

        Nothing is lost: no name can be wider than the widest name, so
        no row's text is ever clipped.

        The chip's own x is what gets measured, because that is the
        number that has to match - it is the name column's width
        INCLUDING the padding grid adds round the label, which reading
        the label's text width by hand got a pixel wrong.

        update_idletasks() first, because a widget only reports a real
        position once Tk has laid it out.
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
        """The category tag, with the sub-item appended when there is one.

        Normal: a filled pill in the accent pair (accent_soft /
        accent_text), which theme.py documents as a readable
        combination.

        With a sub-item: ONE pill reading "Subscriptions → Netflix".
        One pill rather than two because the two names are a single
        path - the arrow is the hierarchy - and a second pill would
        widen the chip column in exactly the rows that have one, which
        is what _align_name_columns exists to prevent. Only the pill's
        text grows; the pill's x (and so every other row's) does not.

        Uncategorised: no fill at all, warning text straight on the card.
        That is on purpose - the warning colour on the surface fill the
        pill would need measures below the 4.5:1 the project holds itself
        to, while warning on card_bg clears it comfortably in both
        palettes. It should look different anyway: it is the anomaly.
        An uncategorised expense has no sub-item either - the holder
        drops both links together - so this branch never needs one.
        """
        category = expense["category"]
        if category:
            text = category
            sub_item = expense["sub_item"]
            if sub_item:
                text = f"{category} → {sub_item}"
            return ctk.CTkLabel(
                master, text=text,
                font=theme.font("caption"),
                fg_color=theme.color("accent_soft"),
                text_color=theme.color("accent_text"),
                corner_radius=theme.radius("sm"),
                padx=8, pady=2,
            )
        return ctk.CTkLabel(
            master, text="Uncategorised",
            font=theme.font("caption"),
            fg_color="transparent",
            text_color=theme.color("warning"),
            padx=0, pady=2,
        )

    # -- actions ------------------------------------------------------------

    def _submit(self) -> None:
        """Add a new expense, or save the one being edited.

        Everything is read off the vars FIRST (the close step blanks
        them), then the form is put into its post-action shape, and only
        then is the holder asked. A refusal restores the state, so the
        open form keeps exactly what the user typed - the same
        close/restore dance the Categories screen uses.
        """
        name = self._name_var.get()
        amount = self._amount_var.get()
        budget = _key_for_label(self._budget_var.get())
        category = self._category_var.get()
        sub_item = self._sub_item_var.get()
        old_name = self._editing

        # The picker's "none" entry is a UI spelling, not data: the
        # holder is handed a real None so it stores a real None. When
        # the sub-item row is hidden the var has already been reset to
        # the placeholder by _sync_sub_item_field, so this line is also
        # what makes a hidden field mean "category level only".
        sub_item = None if sub_item == NO_SUB_ITEM else sub_item

        saved = self._close_form()

        try:
            if old_name is None:
                fixed_expenses.add_fixed_expense(name, amount, budget,
                                                 category, sub_item)
            else:
                fixed_expenses.update_fixed_expense(
                    old_name, name, amount, budget, category, sub_item)
        except ValueError as exc:
            # Nothing was stored, so nothing was notified and no rebuild
            # happened: put the state back so the form still matches what
            # the user is looking at, and keep the caret in the field.
            self._restore_form(saved)
            self._name_entry.focus_set()
            self._set_message(str(exc), "error")
            return

        # The holder already notified, so the form above is rebuilt and
        # empty. Land the caret in it so the next expense is one click
        # away, and say which record changed.
        verb = "Added" if old_name is None else "Updated"
        self._set_message(f"✓ {verb} '{name.strip()}'.", "success")
        self._name_entry.focus_set()

    def _cancel_form(self) -> None:
        """Clear / Cancel: empty the fields, leave edit mode, drop the
        message. The stored expenses are untouched - cancel is not undo."""
        self._close_form()
        self._set_message("", "")
        self._reload()

    def _start_edit(self, name: str) -> None:
        """Load one expense into the form and switch it to edit mode."""
        expense = fixed_expenses.get_expense(name)
        if expense is None:
            self._set_message(f"No fixed expense named {name!r}.", "error")
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

        self._name_var.set(expense["name"])
        self._amount_var.set(str(expense["amount"]))
        self._editing = expense["name"]
        self._set_message("", "")
        self._reload()

    def _ask_delete(self, name: str) -> None:
        """Open the confirmation dialog for one expense.

        Held on self so the dialog is not garbage-collected while open,
        and the sentence is built here so the shared widget stays
        ignorant of fixed expenses.
        """
        self._set_message("", "")
        self._dialog = ConfirmDialog(
            self,
            title="Confirm delete",
            message=f"Delete fixed expense '{name}'?\n\nThis cannot be undone.",
            on_confirm=lambda: self._confirm_delete(name),
        )

    def _confirm_delete(self, name: str) -> None:
        """Actually remove the expense - only ever reached from the dialog.

        The form is reset ONLY if the expense being deleted is the one
        open for editing; deleting something else must not wipe what the
        user is currently typing.
        """
        was_editing = (self._editing is not None
                       and self._editing.casefold() == name.casefold())
        saved = self._close_form() if was_editing else None

        try:
            fixed_expenses.delete_fixed_expense(name)
        except ValueError as exc:
            if saved is not None:
                self._restore_form(saved)
            self._set_message(str(exc), "error")
            return

        self._set_message(f"✓ Deleted '{name}'.", "success")

    # -- shared row button --------------------------------------------------

    def _action(self, master, text, command, color_key, width=84):
        """Create one small ghost button and pack it into `master`.

        Ghost style (transparent face, colour in the label) keeps a row of
        two buttons from shouting; the face only appears on hover.
        `color_key` is a palette key, not a hex value. Deliberately the
        same treatment the Categories screen gives its row buttons.
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
