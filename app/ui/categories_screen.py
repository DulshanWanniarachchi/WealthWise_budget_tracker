"""
categories_screen.py - the Categories screen (Phase 4).

WHAT IT DOES
  Lists the three budgets (Needs / Wants / Savings) with every category
  under them, sub-items indented beneath their category, and lets the
  user ADD, RENAME and DELETE both levels. Every action writes straight
  into app.services.category_settings and applies immediately - there is
  no Save button here, unlike Settings, which validates four fields as
  one atomic plan before writing anything.

WHY A SIDEBAR SCREEN INSTEAD OF A SECTION ON SETTINGS
  Settings is an ATOMIC form: four fields are validated together, one
  Save button, and invalid input blocks the write. Category management
  is the opposite - independent one-row actions that apply the moment
  you click, with a confirmation dialog in between. Folding it into
  settings_screen.py would push that file (already ~490 lines) past a
  thousand lines and would sit two different interaction models behind
  one Save button. A separate screen keeps each file focused and lets
  main.py's generic screen switching do the work. main.py was touched
  ONLY to register this screen (import, nav item, screens dict, and the
  sidebar row numbers that shift because of the third nav button).

CONTRACT WITH main.py (identical to the Dashboard and Settings)
  * every colour / font / spacing / radius comes from app.core.theme
  * refresh_theme() repaints EVERY widget this screen creates. Rows are
    rebuilt by _reload() using the active palette, so they cannot go
    stale; only the static chrome is recoloured by hand below.

HOW THE LIST IS BUILT
  _reload() is the ONLY function that creates row widgets. It runs
    (a) once at startup, from refresh_theme(),
    (b) after every successful change - __init__ subscribes it to the
        holder, and the holder notifies AFTER storing, and
    (c) on every dark/light flip, through refresh_theme().
  So action handlers never build rows themselves: they call the holder
  and report the outcome. Exactly one rebuild per change, always in sync.

  Consequence worth knowing: a REFUSED change (ValueError from the
  holder) stores nothing, therefore notifies nothing, therefore rebuilds
  nothing - so the field the user was typing in is still alive and keeps
  its text. Handlers only have to put the state back (see _commit_field).
"""

import customtkinter as ctk

from app.core import theme
from app.services import budget_settings, category_settings
# Phase 5: the confirmation dialog moved out of this file into
# app/widgets/ so the Fixed Expenses screen can use the same box instead
# of a second copy of it. Nothing about its behaviour changed.
from app.widgets.confirm_dialog import ConfirmDialog

# Which palette accent identifies each budget. It now lives next to
# BUDGET_KEYS / BUDGET_LABELS in budget_settings - one canonical mapping
# that every budget-coloured screen (this one, Fixed Expenses) reads from
# instead of each keeping its own copy.
BUDGET_ACCENTS = budget_settings.BUDGET_ACCENTS

# Row-control sizes, in PIXELS. Same precedent as the Settings screen's
# input widths (200 / 70 / 140) and main.py's sidebar width: these are
# control dimensions, not colours / fonts / spacing / radius - those all
# still come from theme.py.
ACTION_W = 68          # Rename / Delete / Cancel
ACTION_W_WIDE = 92     # "+ Sub-item" needs the extra room
ACTION_W_COMMIT = 60   # Add / Save
ACTION_H = 26          # buttons and the inline field share it, so rows line up


# ---------------------------------------------------------------------------
# THE SCREEN
# ---------------------------------------------------------------------------

