"""
theme.py - the single source of truth for how Budget Tracker looks.

WHY THIS FILE EXISTS
  Nothing else in the app is allowed to hardcode a colour, font size,
  spacing value or corner radius. Screens ask this module instead:

      from app.core import theme
      label = ctk.CTkLabel(self, text="Hi", text_color=theme.color("text"))

  That way, restyling the whole app - or adding a new colour - is a
  one-line change in one file.

HOW MODES WORK
  There are two palettes with EXACTLY the same keys: LIGHT and DARK.
  The module remembers which one is active (_MODE), and theme.color()
  always reads from the active palette. When the user flips the switch
  in the sidebar, main.py updates _MODE and asks every screen to call
  its refresh_theme() method, which re-reads the colours from here.
"""

import customtkinter as ctk

# ---------------------------------------------------------------------------
# 1. PALETTES - one dict per appearance mode.
#    Keep the keys identical in both dicts! This module checks that at
#    import time (see _validate_palettes at the bottom), so a typo like
#    adding "text_secondary" only to LIGHT fails fast instead of looking
#    broken later in dark mode.
# ---------------------------------------------------------------------------

LIGHT = {
    # --- surfaces (neutral greys) ---
    "bg": "#F4F5F8",                 # window background / content area
    "sidebar_bg": "#FFFFFF",         # left sidebar
    "card_bg": "#FFFFFF",            # cards and panels
    "surface": "#ECEEF3",            # recessed areas (hover states, empty panels)
    "border": "#E2E5EB",             # 1px outlines
    # The chart grid. A border is right for ONE outline, but the same
    # colour repeated eight times across a plot reads as hard rules:
    # #E2E5EB on this white card is 1.26:1, which is why the Reports
    # charts looked over-gridded in light mode. #EDEFF4 is 1.15:1 -
    # a hair fainter than the #EEEEEE (1.16:1) most charts use - so the
    # grid reads as a guide you can still count against, not as a cage.
    "grid": "#EDEFF4",

    # --- the ONE brand accent colour (indigo) ---
    "accent": "#4F46E5",             # filled buttons, progress, highlights
    "accent_hover": "#4338CA",       # accent, slightly darker, for hovers
    "accent_soft": "#E9EBFF",        # tinted accent background (selected nav item)
    "accent_text": "#4F46E5",        # accent-coloured TEXT (readable on soft bg)
    "text_on_accent": "#FFFFFF",     # text drawn on top of the accent
    "text_on_accent_secondary": "#C5C9FF",  # muted captions ON the accent card

    # --- semantic accents (the only colours besides the brand accent) ---
    # Added in Phase 2 for the dashboard's budget categories. Each value
    # is chosen to work as BOTH a fill (progress bars) and as readable
    # text on card_bg, so one key covers both uses.
    "info": "#2563EB",               # Needs
    "warning": "#B45309",            # Wants
    "success": "#15803D",            # Savings / positive amounts
    "danger": "#DC2626",             # red - validation errors, critical states
    "danger_hover": "#B91C1C",       # danger, hovered/pressed - the same deeper-on-
                                     # hover step the accent / accent_hover pair has
    # Text drawn ON a danger-filled button (Phase 4's delete confirmation).
    # White is the readable choice on this deep red - the mirror image of
    # text_on_accent, which pairs with "accent" the same way.
    "text_on_danger": "#FFFFFF",

    # --- status colours FOR THE ACCENT BANNER (salary card) ---
    # The colour-coded remaining balance on the purple salary banner.
    # The values differ per mode ON PURPOSE (design decision):
    #   LIGHT: mint green + bright yellow are banner-tuned - the normal
    #          status greens/ambers are nearly invisible on #4F46E5, so
    #          these were brightened until legible (measured 4.90:1 and
    #          4.77:1; white itself only reaches 6.29:1 on the banner).
    #          The red is #F87171 - the SHADE dark mode used to use. It
    #          measures 2.27:1 here, versus only 1.30:1 for #DC2626, so
    #          the swap makes the light-mode red noticeably easier to
    #          read (the two reds were exchanged between the modes).
    "balance_good": "#A7F3D0",       # mint - banner-tuned green (4.90:1)
    "balance_warn": "#FDE047",       # bright yellow - banner-tuned (4.77:1)
    "balance_bad": "#F87171",        # lightened red - was dark mode's (2.27:1)

    # --- text ---
    "text": "#14161C",               # primary text
    "text_secondary": "#616875",     # subtitles, captions, inactive nav items

    # --- switch (dark/light toggle in the sidebar) ---
    "switch_track": "#4F46E5",       # track colour while the switch is ON
    "switch_track_off": "#C7CCD6",   # track colour while the switch is OFF
    "switch_button": "#FFFFFF",
    "switch_button_hover": "#F0F1F5",
}

