"""
Budget Tracker - Phase 1 entry point.

Run it with:   python main.py

WHAT THIS FILE DOES (Phase 1 = the shell only)
  1. Creates the main window ("Budget Tracker", sensible default size).
  2. Builds a fixed-width sidebar on the left with:
       - the app brand
       - navigation buttons (Dashboard, Settings, Categories,
         Fixed Expenses, Daily Expenses, Reports)
       - a dark/light switch that re-themes the app live
       - a status label proving the SQLite connection works
  3. Builds a content area on the right that shows ONE screen at a time.
  4. Opens data/budget.db once to prove the connection (no tables yet).

SCREEN SWITCHING - the short version:
  All screens are created once and live inside `self.content`. show_screen()
  packs the screen you want and pack_forget()s the rest, then updates the
  sidebar highlight. Nothing is ever destroyed or rebuilt.

THEMING - the short version:
  Every colour comes from app/core/theme.py. Flipping the switch updates the
  active palette there, tells CustomTkinter to switch its own defaults, and
  then calls refresh_theme() on the shell (sidebar) and on each screen, so
  every explicitly-coloured widget is re-painted immediately.
"""

import ctypes
import sqlite3  # imported only so we can catch sqlite3.Error in the startup check
import sys
import customtkinter as ctk
import tkinter as tk

from app.core import db, theme
from app.ui.dashboard_screen import DashboardScreen
from app.ui.settings_screen import SettingsScreen
# Phase 4: the Categories screen. Import order follows the sidebar order.
from app.ui.categories_screen import CategoriesScreen
# Phase 5: the Fixed Expenses screen.
from app.ui.fixed_expenses_screen import FixedExpensesScreen
# Phase 6: the Daily Expenses screen - the log/edit/delete flow the
# Dashboard's "Add Expense" button opens.
from app.ui.daily_expenses_screen import DailyExpensesScreen
# Phase 8: the Reports screen - charts over the data every other screen
# has already collected. Read-only, so it is added last in the sidebar
# order too.
from app.ui.reports_screen import ReportsScreen
from pathlib import Path

import ctypes
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wealthwise.app")
except Exception:
    pass