class CategoriesScreen(ctk.CTkFrame):
    """Screen for managing the category tree under Needs / Wants / Savings."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)
        self._build()
        # Other screens could change the holder later; rebuild when they do.
        # The holder ignores duplicate registrations of the same callable.
        category_settings.subscribe(self._reload)
        self.refresh_theme()   # paints the chrome AND builds the rows

    # -- construction -------------------------------------------------------

    def _build(self) -> None:
        """Create the static chrome once. Colours are applied in
        refresh_theme(); the list itself is built by _reload()."""
        pad = theme.spacing("lg")

        # --- state, read by _reload() while it decides what to render -----
        self._message_kind = ""       # "" | "error" | "success"
        self._add_target = None       # open "new name" field, or None
        self._rename_target = None    # open "rename" field, or None
        self._prefill = ""            # text to restore into a rebuilt field
        self._active_entry = None     # the field widget on screen right now
        self._dialog = None           # keeps a confirm box alive (no GC mid-air)

        # One column fills the width; row 2 (the list) stretches.
        #   rows: 0 title | 1 subtitle | 2 list (weight 1) | 3 message
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._title = ctk.CTkLabel(
            self, text="Categories",
            font=theme.font("title"), anchor="w",
        )
        self._title.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._subtitle = ctk.CTkLabel(
            self,
            text="Organise what each budget is spent on. Changes apply immediately.",
            font=theme.font("subtitle"), anchor="w",
        )
        self._subtitle.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # The scrollable area holds the three budget cards. The scrollbar
        # is themed here too so it does not fall back to CustomTkinter's
        # own grey (main.py syncs CTk's appearance mode, but its default
        # colours are not ours).
        self._list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._list.grid(
            row=2, column=0, sticky="nsew",
            padx=pad, pady=(0, theme.spacing("md")),
        )
        # Children of a CTkScrollableFrame are gridded onto its inner
        # window, so this makes column 0 take the full usable width.
        self._list.grid_columnconfigure(0, weight=1)

        # Inline feedback. Always gridded (even when empty) so the layout
        # never jumps - same trick as the Settings screen.
        self._message = ctk.CTkLabel(
            self, text="", font=theme.font("body"),
            anchor="w", justify="left",
        )
        self._message.grid(
            row=3, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("sm")),
        )

    # -- state helpers ------------------------------------------------------

    def _close_fields(self):
        """Close any open add/rename field and return its previous state.

        Called BEFORE a change is attempted: the holder notifies on
        success, which rebuilds the list while the handler is still
        running, and the rebuild must see the field as already closed.
        """
        saved = (self._add_target, self._rename_target, self._prefill)
        self._add_target = None
        self._rename_target = None
        self._prefill = ""
        return saved

    def _restore_fields(self, saved) -> None:
        """Put back what _close_fields took - used only when the holder
        REFUSED the value, because a refusal never rebuilds anything."""
        self._add_target, self._rename_target, self._prefill = saved

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

    # -- opening / committing fields ---------------------------------------

    def _start_add(self, target) -> None:
        """Open a blank 'new name' field. target identifies the parent:
        ("category", budget) or ("item", budget, category_name)."""
        self._set_message("", "")
        self._close_fields()
        self._add_target = target
        self._reload()

    def _start_rename(self, target) -> None:
        """Open a prefilled rename field. target names the node:
        ("category", budget, name) or ("item", budget, category, name)."""
        self._set_message("", "")
        self._close_fields()
        self._rename_target = target
        self._reload()

    def _commit_field(self, entry, *, budget, level, parent,
                      initial, action) -> None:
        """Validate + store whatever the open field holds.

        `level` is "category" or "item"; `parent` is the category an item
        belongs to (None for category level); `action` is "add" or
        "rename"; `initial` is the name a rename started from.

        Which field is open is not passed in: _close_fields() reads it
        straight off the screen, which is the single source of truth.
        """
        text = entry.get()
        saved = self._close_fields()

        # Renaming a node to the name it already has is a deliberate
        # no-op in the holder (no notify, no rebuild) - so close the
        # field here instead of waiting for a rebuild that never comes.
        if action == "rename" and text.strip().casefold() == initial.casefold():
            self._reload()
            self._set_message("Name unchanged.", "")
            return

        try:
            if action == "add":
                if level == "category":
                    category_settings.add_category(budget, text)
                else:
                    category_settings.add_item(budget, parent, text)
            else:
                if level == "category":
                    category_settings.rename_category(budget, initial, text)
                else:
                    category_settings.rename_item(budget, parent, initial, text)
        except ValueError as exc:
            # Nothing was stored, so nothing was notified, so the field
            # the user is looking at is still alive: put the state back
            # and keep the caret in it so they can fix the name.
            self._restore_fields(saved)
            entry.focus_set()
            self._set_message(str(exc), "error")
            return

        # Success: the holder already rebuilt the list (field gone).
        verb = "Added" if action == "add" else "Renamed to"
        self._set_message(f"✓ {verb} '{text.strip()}'.", "success")

    def _cancel_field(self) -> None:
        """Escape / Cancel: drop the open field and clear the message."""
        self._close_fields()
        self._set_message("", "")
        self._reload()

    # -- deletion -----------------------------------------------------------

    def _ask_delete(self, path) -> None:
        """Open the confirmation dialog for a category or a sub-item.

        path shapes match _start_rename's targets:
          ("category", budget, name)  |  ("item", budget, category, name)
        """
        self._set_message("", "")

        if path[0] == "category":
            budget, name = path[1], path[2]
            subject = f"category '{name}'"
            # Warn about the cascade, but only when there is a cascade:
            # deleting a category takes its sub-items with it (they live
            # inside the node), so say so - a category with none is just
            # a category.
            items = 0
            for category in category_settings.get_categories(budget):
                if category["name"] == name:
                    items = len(category["items"])
            extra = ""
            if items:
                extra = (f"\n\nIts {items} sub-item"
                         f"{'s' if items != 1 else ''} will be deleted too.")
        else:
            budget, name = path[1], path[3]
            subject = f"sub-item '{name}'"
            extra = ""

        # Held on self so the dialog is not garbage-collected while open.
        self._dialog = ConfirmDialog(
            self,
            title="Confirm delete",
            message=f"Delete {subject}?{extra}\n\nThis cannot be undone.",
            on_confirm=lambda: self._confirm_delete(path),
        )

    def _confirm_delete(self, path) -> None:
        """Actually remove the node - only ever reached from the dialog."""
        saved = self._close_fields()
        try:
            if path[0] == "category":
                category_settings.delete_category(path[1], path[2])
            else:
                category_settings.delete_item(path[1], path[2], path[3])
        except ValueError as exc:
            self._restore_fields(saved)
            self._set_message(str(exc), "error")
            return
        self._set_message(f"✓ Deleted '{path[-1]}'.", "success")

    # -- rebuilding the list ------------------------------------------------

    def _reload(self) -> None:
        """Rebuild the three budget cards from the holder.

        This is the only place row widgets are created, which is what
        makes refresh_theme() complete by construction: every row is
        born already painted in the active palette.
        """
        # Keep whatever the user was typing - a rebuild triggered by a
        # theme flip or by another screen must not wipe an open field.
        prefill = ""
        if self._active_entry is not None:
            try:
                prefill = self._active_entry.get()
            except Exception:   # already gone - nothing worth keeping
                prefill = ""
        self._prefill = prefill

        for child in self._list.winfo_children():
            child.destroy()
        self._active_entry = None

        for row, budget in enumerate(budget_settings.BUDGET_KEYS):
            card = self._build_budget_card(self._list, budget)
            card.grid(
                row=row, column=0, sticky="ew",
                pady=(0, theme.spacing("md")),
            )

        # No field was rebuilt, so drop the saved text: it must not leak
        # into some later, unrelated field.
        if self._active_entry is None:
            self._prefill = ""

    # -- one budget card ----------------------------------------------------

    def _build_budget_card(self, master, budget: str):
        """Build one card: header, its categories, then the add row."""
        pad = theme.spacing("md")
        label = budget_settings.BUDGET_LABELS[budget]
        categories = category_settings.get_categories(budget)

        card = ctk.CTkFrame(
            master,
            corner_radius=theme.radius("lg"),
            border_width=1,
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        card.grid_columnconfigure(0, weight=1)

        # --- header: accent dot + budget name + live count ---------------
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("sm")),
        )
        header.grid_columnconfigure(1, weight=1)  # pushes the count right

        dot = ctk.CTkLabel(
            header, text="●", font=theme.font("section"),
            text_color=theme.color(BUDGET_ACCENTS[budget]),
        )
        dot.grid(row=0, column=0, sticky="w")

        name_label = ctk.CTkLabel(
            header, text=label, font=theme.font("section"),
            text_color=theme.color("text"), anchor="w",
        )
        name_label.grid(
            row=0, column=1, sticky="w",
            padx=(theme.spacing("xs"), 0),
        )

        count = len(categories)
        count_label = ctk.CTkLabel(
            header,
            text=f"{count} {'category' if count == 1 else 'categories'}",
            font=theme.font("caption"),
            text_color=theme.color("text_secondary"), anchor="e",
        )
        count_label.grid(row=0, column=2, sticky="e")

        # --- rows ----------------------------------------------------------
        row = 1

        # A budget the user has emptied shows a note instead of nothing -
        # no crash, no blank card, and the add row below still works.
        if not categories:
            empty = ctk.CTkLabel(
                card, text=f"No categories under {label} yet - add one below.",
                font=theme.font("body"),
                text_color=theme.color("text_secondary"), anchor="w",
            )
            empty.grid(
                row=row, column=0, sticky="ew",
                padx=pad, pady=(0, theme.spacing("xs")),
            )
            row += 1

        for category in categories:
            self._build_category_row(card, row, budget, category)
            row += 1

            # Sub-items sit directly beneath their category, indented one
            # level. EVERY category may have them - none is special-cased,
            # so a category the user gives items to renders them too.
            for item in category["items"]:
                self._build_item_row(card, row, budget, category["name"], item)
                row += 1

            # An open "new sub-item" field sits directly beneath the
            # category it belongs to, so the nesting reads correctly.
            if self._add_target == ("item", budget, category["name"]):
                self._build_field_row(
                    card, row, budget=budget, level="item",
                    parent=category["name"],
                    initial="", action="add",
                )
                row += 1

        # --- add row: a field when open, otherwise the button -------------
        if self._add_target == ("category", budget):
            self._build_field_row(
                card, row, budget=budget, level="category", parent=None,
                initial="", action="add",
            )
        else:
            add = ctk.CTkButton(
                card, text="+ Add category",
                height=ACTION_H, corner_radius=theme.radius("sm"),
                font=theme.font("caption"),
                fg_color="transparent",
                hover_color=theme.color("surface"),
                text_color=theme.color("accent_text"),
                command=lambda: self._start_add(("category", budget)),
            )
            add.grid(
                row=row, column=0, sticky="w",
                padx=pad, pady=(theme.spacing("xs"), pad),
            )

        return card

    # -- one category row ---------------------------------------------------

    def _build_category_row(self, master, row, budget: str, category) -> None:
        """A category: its name plus Rename / Delete / + Sub-item buttons,
        or an inline field if this one is being renamed."""
        name = category["name"]
        pad = theme.spacing("md")

        if self._rename_target == ("category", budget, name):
            self._build_field_row(
                master, row, budget=budget, level="category", parent=None,
                initial=name, action="rename",
            )
            return

        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid(
            row=row, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("xs")),
        )
        bar.grid_columnconfigure(0, weight=1)  # name left, buttons right

        # Categories use the bold "value" font so the two levels of the
        # tree are distinguishable even without the indent.
        label = ctk.CTkLabel(
            bar, text=name, font=theme.font("value"),
            text_color=theme.color("text"), anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        # Pack order is left-to-right. Delete wears danger; the other two
        # are neutral, and all three are "ghost" buttons (transparent
        # face, colour in the label) so a list of them stays quiet.
        self._action(actions, "Rename",
                     lambda: self._start_rename(("category", budget, name)),
                     "text_secondary")
        self._action(actions, "Delete",
                     lambda: self._ask_delete(("category", budget, name)),
                     "danger")
        self._action(actions, "+ Sub-item",
                     lambda: self._start_add(("item", budget, name)),
                     "accent_text", width=ACTION_W_WIDE)

    # -- one sub-item row ---------------------------------------------------

    def _build_item_row(self, master, row, budget: str, category_name: str,
                        item) -> None:
        """A sub-item: indented, with Rename / Delete only (a sub-item has
        no level beneath it), or an inline rename field."""
        name = item["name"]
        # Left inset = the card's own padding PLUS the nesting indent.
        pad = theme.spacing("md")
        inset = pad + theme.spacing("lg")

        if self._rename_target == ("item", budget, category_name, name):
            self._build_field_row(
                master, row, budget=budget, level="item", parent=category_name,
                initial=name, action="rename",
            )
            return

        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid(
            row=row, column=0, sticky="ew",
            padx=(inset, pad), pady=(0, theme.spacing("xs")),
        )
        bar.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            bar, text=name, font=theme.font("body"),
            text_color=theme.color("text"), anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        self._action(actions, "Rename",
                     lambda: self._start_rename(("item", budget, category_name, name)),
                     "text_secondary")
        self._action(actions, "Delete",
                     lambda: self._ask_delete(("item", budget, category_name, name)),
                     "danger")

    # -- the inline add / rename field -------------------------------------

    def _build_field_row(self, master, row, *, budget, level, parent,
                         initial, action) -> None:
        """An inline text field with a commit button and a Cancel.

        Enter commits, Escape cancels. On success the holder rebuilds
        the list and this row simply disappears; on failure it stays
        exactly as the user left it (see _commit_field).
        """
        pad = theme.spacing("md")
        indent = theme.spacing("lg") if level == "item" else 0

        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid(
            row=row, column=0, sticky="ew",
            padx=(pad + indent, pad), pady=(0, theme.spacing("xs")),
        )
        bar.grid_columnconfigure(0, weight=1)   # field takes the spare width

        if action == "add":
            placeholder = ("New sub-item name" if level == "item"
                           else "New category name")
            commit_text = "Add"
        else:
            placeholder = ""
            commit_text = "Save"

        entry = ctk.CTkEntry(
            bar, height=ACTION_H, font=theme.font("body"),
            placeholder_text=placeholder,
            fg_color=theme.color("surface"),
            border_color=theme.color("border"),
            text_color=theme.color("text"),
            placeholder_text_color=theme.color("text_secondary"),
        )
        entry.grid(row=0, column=0, sticky="ew",
                   padx=(0, theme.spacing("sm")))

        # A rebuild mid-edit (theme flip) hands the user's text back; the
        # first build has no prefill, so it falls through to `initial`.
        if self._prefill:
            entry.insert(0, self._prefill)
        elif initial:
            entry.insert(0, initial)
        self._prefill = ""          # consumed exactly once
        self._active_entry = entry

        commit = ctk.CTkButton(
            bar, text=commit_text,
            width=ACTION_W_COMMIT, height=ACTION_H,
            corner_radius=theme.radius("sm"), font=theme.font("caption"),
            fg_color=theme.color("accent"),
            hover_color=theme.color("accent_hover"),
            text_color=theme.color("text_on_accent"),
            command=lambda: self._commit_field(
                entry, budget=budget, level=level, parent=parent,
                initial=initial, action=action,
            ),
        )
        commit.grid(row=0, column=1, sticky="e")

        cancel = ctk.CTkButton(
            bar, text="Cancel",
            width=ACTION_W, height=ACTION_H,
            corner_radius=theme.radius("sm"), font=theme.font("caption"),
            fg_color="transparent",
            hover_color=theme.color("surface"),
            text_color=theme.color("text_secondary"),
            command=self._cancel_field,
        )
        cancel.grid(row=0, column=2, sticky="e")

        # CTkEntry.bind() forwards to the inner tkinter entry, so these
        # fire on real key presses. <Return> commits, <Escape> backs out.
        entry.bind("<Return>",
                   lambda _e: self._commit_field(
                       entry, budget=budget, level=level, parent=parent,
                       initial=initial, action=action))
        entry.bind("<Escape>", lambda _e: self._cancel_field())

        # Land the caret in the field, with existing text selected so a
        # rename can be typed straight over.
        entry.focus_set()
        if initial:
            entry.select_range(0, "end")
            entry.icursor("end")

    # -- shared row button --------------------------------------------------

    def _action(self, master, text, command, color_key, width=ACTION_W):
        """Create one small ghost button and pack it into `master`.

        Ghost style (transparent face, colour in the label) keeps a row
        of three buttons from shouting; the face only appears on hover.
        `color_key` is a palette key, not a hex value.
        """
        button = ctk.CTkButton(
            master, text=text,
            width=width, height=ACTION_H,
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
        flip. The static chrome is recoloured here; the list below is
        rebuilt by _reload(), so every row widget is recreated already
        painted in the active palette - nothing can be missed.
        """
        self.configure(fg_color=theme.color("bg"))
        self._title.configure(text_color=theme.color("text"))
        self._subtitle.configure(text_color=theme.color("text_secondary"))
        self._list.configure(
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._apply_message_style()
        self._reload()