DARK = {
    # --- surfaces (neutral greys) ---
    "bg": "#121317",
    "sidebar_bg": "#17191E",
    "card_bg": "#1C1F26",
    "surface": "#23262E",
    "border": "#2A2E37",
    # The chart grid - deliberately the SAME value as this palette's
    # border. #2A2E37 on this card is 1.21:1, which already reads as a
    # faint guide, so dark mode needed no change; only light mode's
    # border was too heavy for a repeated line. The key exists in both
    # palettes so the reports screen can ask for "grid" once and let
    # each mode answer with the value that is right for it.
    "grid": "#2A2E37",

    # --- the ONE brand accent colour (indigo, brightened for dark bg) ---
    "accent": "#6366F1",
    "accent_hover": "#7579F5",
    "accent_soft": "#262A4A",
    "accent_text": "#8B93F9",        # brighter than "accent" so text stays readable
    "text_on_accent": "#FFFFFF",
    "text_on_accent_secondary": "#DFE1FF",  # muted captions ON the accent card

    # --- semantic accents (same keys as LIGHT - the guard at the bottom
    #     of this file fails the app if they ever drift apart) ---
    "info": "#60A5FA",               # Needs
    "warning": "#FBBF24",            # Wants
    "success": "#4ADE80",            # Savings / positive amounts
    "danger": "#F87171",             # red - validation errors, critical states
    "danger_hover": "#EF4444",       # deeper, more saturated on hover (still clears
                                     # 4.5:1 with this palette's dark ink)
    # Text drawn ON a danger-filled button. This palette's danger is a
    # LIGHT coral, so white on it only reaches ~2.4:1 - dark ink reads
    # far better (6.6:1), which is why the value flips between modes.
    "text_on_danger": "#14161C",

    # --- status colours FOR THE ACCENT BANNER (salary card) ---
    # Dark mode keeps the ORIGINAL green and amber (the same values as
    # success / warning in this palette). The red, however, was SWAPPED
    # with light mode: dark now wears #DC2626, the deeper red light mode
    # used to use.
    # Measured against the dark banner #6366F1 (white only reaches
    # 4.47:1 there): 2.56 / 2.68 / 1.08:1.
    "balance_good": "#4ADE80",       # = success green, as it was before
    "balance_warn": "#FBBF24",       # = warning amber, as it was before
    "balance_bad": "#DC2626",        # deep red - was light mode's (1.08:1)

    # --- text ---
    "text": "#E9EBEF",
    "text_secondary": "#9BA3B2",

    # --- switch ---
    "switch_track": "#6366F1",
    "switch_track_off": "#3A3F4A",
    "switch_button": "#FFFFFF",
    "switch_button_hover": "#E8E9FF",
}

# ---------------------------------------------------------------------------
# 2. SPACING, RADII AND FONTS
#    Named values instead of magic numbers, so the app feels consistent
#    (everything is a multiple of the same few steps).
# ---------------------------------------------------------------------------

SPACING = {
    "xs": 6,     # gap between a nav button and the next one
    "sm": 10,    # inner padding of small elements
    "md": 16,    # standard padding
    "lg": 24,    # sidebar / screen side padding
    "xl": 36,    # breathing room at the top of a screen
}

RADIUS = {
    "sm": 8,     # buttons, small chips
    "md": 12,    # inputs, mid-size panels
    "lg": 16,    # big cards
}

# One font family for the whole app (Segoe UI ships with Windows, so it
# looks native now and inside the packaged .exe later).
FONT_FAMILY = "Segoe UI"