def _resource_path(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return str(base/ name)

# Window sizes in LOGICAL pixels. CustomTkinter multiplies these by the
# display's DPI factor (1.25 on a 125% display) before handing them to Tk.
DEFAULT_SIZE = (1120, 740)  # what we ask for when the screen allows it
MIN_SIZE = (960, 620)       # the layout starts to break below this


def _default_geometry(window) -> str:
    """Build a "WxH+X+Y" geometry string that fits inside the work area.

    WHY THIS EXISTS
      A fixed 1120x740 becomes 1400x925 physical pixels on a 125% display,
      and Windows may then drop the window at an offset (e.g. +137+166),
      which pushes the bottom of the sidebar - the theme switch and the
      database status - behind the taskbar. So we:
        1. shrink the preferred size to whatever the screen minus the
           taskbar allows (never below MIN_SIZE), and
        2. centre the window inside that free area.

    UNITS - the important detail
      CustomTkinter multiplies width/height by the DPI factor (1.25 on a
      125% display) but passes the +X+Y position through untouched.
      Therefore: sizes go in LOGICAL pixels, position goes in PHYSICAL
      pixels (the same units SystemParametersInfoW returns).
    """
    width, height = DEFAULT_SIZE  # logical pixels
    position = ""                 # becomes "+x+y" once we know where to put it

    try:
        # CustomTkinter's own DPI factor, so our maths matches the value
        # CTk applies to the width/height we return.
        scale = ctk.ScalingTracker.get_window_scaling(window)

        # SPI_GETWORKAREA (0x0030) fills a RECT with the screen area NOT
        # covered by the taskbar, in physical pixels.
        from ctypes import wintypes  # Windows-only module, hence the local import

        rect = wintypes.RECT()
        has_work_area = ctypes.windll.user32.SystemParametersInfoW(
            0x0030, 0, ctypes.byref(rect), 0
        )
        if has_work_area:
            avail_w = rect.right - rect.left   # physical px
            avail_h = rect.bottom - rect.top

            # (1) preferred logical -> physical, shrink to fit, back to logical
            fit_w = min(round(width * scale), avail_w)
            fit_h = min(round(height * scale), avail_h)
            width = max(MIN_SIZE[0], int(fit_w / scale))
            height = max(MIN_SIZE[1], int(fit_h / scale))

            # (2) centre the window in the free area (physical pixels!)
            x = max(0, (avail_w - round(width * scale)) // 2)
            y = max(0, (avail_h - round(height * scale)) // 2)
            position = f"+{x}+{y}"
    except Exception:
        pass  # not Windows, or the API failed: default size, Windows places it

    return f"{width}x{height}{position}"


class BudgetTrackerApp(ctk.CTk):
    """Main window: sidebar navigation + a content area that swaps screens."""

    SIDEBAR_WIDTH = 240  # pixels; fixed so the sidebar never jumps around

    def __init__(self):
        super().__init__()  # creates the Tk root window - fonts can only be made after this

        # --- global CustomTkinter defaults ---------------------------------
        # Our widgets always get explicit colours from theme.py, so these two
        # calls only style anything we forget to configure ourselves.
        ctk.set_default_color_theme("blue")
        ctk.set_appearance_mode(theme.appearance_mode())  # "Dark" on first launch

        # --- window basics --------------------------------------------------
        self.title("Wealthwise")
        try:
            self.iconbitmap(_resource_path("wealthwise_W.ico"))
        except Exception:
            pass
        self.geometry(_default_geometry(self))  # fits the screen incl. taskbar
        self.minsize(*MIN_SIZE)                 # the layout falls apart below this
        self.configure(fg_color=theme.color("bg"))

        # Which screen is currently visible (drives the sidebar highlight).
        self._current_screen = "dashboard"

        # --- layout: column 0 = sidebar (fixed), column 1 = content (fills) --
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        # Content frame holds the screens; only one is packed at a time.
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.color("bg"))
        self.content.grid(row=0, column=1, sticky="nsew")

        self.screens = {
            # The Dashboard's "+ Add Expense" button navigates to the Daily
            # Expenses screen: the callback is handed over HERE, so the
            # dashboard never needs to know how the shell switches pages.
            "dashboard": DashboardScreen(
                self.content,
                on_add_expense=lambda: self.show_screen("daily"),
            ),
            "settings": SettingsScreen(self.content),
            "categories": CategoriesScreen(self.content),
            "fixed": FixedExpensesScreen(self.content),
            "daily": DailyExpensesScreen(self.content),
            # Phase 8: reports. No callbacks to hand over - it only ever
            # reads the holders, so it needs nothing from the shell.
            "reports": ReportsScreen(self.content),
        }

        # Prove the SQLite connection works (Phase 1: connection only).
        ok, detail = self._probe_database()
        self._status_label.configure(text=("✓  " if ok else "✗  ") + detail)

        # Show the starting screen and paint its nav button as active.
        self.show_screen("dashboard")

    # ---------------------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------------------

    def _build_sidebar(self) -> None:
        """Left navigation column: brand, nav buttons, theme switch, status."""
        pad_lg = theme.spacing("lg")
        pad_md = theme.spacing("md")

        self.sidebar = ctk.CTkFrame(
            self,
            width=self.SIDEBAR_WIDTH,
            corner_radius=0,               # flush with the window edge
            fg_color=theme.color("sidebar_bg"),
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)  # keep the fixed width regardless of content

        # Single column. Row 8 is an EMPTY spacer row with weight 1, so it
        # absorbs all leftover height and pushes the appearance section and
        # the status label down to the bottom of the sidebar.
        #   rows: 0-1 brand | 2-7 nav buttons | 8 spacer | 9-11 bottom section
        # Phase 6 note: every row below the nav moved DOWN BY ONE each time
        # the nav gained a button (spacer 6->7, appearance 7->8, switch
        # 8->9, status 9->10, bottom padding 10->11 - that was the fifth
        # button, on row 6).
        # Phase 8: moved DOWN BY ONE again (spacer 7->8, appearance 8->9,
        # switch 9->10, status 10->11, bottom padding 11->12) because the
        # nav gained a SIXTH button, which occupies row 7.
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)

        # --- brand --------------------------------------------------------
        self._brand_label = ctk.CTkLabel(
            self.sidebar,
            text="Wealthwise",
            font=theme.font("brand"),
            anchor="w",
        )
        self._brand_label.grid(
            row=0, column=0, sticky="ew",
            padx=pad_lg, pady=(pad_lg, 0),
        )

        self._brand_caption = ctk.CTkLabel(
            self.sidebar,
            text="Master Your Money",
            font=theme.font("caption"),
            anchor="w",
        )
        self._brand_caption.grid(
            row=1, column=0, sticky="ew",
            padx=pad_lg, pady=(0, theme.spacing("xl")),
        )

        # --- navigation buttons --------------------------------------------
        # Each button remembers its screen key in a dict for later re-theming.
        self._nav_buttons: dict = {}
        # Phase 8: Reports is appended last - it summarises what the
        # other screens recorded, so it belongs at the end of the flow.
        nav_items = [("dashboard", "Dashboard"), ("settings", "Settings"),
                     ("categories", "Categories"), ("fixed", "Fixed Expenses"),
                     ("daily", "Daily Expenses"), ("reports", "Reports")]

        for row, (key, label) in enumerate(nav_items, start=2):
            button = ctk.CTkButton(
                self.sidebar,
                # CTkButton has no internal text padding, so we indent with
                # two leading spaces to align text under the brand label.
                text=f"  {label}",
                anchor="w",                 # text sticks to the left edge
                height=42,
                corner_radius=theme.radius("sm"),
                font=theme.font("button"),
                fg_color="transparent",     # inactive = no background
                hover_color=theme.color("surface"),
                text_color=theme.color("text_secondary"),
                command=lambda k=key: self.show_screen(k),
            )
            button.grid(
                row=row, column=0, sticky="ew",
                padx=pad_md, pady=(0, theme.spacing("xs")),
            )
            self._nav_buttons[key] = button

        # --- appearance section (bottom half of the sidebar) ---------------
        self._appearance_caption = ctk.CTkLabel(
            self.sidebar,
            text="APPEARANCE",
            font=theme.font("caption"),
            anchor="w",
        )
        # Phase 8 note: row 9 (instead of 8) because the nav gained a
        # sixth button, which now occupies row 7 - see the row map above.
        self._appearance_caption.grid(
            row=9, column=0, sticky="ew",
            padx=pad_lg, pady=(0, theme.spacing("sm")),
        )

        self.theme_switch = ctk.CTkSwitch(
            self.sidebar,
            text="Dark mode",
            font=theme.font("body"),
            command=self._on_theme_toggle,
            fg_color=theme.color("switch_track_off"),   # track while OFF
            progress_color=theme.color("switch_track"), # track while ON
            button_color=theme.color("switch_button"),
            button_hover_color=theme.color("switch_button_hover"),
            text_color=theme.color("text_secondary"),
        )
        self.theme_switch.grid(
            row=10, column=0, sticky="w",
            padx=pad_lg, pady=(0, pad_lg),
        )
        # The app starts in dark mode, so the switch starts in the "on" state.
        self.theme_switch.select()

        # --- database status (proof that db.py works) ----------------------
        self._status_label = ctk.CTkLabel(
            self.sidebar,
            text="Checking database...",
            font=theme.font("caption"),
            anchor="w",
            justify="left",
            wraplength=self.SIDEBAR_WIDTH - 2 * pad_lg,  # don't overflow the sidebar
        )
        self._status_label.grid(
            row=11, column=0, sticky="ew",
            padx=pad_lg, pady=(0, pad_lg),
        )

        # Bottom padding: a little breathing room under the status label.
        self.sidebar.grid_rowconfigure(12, weight=0, minsize=theme.spacing("sm"))

    # ---------------------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------------------

    def show_screen(self, key: str) -> None:
        """Make `key` the visible screen and update the sidebar highlight.

        Screens are created once in __init__; here we only pack the wanted
        one and pack_forget() the others. pack_forget() just unmaps a
        widget - it is NOT destroyed, so scroll position and state would
        survive a switch (useful once real content exists).
        """
        if key not in self.screens:
            raise KeyError(f"Unknown screen {key!r}. Available: {sorted(self.screens)}")

        for name, screen in self.screens.items():
            if name == key:
                screen.pack(fill="both", expand=True)
            else:
                screen.pack_forget()

        self._current_screen = key
        self._update_nav_highlight()

    def _update_nav_highlight(self) -> None:
        """Colour the active nav button differently from the inactive ones."""
        for key, button in self._nav_buttons.items():
            active = key == self._current_screen
            button.configure(
                fg_color=theme.color("accent_soft") if active else "transparent",
                text_color=theme.color("accent_text") if active else theme.color("text_secondary"),
                hover_color=theme.color("accent_soft") if active else theme.color("surface"),
            )

    # ---------------------------------------------------------------------
    # Dark / light toggle
    # ---------------------------------------------------------------------

    def _on_theme_toggle(self) -> None:
        """Called every time the sidebar switch is clicked.

        CustomTkinter flips the switch state BEFORE calling this callback,
        so switch.get() already returns the new value (1 = on = dark).
        """
        new_mode = "dark" if self.theme_switch.get() == 1 else "light"
        theme.set_mode(new_mode)                       # 1. update the palette source
        ctk.set_appearance_mode(theme.appearance_mode())  # 2. update CustomTkinter's defaults
        self._refresh_shell_theme()                    # 3. repaint everything we coloured

    def _refresh_shell_theme(self) -> None:
        """Re-apply the active palette to the window, sidebar and screens."""
        self.configure(fg_color=theme.color("bg"))

        # Sidebar + its widgets
        self.sidebar.configure(fg_color=theme.color("sidebar_bg"))
        self._brand_label.configure(text_color=theme.color("text"))
        self._brand_caption.configure(text_color=theme.color("text_secondary"))
        self._appearance_caption.configure(text_color=theme.color("text_secondary"))
        self._status_label.configure(text_color=theme.color("text_secondary"))
        self.theme_switch.configure(
            fg_color=theme.color("switch_track_off"),
            progress_color=theme.color("switch_track"),
            button_color=theme.color("switch_button"),
            button_hover_color=theme.color("switch_button_hover"),
            text_color=theme.color("text_secondary"),
        )

        # Content area + every screen
        self.content.configure(fg_color=theme.color("bg"))
        self._update_nav_highlight()
        for screen in self.screens.values():
            screen.refresh_theme()

    # ---------------------------------------------------------------------
    # Database check (Phase 1: connection only, no tables)
    # ---------------------------------------------------------------------

    @staticmethod
    def _probe_database():
        """Open data/budget.db, run a tiny query, close it.

        Returns (ok: bool, detail: str) so the sidebar can show the result.
        """
        try:
            connection = db.get_connection()
            version = connection.execute("SELECT sqlite_version()").fetchone()[0]
            return True, f"SQLite {version} · data/budget.db"
        except sqlite3.Error as exc:
            return False, f"Database error: {exc}"
        finally:
            if "connection" in locals():  # close it on success AND on failure
                connection.close()


def main() -> None:
    """Create the window and start the Tk event loop."""
    app = BudgetTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
