

import customtkinter as ctk

from app.core import theme
from app.services import budget_settings

# Display names for the three budgets, in the order they are shown.
BUDGET_LABELS = {"needs": "Needs", "wants": "Wants", "savings": "Savings"}


# ---------------------------------------------------------------------------
# INPUT PARSING - written to NEVER raise. The screen must survive
# anything a user can type into a text field.
# ---------------------------------------------------------------------------

def _parse_int(text: str):
    """Return (ok, value) for a whole-number field.

    Empty strings, signs, decimal points and letters all give
    (False, None) instead of an exception. isdecimal() rather than
    isdigit(): int() rejects a few unicode characters that isdigit()
    accepts (superscripts, for example).
    """
    text = text.strip()
    if not text.isdecimal():
        return False, None
    try:
        return True, int(text)
    except ValueError:
        return False, None


def _parse_percent(text: str):
    """Like _parse_int, but also rejects values above 100."""
    ok, value = _parse_int(text)
    if not ok or value > 100:
        return False, None
    return True, value


class SettingsScreen(ctk.CTkFrame):
    """Screen for entering the salary and the three budget percentages."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)
        self._build()
        self._reload_from_fields()  # fill the fields from the holder
        self.refresh_theme()        # then colour every widget

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        """Create the widgets once. Colours are applied in refresh_theme()."""
        pad = theme.spacing("lg")      # screen side padding
        card_pad = theme.spacing("md")  # padding inside the cards

        # Validation state, read by refresh_theme() through
        # _apply_validation_styles(). Initial values = "nothing typed yet",
        # which _reload_from_fields() replaces immediately.
        self._save_valid = False
        self._total_state = "unknown"   # "ok" (100%) | "bad" | "unknown"
        self._message_kind = ""         # "" | "error" | "success"

        # One column fills the width; row 3 (allocation card) stretches.
        #   rows: 0 title | 1 subtitle | 2 salary card
        #         3 allocation card (weight 1) | 4 salary-month card
        #         5 message | 6 button
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # -- title ---------------------------------------------------------
        self._title = ctk.CTkLabel(
            self, text="Settings",
            font=theme.font("title"), anchor="w",
        )
        self._title.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._subtitle = ctk.CTkLabel(
            self,
            text="Set your monthly salary and how it splits across your budgets.",
            font=theme.font("subtitle"), anchor="w",
        )
        self._subtitle.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # -- salary card ---------------------------------------------------
        self._salary_card = ctk.CTkFrame(
            self, corner_radius=theme.radius("lg"), border_width=1,
        )
        self._salary_card.grid(
            row=2, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("lg")),
        )
        # Left column (labels) takes the leftover width so the field
        # stays pinned to the right edge as the window grows.
        self._salary_card.grid_columnconfigure(0, weight=1)

        self._salary_caption = ctk.CTkLabel(
            self._salary_card, text="MONTHLY SALARY",
            font=theme.font("caption"), anchor="w",
        )
        self._salary_caption.grid(
            row=0, column=0, sticky="w",
            padx=(card_pad, 0), pady=(card_pad, 0),
        )

        self._salary_helper = ctk.CTkLabel(
            self._salary_card,
            text="Take-home income to allocate each month.",
            font=theme.font("caption"), anchor="w",
        )
        self._salary_helper.grid(
            row=1, column=0, sticky="w",
            padx=(card_pad, 0), pady=(theme.spacing("xs"), card_pad),
        )

        # "Rs." prefix + the input itself, right-aligned as one block.
        salary_field = ctk.CTkFrame(self._salary_card, fg_color="transparent")
        salary_field.grid(
            row=0, column=1, rowspan=2, sticky="e",
            padx=(theme.spacing("sm"), card_pad), pady=card_pad,
        )
        self._salary_prefix = ctk.CTkLabel(
            salary_field, text="Rs.",
            font=theme.font("value"), text_color=theme.color("text_secondary"),
        )
        self._salary_prefix.pack(side="left")

        # Field widths (200 / 70 / 140) are pixel sizes for inputs, not
        # colours/fonts/spacing/radius - same precedent as main.py's
        # sidebar width. Everything else comes from theme.py.
        self._salary_entry = ctk.CTkEntry(
            salary_field, width=200, justify="right",
            font=theme.font("body"), placeholder_text="e.g. 120000",
        )
        self._salary_entry.pack(side="left", padx=(theme.spacing("xs"), 0))

        # -- allocation card -----------------------------------------------
        # A grid table, one row per budget:
        #   [Needs]      [ 50 ] %          Rs. 60,000
        #   col0 name (weight 1) | col1 field | col2 "%"
        #   col3 spacer (weight 1) | col4 allocated amount (right edge)
        # The two weight-1 columns split the free space, so the name hugs
        # the left edge and the amount hugs the right edge.
        self._alloc_card = ctk.CTkFrame(
            self, corner_radius=theme.radius("lg"), border_width=1,
        )
        self._alloc_card.grid(
            row=3, column=0, sticky="nsew",
            padx=pad, pady=(0, theme.spacing("lg")),
        )
        self._alloc_card.grid_columnconfigure(0, weight=1)
        self._alloc_card.grid_columnconfigure(3, weight=1)

        self._alloc_caption = ctk.CTkLabel(
            self._alloc_card, text="BUDGET ALLOCATION",
            font=theme.font("caption"), anchor="w",
        )
        self._alloc_caption.grid(
            row=0, column=0, columnspan=5, sticky="w",
            padx=card_pad, pady=(card_pad, theme.spacing("sm")),
        )

        # Per-budget widgets, kept in dicts so refresh_theme() and the
        # live-update logic can walk them by settings key.
        self._pct_names: list = []    # name labels, in display order
        self._pct_entries: dict = {}   # key -> CTkEntry
        self._pct_marks: dict = {}     # key -> the "%" label
        self._alloc_values: dict = {}  # key -> the "Rs. ..." preview label

        for row, key in enumerate(budget_settings.BUDGET_KEYS, start=1):
            name = ctk.CTkLabel(
                self._alloc_card, text=BUDGET_LABELS[key],
                font=theme.font("value"), anchor="w",
            )
            name.grid(
                row=row, column=0, sticky="w",
                padx=(card_pad, 0), pady=(0, theme.spacing("xs")),
            )
            self._pct_names.append(name)

            entry = ctk.CTkEntry(
                self._alloc_card, width=70, justify="right",
                font=theme.font("body"),
            )
            entry.grid(
                row=row, column=1, sticky="w",
                pady=(0, theme.spacing("xs")),
            )
            # CTkEntry.bind() forwards to the inner tkinter entry, so this
            # fires on every keystroke (and on paste / focus-out).
            entry.bind("<KeyRelease>", self._on_field_changed)
            entry.bind("<FocusOut>", self._on_field_changed)

            mark = ctk.CTkLabel(
                self._alloc_card, text="%",
                font=theme.font("value"), anchor="w",
            )
            mark.grid(
                row=row, column=2, sticky="w",
                padx=(theme.spacing("xs"), 0), pady=(0, theme.spacing("xs")),
            )

            value = ctk.CTkLabel(
                self._alloc_card, text="",
                font=theme.font("value"), anchor="e", justify="right",
                width=140,  # reserved so the row does not jitter while typing
            )
            value.grid(
                row=row, column=4, sticky="e",
                padx=(0, card_pad), pady=(0, theme.spacing("xs")),
            )

            self._pct_entries[key] = entry
            self._pct_marks[key] = mark
            self._alloc_values[key] = value

        # Salary field gets the same keystroke binding as the others.
        self._salary_entry.bind("<KeyRelease>", self._on_field_changed)
        self._salary_entry.bind("<FocusOut>", self._on_field_changed)

        # -- total row (validates the 100% rule at a glance) ---------------
        self._total_caption = ctk.CTkLabel(
            self._alloc_card, text="TOTAL",
            font=theme.font("value"), anchor="w",
        )
        self._total_caption.grid(
            row=4, column=0, sticky="w",
            padx=(card_pad, 0), pady=(theme.spacing("md"), card_pad),
        )
        self._total_value = ctk.CTkLabel(
            self._alloc_card, text="",
            font=theme.font("value"), anchor="e", justify="right", width=140,
        )
        self._total_value.grid(
            row=4, column=4, sticky="e",
            padx=(0, card_pad), pady=(theme.spacing("md"), card_pad),
        )

        # -- salary-month card --------------------------------
        # Which day of the month the user's salary cycle begins on. Same
        # shape as the salary card: caption + helper on the left, the
        # control pinned to the right edge, so the two cards read as one
        # form. A DROPDOWN rather than a text field because the holder
        # only accepts 1-28 and a menu cannot offer an invalid value;
        # the holder still validates (defence in depth) and the value is
        # written by the SAME Save button as everything else - this
        # screen is one atomic form, so the day is not applied early.
        self._cycle_card = ctk.CTkFrame(
            self, corner_radius=theme.radius("lg"), border_width=1,
        )
        self._cycle_card.grid(
            row=4, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("lg")),
        )
        self._cycle_card.grid_columnconfigure(0, weight=1)

        self._cycle_caption = ctk.CTkLabel(
            self._cycle_card, text="SALARY MONTH STARTS ON",
            font=theme.font("caption"), anchor="w",
        )
        self._cycle_caption.grid(
            row=0, column=0, sticky="w",
            padx=(card_pad, 0), pady=(card_pad, 0),
        )

        self._cycle_helper = ctk.CTkLabel(
            self._cycle_card,
            text=("The day your salary month begins - spending is grouped "
                  "into months starting from this day."),
            font=theme.font("caption"), anchor="w",
        )
        self._cycle_helper.grid(
            row=1, column=0, sticky="w",
            padx=(card_pad, 0), pady=(theme.spacing("xs"), card_pad),
        )

        # 1..28 as strings: the menu's values are display text, and the
        # holder's get/set are what decide whether a day is legal.
        # width/dynamic_resizing are layout sizes (same precedent as the
        # 200/70/140 inputs above), fixed so the box cannot change size
        # when the day changes from 1 to 28.
        self._cycle_menu = ctk.CTkOptionMenu(
            self._cycle_card,
            values=[str(day) for day in range(
                budget_settings.MONTH_START_DAY_MIN,
                budget_settings.MONTH_START_DAY_MAX + 1,
            )],
            width=100,
            dynamic_resizing=False,
            corner_radius=theme.radius("sm"),
            # Same palette as every other control in this form: the face
            # is the recessed surface, the button square is the border
            # (so the arrow stays visible in either mode) and the
            # dropdown opens on a card-coloured panel.
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
        self._cycle_menu.grid(
            row=0, column=1, rowspan=2, sticky="e",
            padx=(theme.spacing("sm"), card_pad), pady=card_pad,
        )

        # -- inline message (warning / saved confirmation) -----------------
        # Always gridded (even when empty) so the layout never jumps.
        self._message = ctk.CTkLabel(
            self, text="", font=theme.font("body"),
            anchor="w", justify="left",
        )
        self._message.grid(
            row=5, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("sm")),
        )

        # -- save button ---------------------------------------------------
        self._save_button = ctk.CTkButton(
            self, text="Save Settings",
            font=theme.font("section"),
            # CTA height as a sum of theme steps: xl (36) + sm (10) = 46,
            # identical to the Dashboard's Add Expense button.
            height=theme.spacing("xl") + theme.spacing("sm"),
            corner_radius=theme.radius("md"),
            border_width=0,
            command=self._on_save,
        )
        self._save_button.grid(
            row=6, column=0, sticky="ew",
            padx=pad, pady=(0, pad),
        )

    # -- input handling -----------------------------------------------------

    def _reload_from_fields(self) -> None:
        """Copy the holder's current values into the fields.

        Runs at startup (and could run again if some other part of the
        app changed the holder behind this screen's back).
        """
        self._salary_entry.delete(0, "end")
        self._salary_entry.insert(0, str(budget_settings.get_salary()))

        percentages = budget_settings.get_percentages()
        for key in budget_settings.BUDGET_KEYS:
            entry = self._pct_entries[key]
            entry.delete(0, "end")
            entry.insert(0, str(percentages[key]))

        # the salary-cycle day. CTkOptionMenu takes its value
        # as the exact string from its list, so set() it rather than
        # insert() - there is no text cursor to preserve here.
        self._cycle_menu.set(str(budget_settings.get_month_start_day()))

        # Programmatic inserts fire no key events, so validate by hand.
        self._update_from_fields()

    def _on_field_changed(self, event=None) -> None:
        """Called on every keystroke (and when a field loses focus):
        refresh the rupee previews, the total and the warning."""
        self._update_from_fields()

    def _update_from_fields(self) -> bool:
        """Re-read all four fields, update every preview, validate, and
        show or clear the inline message. Returns True when the current
        input is a valid plan (the only state in which Save may run).

        This is the heart of the screen: one function keeps the previews,
        the total row, the warning and the Save button in sync with
        whatever is in the fields right now.
        """
        # --- parse everything (never raises) -----------------------------
        salary_ok, salary = _parse_int(self._salary_entry.get())
        pct_ok, pcts = {}, {}
        for key in budget_settings.BUDGET_KEYS:
            ok, value = _parse_percent(self._pct_entries[key].get())
            pct_ok[key], pcts[key] = ok, value
        all_pcts_ok = all(pct_ok.values())
        total = sum(pcts.values()) if all_pcts_ok else None

        # --- live preview: what each percentage would be worth ------------
        for key in budget_settings.BUDGET_KEYS:
            if salary_ok and pct_ok[key]:
                amount = salary * pcts[key] // 100
                self._alloc_values[key].configure(text=f"Rs. {amount:,}")
            else:
                # Cannot compute (bad salary or bad percentage).
                self._alloc_values[key].configure(text="—")

        # --- total row ----------------------------------------------------
        if total is None:
            self._total_value.configure(text="—")
            self._total_state = "unknown"
        else:
            self._total_value.configure(text=f"{total}%")
            self._total_state = "ok" if total == 100 else "bad"

        # --- inline message: the first failing rule wins -------------------
        if not salary_ok:
            message, kind = "Enter a whole-number monthly salary (0 or more).", "error"
        elif not all_pcts_ok:
            message, kind = "Enter whole numbers from 0 to 100 for each budget.", "error"
        elif total != 100:
            message, kind = (
                f"Needs + Wants + Savings must add up to 100% - currently {total}%.",
                "error",
            )
        else:
            message, kind = "", ""

        # --- may we save? --------------------------------------------------
        valid = salary_ok and all_pcts_ok and total == 100
        self._save_valid = valid
        self._message_kind = kind
        self._message.configure(text=message)
        self._apply_validation_styles()
        return valid

    def _on_save(self) -> None:
        """Write the fields into the shared settings holder.

        budget_settings.set_*() notify their subscribers, so the Dashboard
        picks the new plan up immediately - no main.py changes needed.
        """
        # The button is disabled while invalid, but re-validate anyway:
        # never trust the UI alone (cheap insurance against bugs).
        if not self._update_from_fields():
            return

        # the salary-cycle day, read and checked BEFORE any
        # write so a refusal can never leave the form half-saved. The
        # dropdown only offers legal days, but this screen validates
        # every field first (friendly inline message) exactly like the
        # salary and percentages above - and set_month_start_day()
        # enforces the same 1-28 rule again in the holder.
        day_ok, month_start_day = _parse_int(self._cycle_menu.get())
        if not day_ok or not (
            budget_settings.MONTH_START_DAY_MIN
            <= month_start_day <= budget_settings.MONTH_START_DAY_MAX
        ):
            self._message_kind = "error"
            self._message.configure(
                text=(f"Month start day must be "
                      f"{budget_settings.MONTH_START_DAY_MIN}-"
                      f"{budget_settings.MONTH_START_DAY_MAX}.")
            )
            self._apply_validation_styles()
            return

        salary = _parse_int(self._salary_entry.get())[1]
        pcts = {key: _parse_percent(self._pct_entries[key].get())[1]
                for key in budget_settings.BUDGET_KEYS}

        budget_settings.set_salary(salary)
        budget_settings.set_percentages(pcts["needs"], pcts["wants"], pcts["savings"])
        budget_settings.set_month_start_day(month_start_day)

        # Confirmation replaces whatever the message row was showing.
        self._message_kind = "success"
        self._message.configure(text="✓ Saved - the Dashboard now uses these figures.")
        self._apply_validation_styles()

    def _apply_validation_styles(self) -> None:
        """Colour the total row, the message and the Save button from the
        current validation state.

        Called after every edit AND from refresh_theme(), so the
        dark/light flip can never leave these three stale.
        """
        # Total: green at exactly 100%, red when it is wrong, muted when
        # the input is not even a number.
        if self._total_state == "ok":
            total_color = theme.color("success")
        elif self._total_state == "bad":
            total_color = theme.color("danger")
        else:
            total_color = theme.color("text_secondary")
        self._total_value.configure(text_color=total_color)

        # Inline message: red for warnings, green for the saved note.
        # (When the text is empty the colour is invisible anyway.)
        message_colors = {
            "": theme.color("text_secondary"),
            "error": theme.color("danger"),
            "success": theme.color("success"),
        }
        self._message.configure(text_color=message_colors[self._message_kind])

        # Save button. A disabled CTkButton only greys its TEXT (see the
        # ctk_button.py source), so we repaint the face too - disabled
        # reads as a flat grey block, enabled as the accent CTA.
        if self._save_valid:
            self._save_button.configure(
                state="normal",
                fg_color=theme.color("accent"),
                hover_color=theme.color("accent_hover"),
                text_color=theme.color("text_on_accent"),
            )
        else:
            self._save_button.configure(
                state="disabled",
                fg_color=theme.color("surface"),
                hover_color=theme.color("surface"),
                text_color=theme.color("text_secondary"),
            )

    # -- theming ------------------------------------------------------------

    def refresh_theme(self) -> None:
        """Re-read every colour from theme.py and apply it to this screen.

        main.py calls this once at startup and again each time the
        dark/light switch is flipped - so EVERY widget built in _build()
        must be configured here.
        """
        self.configure(fg_color=theme.color("bg"))
        self._title.configure(text_color=theme.color("text"))
        self._subtitle.configure(text_color=theme.color("text_secondary"))

        # Salary card.
        self._salary_card.configure(
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._salary_caption.configure(text_color=theme.color("text_secondary"))
        self._salary_helper.configure(text_color=theme.color("text_secondary"))
        self._salary_prefix.configure(text_color=theme.color("text_secondary"))
        self._configure_entry(self._salary_entry)

        # Allocation card + its table.
        self._alloc_card.configure(
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._alloc_caption.configure(text_color=theme.color("text_secondary"))
        self._total_caption.configure(text_color=theme.color("text_secondary"))
        for name_label in self._pct_names:
            name_label.configure(text_color=theme.color("text"))
        for key in budget_settings.BUDGET_KEYS:
            self._configure_entry(self._pct_entries[key])
            self._pct_marks[key].configure(text_color=theme.color("text_secondary"))
            self._alloc_values[key].configure(text_color=theme.color("text"))

        # Salary-month card + its dropdown (Phase 8.1). The dropdown's
        # face and arrow square match the text fields, so the control
        # reads as part of the same form in both palettes.
        self._cycle_card.configure(
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._cycle_caption.configure(text_color=theme.color("text_secondary"))
        self._cycle_helper.configure(text_color=theme.color("text_secondary"))
        self._cycle_menu.configure(
            fg_color=theme.color("surface"),
            button_color=theme.color("border"),
            button_hover_color=theme.color("accent_soft"),
            text_color=theme.color("text"),
            text_color_disabled=theme.color("text_secondary"),
            dropdown_fg_color=theme.color("card_bg"),
            dropdown_hover_color=theme.color("border"),
            dropdown_text_color=theme.color("text"),
        )

        # Message + total row + save button (state-driven colours).
        self._apply_validation_styles()

    def _configure_entry(self, entry) -> None:
        """Apply the shared field palette to one text input.

        Kept as a helper because the salary field and the three
        percentage fields must always look identical.
        """
        entry.configure(
            fg_color=theme.color("surface"),          # recessed field face
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text_color=theme.color("text_secondary"),
        )