# Font "specs" are plain dicts on purpose: a CTkFont can only be created
# AFTER the first window exists (Tk needs a root window first), so we
# build and cache the real CTkFont objects lazily in font() below.
FONT_SPECS = {
    "brand":     {"size": 20, "weight": "bold"},    # "Budget Tracker" in the sidebar
    "title":     {"size": 26, "weight": "bold"},    # screen titles (Dashboard, Settings)
    "subtitle":  {"size": 14, "weight": "normal"},  # one-line description under a title
    "section":   {"size": 16, "weight": "bold"},    # headings inside cards
    "body":      {"size": 14, "weight": "normal"},  # normal UI text
    "button":    {"size": 14, "weight": "normal"},  # sidebar navigation buttons
    "caption":   {"size": 12, "weight": "normal"},  # small status/hint text

    # Dashboard (Phase 2) - a size ladder for money figures:
    #   32 (display) -> 20 (amount) -> 16 (section) -> 14 (value) -> 12 (caption)
    "display":   {"size": 32, "weight": "bold"},    # big figures on the salary card
    "amount":    {"size": 20, "weight": "bold"},    # allocated amount in a budget card
    "value":     {"size": 14, "weight": "bold"},    # spent / remaining / percent figures
}

# ---------------------------------------------------------------------------
# 3. MODE STATE
# ---------------------------------------------------------------------------

_MODE = "dark"  # the app starts in dark mode (the switch in the sidebar starts "on")


def set_mode(mode: str) -> None:
    """Remember which palette is active. Call this when the toggle flips."""
    global _MODE
    if mode not in ("light", "dark"):
        raise ValueError(f"Unknown appearance mode {mode!r} - use 'light' or 'dark'.")
    _MODE = mode


def get_mode() -> str:
    """Return the active mode: 'light' or 'dark'."""
    return _MODE


def appearance_mode() -> str:
    """Return the mode in the spelling CustomTkinter expects: 'Light' / 'Dark'."""
    return "Light" if _MODE == "light" else "Dark"


def palette() -> dict:
    """Return the whole active palette (rarely needed - prefer color())."""
    return LIGHT if _MODE == "light" else DARK


# ---------------------------------------------------------------------------
# 4. ACCESSORS - what the rest of the app uses
# ---------------------------------------------------------------------------

def color(key: str) -> str:
    """Return a colour (hex string) from the ACTIVE palette."""
    active = palette()
    if key not in active:
        raise KeyError(
            f"Unknown theme colour {key!r}. Available keys: {', '.join(sorted(active))}"
        )
    return active[key]


def spacing(key: str) -> int:
    """Return a spacing step in pixels ('xs' | 'sm' | 'md' | 'lg' | 'xl')."""
    return SPACING[key]


def radius(key: str) -> int:
    """Return a corner radius in pixels ('sm' | 'md' | 'lg')."""
    return RADIUS[key]


_font_cache: dict = {}


def font(key: str) -> ctk.CTkFont:
    """Return a cached CTkFont for a named style (see FONT_SPECS).

    Fonts are cached because every Tk font object registers itself with
    the Tk interpreter - creating new ones on every theme refresh would
    leak them. The first call happens while the window is already open,
    which is what Tk requires.
    """
    if key not in FONT_SPECS:
        raise KeyError(
            f"Unknown font style {key!r}. Available: {', '.join(sorted(FONT_SPECS))}"
        )
    if key not in _font_cache:
        spec = FONT_SPECS[key]
        _font_cache[key] = ctk.CTkFont(
            family=FONT_FAMILY, size=spec["size"], weight=spec["weight"]
        )
    return _font_cache[key]


# ---------------------------------------------------------------------------
# 5. GUARD - run once at import time
# ---------------------------------------------------------------------------

def _validate_palettes() -> None:
    """Fail loudly if LIGHT and DARK ever drift apart (missing keys)."""
    missing_in_light = set(DARK) - set(LIGHT)
    missing_in_dark = set(LIGHT) - set(DARK)
    if missing_in_light or missing_in_dark:
        raise RuntimeError(
            "Theme palettes out of sync. "
            f"Missing in LIGHT: {sorted(missing_in_light)} | "
            f"Missing in DARK: {sorted(missing_in_dark)}"
        )


_validate_palettes()
