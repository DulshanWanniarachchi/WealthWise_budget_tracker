"""
reports_screen.py - the Reports screen (Phase 8).

WHAT THIS SCREEN DOES
  Four charts plus four text statistics, all built from what the user
  has ALREADY logged:

    split        donut  - spending split across Needs / Wants / Savings
    categories   bars   - spending by category (pick a budget, or "All")
    comparison   bars   - allocated vs planned vs spent, per budget
    compare      bars   - Phase 8.4: two finished cycles side by side,
                          three budget bars each, with each cycle's
                          spent/saved figures above its group
    statistics          - top category, spent this salary cycle, total
                          spent, remaining - plus, since Phase 8.3, the
                          cycle's exact date range under its month name
    history              - Phase 8.3: finished salary cycles, newest
                          first, each with what was spent and what was
                          saved (the third tab, plain widgets - no chart)

READ-ONLY
  This screen writes nothing. It calls app/services/reports.py, which
  only ever calls the four holders' READERS, so opening Reports cannot
  change a single rupee of the user's data.

WHERE THE NUMBERS COME FROM
  Every figure is aggregated in app/services/reports.py - this file
  contains presentation and NOTHING else. If a number looks wrong, the
  bug is in reports.py; if it looks ugly, the bug is in here. That
  split is the same one the rest of the app keeps.

THEMATING - the tricky part of this phase
  matplotlib ships with its own light, grey-on-white style, so every
  element is painted by hand from app/core/theme.py in two places:

    1. _apply_matplotlib_palette() pushes the ACTIVE palette into
       matplotlib's rcParams (figure and axes background, frame, tick
       and label colours, grid, legend). It runs at the top of every
       single draw, so a figure can never be built with matplotlib's
       own defaults left in it.
    2. The artists whose colour varies with the DATA - the donut
       wedges, the bars, the over/under notes - are given
       theme.color(...) explicitly where they are created.

  A theme flip therefore needs no special case: main.py calls
  refresh_theme(), which recolours the CustomTkinter widgets AND
  redraws all three figures, and step 1 above repaints them.

  Budget identity: Needs/Wants/Savings always take their colour from
  budget_settings.BUDGET_ACCENTS (info / warning / success) - the same
  three keys the Dashboard's progress bars use - so a slice or a bar
  means the same thing everywhere in the app.

LAYOUT (why this screen is split across tabs)
  Three charts stacked in one column never had enough HEIGHT: at
  960x620 each one squeezed into a band the donut could not hold its
  own centre label in. The screen is therefore laid out in two fixed
  bands:

    always visible   title, subtitle, statistics, the category filter
    behind the tabs  the charts, one group per tab

    row 0 title | 1 subtitle | 2 statistics | 3 filter | 4 tabview

  The tabview owns row 4 (weight=1) so it - and only it - absorbs
  whatever height the window has left. Inside it:

    "Spending"       donut (left)  +  spending by category (right)
    "Plan vs Actual" allocated vs spent, at full width
    "History"        finished salary cycles in a scrollable list
                     (Phase 8.3) - a list, not a chart, so it needs
                     none of the matplotlib machinery

  Each chart tab holds a single row of cards, so the charts now get the
  whole band instead of a third of it - which is also what gives the
  donut enough room for "Rs. 31,000 / spent" to sit inside the hole
  with margin to spare. Nothing scrolls, because nothing overflows: at
  most two cards share one row. The History tab is the exception and
  scrolls on purpose - one record per finished cycle accumulates
  forever.

  The statistics and the filter deliberately stay ABOVE the tabs.
  They summarise everything, not one tab's chart, and keeping them
  out of the way of the tab swap means the screen's frame never
  jumps when the user changes tab. The empty panel sits in row 4
  too, so swapping to it cannot leave a dead weighted row behind.

RESIZING
  The figures are rebuilt at each chart box's CURRENT pixel size, and a
  <Configure> binding on that box schedules a redraw 120 ms after the
  last size change (so dragging the window edge does not redraw on
  every intermediate frame).

CONTRACT WITH main.py (identical to every other screen)
  * every colour / font / spacing / radius comes from app.core.theme
  * refresh_theme() re-applies the palette to EVERY widget created
    here, so the sidebar's dark/light switch repaints this screen live
"""

from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

import tkinter as tk

import customtkinter as ctk

from app.core import theme
from app.services import (
    budget_settings,
    category_settings,
    daily_expenses,
    fixed_expenses,
    reports,
)

# Budget key -> the theme colour that budget has everywhere else.
BUDGET_ACCENTS = budget_settings.BUDGET_ACCENTS
BUDGET_LABELS = budget_settings.BUDGET_LABELS

# --- the category picker -------------------------------------------------
PICKER_ALL = "All"
PICKER_VALUES = [PICKER_ALL] + [BUDGET_LABELS[key] for key in reports.BUDGET_KEYS]
# Display value -> the key reports.spending_by_category() expects.
# "All" maps to None, which that function reads as "every budget".
PICKER_KEYS = {PICKER_ALL: None}
PICKER_KEYS.update({BUDGET_LABELS[key]: key for key in reports.BUDGET_KEYS})

# --- the tabs -------------------------------------------------------------
# The tab TITLES are constants because _apply_state() and the tests
# address them by name; _build_tabs() is the only place that creates them.
TAB_SPENDING = "Spending"          # donut + spending by category
TAB_PLAN = "Plan vs Actual"        # allocated vs spent
TAB_HISTORY = "History"            # finished salary cycles (Phase 8.3)
TAB_COMPARE = "Compare"            # two finished cycles, side by side
TABS = (TAB_SPENDING, TAB_PLAN, TAB_HISTORY, TAB_COMPARE)

# --- chart geometry ------------------------------------------------------
# Pixel sizes are layout, not palette - the same precedent as main.py's
# sidebar width and the Settings screen's 200/70/140 input widths.
CHART_DPI = 96      # fixed so a figure built before mapping still fits
MIN_CHART_W = 240   # never draw into a box that has not been laid out
MIN_CHART_H = 140
REDRAW_DELAY_MS = 120   # debounce while the user drags the window edge

# The donut's ring, as a fraction of its radius. The other 1 - 0.30 =
# 0.70 of the radius is the hole, and that hole is where "Rs. 31,000 /
# spent" has to live. Phase 8 used 0.42, which on a full-size window
# still left a hole a hair NARROWER than "Rs. 63,200" - the label ran
# into the colour instead of sitting inside it.
DONUT_RING = 0.30

# Money on an axis: 60000 -> "60,000". The COLOUR of these labels comes
# from rcParams (set from theme.py); only the formatting lives here.
MONEY = FuncFormatter(lambda value, _position: f"{int(value):,}")

# The History tab's salary footnote wraps at this width so it reads as a
# couple of sensible lines instead of one run the full (very wide) panel.
HISTORY_NOTE_WRAP = 560   # layout, like the chart sizes above - not palette

# The Compare tab's salary line wraps at the same width, for the same
# reason: it is a sentence (with an optional honest footnote under it),
# not a figure that should run edge to edge.
COMPARE_NOTE_WRAP = 560   # layout, like the chart sizes above - not palette


def _pt(pixels: int) -> float:
    """Turn a theme font size in PIXELS into matplotlib POINTS.

    Tk sizes text in pixels, matplotlib in points (1/72 of an inch), so
    on a 96-dpi canvas a 12-pixel caption is 9 points. Without this the
    charts' text would be a third taller than every label around them
    and the screen would look like two different apps stitched together.
    """
    return pixels * 72.0 / CHART_DPI


def _font(key: str) -> float:
    """matplotlib point size for one of theme.py's named font styles."""
    return _pt(theme.FONT_SPECS[key]["size"])


def _apply_matplotlib_palette() -> None:
    """Paint matplotlib's defaults with the ACTIVE palette.

    Called at the start of every draw. Each key below is a part of a
    chart that matplotlib would otherwise colour itself, and every value
    is read from theme.py right now - which is exactly why flipping the
    dark/light switch repaints the charts along with the widgets: the
    next figure built after the flip picks up the new palette here.
    """
    rcParams.update({
        # The box the chart is drawn on.
        "figure.facecolor": theme.color("card_bg"),
        "figure.edgecolor": theme.color("border"),
        "savefig.facecolor": theme.color("card_bg"),
        "axes.facecolor": theme.color("card_bg"),
        # The frame around the plotting area, and its labels.
        "axes.edgecolor": theme.color("border"),
        "axes.labelcolor": theme.color("text_secondary"),
        "text.color": theme.color("text"),
        # Numbers along both axes.
        "xtick.color": theme.color("text_secondary"),
        "ytick.color": theme.color("text_secondary"),
        # The grid behind the bars. NOT "border": a border is right for
        # one outline but too heavy when it is repeated across a plot,
        # so this has its own key (one value per palette, in theme.py).
        "grid.color": theme.color("grid"),
        # The chart's own caption box.
        "legend.facecolor": theme.color("card_bg"),
        "legend.edgecolor": theme.color("border"),
        "legend.labelcolor": theme.color("text"),
        # Type: one family for the whole app, sized off theme's caption.
        "font.family": theme.FONT_FAMILY,
        "font.size": _font("caption"),
    })


def _budget_colour(key: str) -> str:
    """The theme colour for one budget - the app's info/warning/success.

    Imported through BUDGET_ACCENTS rather than a local dict so Needs,
    Wants and Savings can never drift out of sync with the Dashboard's
    progress bars or the Categories screen's headings.
    """
    return theme.color(BUDGET_ACCENTS[key])


class ReportsScreen(ctk.CTkFrame):
    """Read-only charts and statistics over the existing spending data."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.color("bg"), corner_radius=0, **kwargs)

        # The category picker's current choice (None = "All").
        self._budget = None
        # One read of the holders, shared by every text widget and every
        # chart, so the screen can never show two different moments.
        self._data = reports.report(self._budget)

        # Phase 8.4 (Compare tab): the two cycles the dropdowns show, as
        # cycle keys - None until the first _apply_compare() defaults
        # them to the two newest finished cycles - plus the cycle keys
        # each month NAME maps to, and the compare_cycles() records the
        # chart is drawn from.
        self._compare_keys = None         # (key_a, key_b) once chosen
        self._label_to_key: dict = {}
        self._compare_data: list = []

        # chart key -> the frame its canvas lives in, for size measuring
        self._boxes: dict = {}
        # chart key -> (Figure, FigureCanvasTkAgg), kept so a redraw
        # reuses the same canvas widget instead of stacking new ones.
        self._figures: dict = {}
        self._canvases: dict = {}
        # chart key -> the size it was last drawn at, so a <Configure>
        # that changes nothing does not schedule a pointless redraw.
        self._drawn_at: dict = {}
        # chart key -> the pending after() id from the resize debounce
        self._resize_jobs: dict = {}

        self._build()
        self._reload()          # read the holders into the widgets
        self.refresh_theme()    # colour everything, then draw the charts

        # Live updates. Screens are built ONCE and shown/hidden by
        # main.py, so nothing would refresh these charts when an expense
        # is logged elsewhere unless we listen here - the same reason the
        # Dashboard subscribes.
        budget_settings.subscribe(self._on_data_changed)
        category_settings.subscribe(self._on_data_changed)
        fixed_expenses.subscribe(self._on_data_changed)
        daily_expenses.subscribe(self._on_data_changed)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Create every widget once. Colours are applied in refresh_theme()."""
        pad = theme.spacing("lg")

        # One column fills the width; row 4 (the tab view) takes the height.
        #   rows: 0 title | 1 subtitle | 2 statistics | 3 filter | 4 charts
        # Row 4 is the ONLY weighted row, and it holds either the tab view
        # or the empty panel - never both at once. That matters: a second
        # weighted row left standing while the first is grid_remove()d
        # would swallow every leftover pixel and shove the panel below it
        # off the bottom of the window.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # -- title / subtitle ---------------------------------------------
        self._title = ctk.CTkLabel(
            self, text="Reports",
            font=theme.font("title"), anchor="w",
        )
        self._title.grid(
            row=0, column=0, sticky="ew",
            padx=pad, pady=(theme.spacing("xl"), theme.spacing("xs")),
        )

        self._subtitle = ctk.CTkLabel(
            self,
            text="Where your money actually went - read straight from your log.",
            font=theme.font("subtitle"), anchor="w",
        )
        self._subtitle.grid(
            row=1, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("md")),
        )

        # -- the four statistics, straight onto the screen ----------------
        # Deliberately NOT inside a scrollable frame: a tile's height is
        # then decided by its own three lines of text and nothing else,
        # so no other widget can shorten the row and clip it.
        self._build_statistics()
        # -- the category chart's budget picker ----------------------------
        # The caption has its own line and the segmented control takes the
        # whole row under it, so the four values run edge to edge with the
        # cards below instead of bunching against the right-hand side.
        picker_row = ctk.CTkFrame(self, fg_color="transparent")
        # sm, not md, underneath: the filter is a CONTROL for what sits
        # directly below it, so it hugs the tab panel. The statistics
        # above keep the full md gap because they are a summary, not a
        # control - the rhythm is md between bands, sm into the panel.
        picker_row.grid(
            row=3, column=0, sticky="ew",
            padx=pad, pady=(0, theme.spacing("sm")),
        )
        picker_row.grid_columnconfigure(0, weight=1)

        self._picker_caption = ctk.CTkLabel(
            picker_row, text="SHOW CATEGORIES FOR",
            font=theme.font("caption"), anchor="w",
        )
        self._picker_caption.grid(
            row=0, column=0, sticky="ew",
            pady=(0, theme.spacing("xs")),
        )

        self._picker = ctk.CTkSegmentedButton(
            picker_row,
            values=PICKER_VALUES,
            # Leave dynamic_resizing ON: with it off CustomTkinter calls
            # grid_propagate(False) and the widget stays at its 140 px
            # default width, which clips "Needs"/"Wants"/"Savings" down to
            # "leed"/"Van"/"aving". The value list never changes, so
            # sizing to content cannot make the row jump either way.
            height=32,
            corner_radius=theme.radius("sm"),
            font=theme.font("caption"),
            command=self._on_picker_changed,
        )
        self._picker.set(PICKER_ALL)
        # sticky="ew" in a weighted column stretches the control across the
        # whole content width. Its internal columns all carry weight=1, so
        # every value grows by exactly the same amount - the four stay
        # evenly spaced rather than the selected one hogging the space.
        self._picker.grid(row=1, column=0, sticky="ew")

        # -- the chart tabs, the compare body, the history tab + empty ----
        # _build_compare() must run BEFORE _build_charts(): all four
        # chart cards are made by the one card() helper inside
        # _build_charts(), and the Compare card is gridded into the body
        # frame that _build_compare() creates.
        self._build_tabs()
        self._build_compare()
        self._build_charts()
        self._build_history()
        self._build_empty_state()

    def _build_statistics(self) -> None:
        """The four text figures across the top (the 'Statistics' idea).

        Vertical padding is deliberately roomy: the caption sits
        theme.spacing("md") below the card's top edge and the detail line
        theme.spacing("md") above its bottom edge, with theme.spacing("sm")
        separating the headline from the caption. That is the "md / sm / md"
        rhythm the chart cards already use, so the tiles read as the same
        kind of object as the charts - and no line can reach the border.
        """
        gap = theme.spacing("sm")

        # caption -> what to shout, value -> the headline number, detail
        # -> the smaller line under it. The tuple is the ORDER they read
        # in, left to right.
        self._stat_specs = (
            ("TOP CATEGORY", "highest"),
            ("SPENT THIS MONTH", "month"),
            ("TOTAL SPENT", "total"),
            ("TOTAL REMAINING", "remaining"),
        )
        self._stats: list = []

        # The strip needs FOUR columns of its own. Gridding the tiles at
        # columns 1-3 of the SCREEN would leave those columns unweighted
        # (the screen only weights column 0), so they would each be sized
        # by whatever a tile asked for - and column 0, which carries the
        # title, the subtitle, the filter and the entire tab view, would
        # be squeezed down to whatever was left over. A transparent strip
        # keeps the screen a single column and gives the four tiles equal
        # shares of the full content width.
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.grid(
            row=2, column=0, sticky="ew",
            padx=theme.spacing("lg"), pady=(0, theme.spacing("md")),
        )
        for column in range(4):
            strip.grid_columnconfigure(column, weight=1)
        # Row 0 carries NO weight on purpose: the strip's height is then
        # exactly the tallest tile's requested height, and because the
        # strip itself is gridded "ew" (never "nsew") nothing above or
        # below it can press down on the row. The tiles cannot clip.

        for column, (caption, _key) in enumerate(self._stat_specs):
            card = ctk.CTkFrame(
                strip, corner_radius=theme.radius("md"), border_width=1,
            )
            # Every tile stretches to the tallest one, so a long category
            # name that wraps cannot leave a ragged row. The strip sits one
            # gap above the filter so the two bands never touch.
            card.grid(
                row=0, column=column, sticky="nsew",
                padx=(0, gap) if column < 3 else 0,
            )
            # One column, one row each: the card's height is simply the
            # sum of its three labels plus the padding above and below,
            # which is exactly the height that gets laid out.
            card.grid_columnconfigure(0, weight=1)

            caption_label = ctk.CTkLabel(
                card, text=caption,
                font=theme.font("caption"), anchor="w",
            )
            caption_label.grid(
                row=0, column=0, sticky="ew",
                padx=theme.spacing("sm"), pady=(theme.spacing("md"), 0),
            )

            value = ctk.CTkLabel(
                card, text="",
                font=theme.font("value"), anchor="w", justify="left",
                # Long category names wrap instead of overflowing the tile.
                wraplength=180,
            )
            value.grid(
                row=1, column=0, sticky="ew",
                padx=theme.spacing("sm"), pady=(theme.spacing("sm"), 0),
            )

            detail = ctk.CTkLabel(
                card, text="",
                font=theme.font("caption"), anchor="w", justify="left",
                wraplength=180,
            )
            detail.grid(
                row=2, column=0, sticky="ew",
                padx=theme.spacing("sm"), pady=(0, theme.spacing("md")),
            )

            self._stats.append({
                "key": _key, "card": card, "caption": caption_label,
                "value": value, "detail": detail,
            })

    def _build_tabs(self) -> None:
        """Create the CTkTabview and every panel inside it.

        CTkTabview grids each tab's frame at row 3 with weight=1, so the
        frame fills whatever space the tab has - the chart cards inside
        simply weight their own columns/rows on top of that. All four
        tab titles come from TABS, so adding one here is all the wiring
        a new tab needs.
        """
        self._tabs = ctk.CTkTabview(
            self,
            # The panel behind the charts is the screen's own background,
            # so the chart cards keep the exact relationship they had when
            # everything sat on one scrollable frame (card_bg floating on
            # bg) - only the tab bar is new.
            fg_color=theme.color("bg"),
            border_width=1,
            border_color=theme.color("border"),
            corner_radius=theme.radius("lg"),
            # The tab bar is a segmented button wearing the picker's
            # colours, so the two controls on this screen look related.
            segmented_button_fg_color=theme.color("card_bg"),
            segmented_button_selected_color=theme.color("accent"),
            segmented_button_selected_hover_color=theme.color("accent_hover"),
            segmented_button_unselected_color=theme.color("surface"),
            segmented_button_unselected_hover_color=theme.color("border"),
            segmented_button_font=theme.font("caption"),
            text_color=theme.color("text"),
            text_color_disabled=theme.color("text_secondary"),
            anchor="w",       # tab bar starts at the left, like a tab bar
        )
        for name in TABS:
            self._tabs.add(name)
        self._tabs.set(TAB_SPENDING)   # the donut is the headline chart

        # NOT gridded here: _apply_state() puts either the tab view or the
        # empty panel into row 4, once it knows which one the data wants.

    def _build_charts(self) -> None:
        """The four chart cards: a caption over an empty box to draw in.

        Each card is a permanent child of the frame it lives in - its
        tab's frame, or (for the Compare card) the body frame that
        _build_compare() put on the Compare tab. It is gridded once,
        here, and never moved again. _apply_state() therefore only has
        to decide between the tab view and the empty panel; the cards
        themselves stay put and keep their sizes.

        Each card stores its box (the frame the canvas is packed into)
        under the chart key, because that is the widget whose pixel size
        decides the figure's size.
        """
        gap = theme.spacing("sm")
        spending = self._tabs.tab(TAB_SPENDING)
        plan = self._tabs.tab(TAB_PLAN)

        def card(parent, row, column, columnspan, caption_text, key, padx):
            frame = ctk.CTkFrame(
                parent, corner_radius=theme.radius("lg"), border_width=1,
            )
            frame.grid(
                row=row, column=column, columnspan=columnspan,
                sticky="nsew", padx=padx,
            )
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(1, weight=1)

            caption = ctk.CTkLabel(
                frame, text=caption_text,
                font=theme.font("caption"), anchor="w",
            )
            caption.grid(
                row=0, column=0, sticky="ew",
                padx=theme.spacing("md"), pady=(theme.spacing("md"), theme.spacing("xs")),
            )

            # The drawing box. Transparent so the card's own colour
            # shows through behind the figure. It has no intrinsic size
            # of its own - the grid's weights decide how big it gets, and
            # the <Configure> below tells us the result.
            box = ctk.CTkFrame(frame, fg_color="transparent")
            box.grid(row=1, column=0, sticky="nsew",
                     padx=(theme.spacing("xs"), theme.spacing("xs")),
                     pady=(0, theme.spacing("xs")))

            # Redraw whenever this chart's box changes size. The first
            # Configure fires when the box is first laid out - including
            # the moment the user switches to its tab - which is how a
            # chart built while still hidden gets its real size. The event
            # itself has to be forwarded: the handler measures
            # event.width/height, and without it every Configure would
            # look like "no size given" and be ignored.
            box.bind("<Configure>",
                     lambda event, k=key: self._on_box_resized(k, event))

            self._boxes[key] = {"card": frame, "caption": caption, "box": box}

        # Spending tab: two columns, one card each, so both charts get the
        # full height of the band (the donut's whole problem before was
        # height, not width). Plan vs Actual: one card across everything,
        # because three groups of three bars need the width. Compare is
        # laid out like Plan for the same reason - two groups of three
        # bars, with the dropdowns and the salary line sitting ABOVE the
        # card inside _compare_body (row 3 is the card's; the body's
        # grid_rowconfigure(3, weight=1) gives it whatever is left).
        for column in range(2):
            spending.grid_columnconfigure(column, weight=1)
        spending.grid_rowconfigure(0, weight=1)
        plan.grid_columnconfigure(0, weight=1)
        plan.grid_rowconfigure(0, weight=1)

        card(spending, row=0, column=0, columnspan=1,
             caption_text="SPENDING SPLIT", key="split", padx=(0, gap))
        card(spending, row=0, column=1, columnspan=1,
             caption_text="SPENDING BY CATEGORY", key="categories", padx=(0, 0))
        card(plan, row=0, column=0, columnspan=1,
             caption_text="ALLOCATED VS SPENT", key="comparison", padx=(0, 0))
        card(self._compare_body, row=3, column=0, columnspan=1,
             caption_text="SPENT BY BUDGET", key="compare", padx=(0, 0))

    def _build_compare(self) -> None:
        """The Compare tab's body: two dropdowns, the salary line, and
        the friendly note (Phase 8.4).

        Everything here is built ONCE, like the rest of this screen -
        _apply_compare() fills it on each reload. The chart card is NOT
        made here: _build_charts() owns all four cards (it holds the
        shared card() helper) and grids the compare one into this
        body's row 3, which is exactly why _build_compare() runs before
        it.

        The tab is TWO frames: _compare_body (instruction + dropdowns +
        salary + card) and _compare_empty (the "not enough months"
        note). The underfilled state is then a single grid_remove() on
        the body - the dropdowns, the salary line and the chart card
        vanish together, so no half of a comparison can be left on
        screen with nothing to compare.
        """
        tab = self._tabs.tab(TAB_COMPARE)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)      # the body fills the band

        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        #   rows: 0 instruction | 1 dropdowns | 2 salary | 3 chart card
        # Row 3 (the card, gridded by _build_charts()) is the only
        # weighted one: it takes whatever the three fixed rows above
        # leave, so the chrome can never squeeze the figure, and the
        # figure never squeezes the controls.
        body.grid_rowconfigure(3, weight=1)
        self._compare_body = body

        # -- what to do ---------------------------------------------------
        self._compare_caption = ctk.CTkLabel(
            body, text="PICK TWO FINISHED CYCLES",
            font=theme.font("caption"), anchor="w",
            text_color=theme.color("text_secondary"),
        )
        self._compare_caption.grid(
            row=0, column=0, sticky="ew",
            pady=(0, theme.spacing("xs")),
        )

        # -- the two dropdowns --------------------------------------------
        # "vs" between them: with the instruction above, the left menu
        # is the first cycle and the right one the second - the chart's
        # groups sit in that same left-to-right order, so the salary
        # line under it can say "Rs. 200,000 vs Rs. 120,000" and still
        # point at the right month.
        pickers = ctk.CTkFrame(body, fg_color="transparent")
        pickers.grid(row=1, column=0, sticky="ew",
                     pady=(0, theme.spacing("sm")))
        pickers.grid_columnconfigure(0, weight=1)   # both menus share
        pickers.grid_columnconfigure(2, weight=1)   # the width equally

        def menu(parent):
            """One cycle dropdown, in the Settings screen's option-menu
            palette (the app's only other CTkOptionMenu) so the app's
            two dropdowns look like the same control.

            width/dynamic_resizing are LAYOUT sizes, not palette - the
            same precedent as Settings' 100 px day menu: a fixed 170
            fits the longest label ("September 2026") and stops the
            "vs" from sliding sideways when the selection changes.
            """
            return ctk.CTkOptionMenu(
                parent,
                width=170,
                dynamic_resizing=False,
                corner_radius=theme.radius("sm"),
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
                # Neither menu says which one fired, and neither needs
                # to: the handler reads BOTH back - the pair on screen
                # is the pair to compare.
                command=self._on_compare_changed,
            )

        self._compare_menu_a = menu(pickers)
        self._compare_menu_a.grid(row=0, column=0, sticky="ew")

        self._compare_vs = ctk.CTkLabel(
            pickers, text="vs", font=theme.font("caption"),
            anchor="center", text_color=theme.color("text_secondary"),
        )
        self._compare_vs.grid(row=0, column=1, padx=theme.spacing("sm"))

        self._compare_menu_b = menu(pickers)
        self._compare_menu_b.grid(row=0, column=2, sticky="ew")

        # -- the salary line ----------------------------------------------
        # Salary is a per-cycle figure too (the 8.3 rule: each cycle's
        # OWN salary), but it is not a bar - so it gets one honest line
        # under the pickers. _fill_compare() appends the "measured at
        # today's rate" footnote to it whenever a selected cycle has no
        # salary of its own on file.
        self._compare_salary = ctk.CTkLabel(
            body, text="", font=theme.font("caption"), anchor="w",
            justify="left", wraplength=COMPARE_NOTE_WRAP,
            text_color=theme.color("text_secondary"),
        )
        self._compare_salary.grid(
            row=2, column=0, sticky="ew",
            pady=(0, theme.spacing("xs")),
        )

        # -- the friendly underfilled note --------------------------------
        # A direct child of the TAB, outside the body: when there are
        # fewer than two finished cycles the body is hidden wholesale
        # and this is all that is left of the tab.
        note = ctk.CTkFrame(tab, fg_color="transparent")
        note.grid(row=1, column=0, sticky="ew",
                  pady=(theme.spacing("xl"), 0))
        note.grid_remove()          # _apply_compare() decides visibility

        self._compare_empty_headline = ctk.CTkLabel(
            note, text="Nothing to compare yet",
            font=theme.font("section"), anchor="center", justify="center",
            text_color=theme.color("text"),
        )
        self._compare_empty_headline.grid(
            row=0, column=0, padx=theme.spacing("lg"),
            pady=(0, theme.spacing("sm")),
        )
        self._compare_empty_body = ctk.CTkLabel(
            note,
            text=("Comparing needs at least two finished salary cycles.\n"
                  "Your current cycle is still running - it is in the "
                  "statistics above. Finished cycles appear here as soon "
                  "as a salary month ends."),
            font=theme.font("body"), anchor="center", justify="center",
            text_color=theme.color("text_secondary"),
        )
        self._compare_empty_body.grid(
            row=1, column=0, padx=theme.spacing("xl"),
        )
        self._compare_empty = note

    def _build_empty_state(self) -> None:
        """The friendly panel shown INSTEAD of the tab view when empty.

        Always built (and always themed) - only its visibility moves, so
        a first launch looks deliberate rather than broken.
        """
        self._empty_card = ctk.CTkFrame(
            self, corner_radius=theme.radius("lg"), border_width=1,
        )
        # Row 4, the same row the tab view uses, but NOT gridded yet:
        # _apply_state() decides which of the two is visible. "new" (and
        # not "nsew") pins it to the top of that weighted row instead of
        # centring it in the middle of a band sized for a chart.
        self._empty_card.grid_columnconfigure(0, weight=1)

        self._empty_headline = ctk.CTkLabel(
            self._empty_card,
            text="No spending to report yet",
            font=theme.font("section"),
            anchor="center", justify="center",
        )
        self._empty_headline.grid(
            row=0, column=0,
            padx=theme.spacing("lg"),
            pady=(theme.spacing("xl"), theme.spacing("sm")),
        )

        self._empty_body = ctk.CTkLabel(
            self._empty_card,
            text=(
                "Log an expense from the Daily Expenses screen and your "
                "charts will appear here.\n"
                "Your salary, budgets and categories are already set up - "
                "only the spending is missing."
            ),
            font=theme.font("body"),
            anchor="center", justify="center",
        )
        self._empty_body.grid(
            row=1, column=0,
            padx=theme.spacing("xl"),
            pady=(0, theme.spacing("xl")),
        )

    def _build_history(self) -> None:
        """The History tab: a scrollable list plus the salary footnote.

        Phase 8.3. Built once, like every other widget on this screen -
        the ROWS inside the list are rebuilt by _apply_history() on each
        reload. None of it is a chart, so the matplotlib palette
        machinery does not apply here: just theme colours on labels,
        all re-applied by refresh_theme().
        """
        tab = self._tabs.tab(TAB_HISTORY)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)      # the list takes the height

        # Cycles never stop arriving (one per month, forever), so the
        # records scroll instead of stacking. The scrollbar is themed
        # here so it does not fall back to CustomTkinter's own grey -
        # the same three colours the other screens' lists use.
        self._history_list = ctk.CTkScrollableFrame(
            tab,
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._history_list.grid(row=0, column=0, sticky="nsew")
        # Children of a CTkScrollableFrame are gridded onto its inner
        # window, so this makes column 0 take the full usable width.
        self._history_list.grid_columnconfigure(0, weight=1)

        # The salary caveat, pinned UNDER the list rather than inside it:
        # it applies to every record and must stay readable even when the
        # list is empty. Its text quotes the salary figure, so
        # _apply_history() restates it on every reload.
        self._history_note = ctk.CTkLabel(
            tab, text="", font=theme.font("caption"),
            anchor="w", justify="left",
            wraplength=HISTORY_NOTE_WRAP,
        )
        self._history_note.grid(
            row=1, column=0, sticky="ew",
            pady=(theme.spacing("sm"), 0),
        )

    # ------------------------------------------------------------------
    # Reading the holders into the widgets (no drawing here)
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        """Re-read every figure from reports.py into the screen's widgets.

        Called at startup and after any holder notifies us. It fills the
        text and fixes up which panels are visible; drawing the charts is
        left to _draw_all(), so a data refresh and a theme flip can both
        choose whether they need to repaint the figures.
        """
        self._data = reports.report(self._budget)
        self._apply_text()
        self._apply_history()
        self._apply_compare()      # Phase 8.4: pickers, salary line, note
        self._apply_state()

    def _apply_text(self) -> None:
        """Put the statistics into the four tiles."""
        stats = self._data["stats"]

        # 1. Top category - the category NAME is the answer, so it is the
        #    headline, and it wears its budget's colour so it reads as the
        #    same object as its slice in the donut.
        if stats["highest_label"]:
            top = self._stats[0]
            top["value"].configure(
                text=stats["highest_label"],
                text_color=(_budget_colour(stats["highest_budget"])
                            if stats["highest_budget"]
                            else theme.color("text_secondary")),
            )
            top["detail"].configure(text=f"Rs. {stats['highest_amount']:,}")
        else:
            self._stats[0]["value"].configure(text="—",
                                              text_color=theme.color("text_secondary"))
            self._stats[0]["detail"].configure(text="Nothing logged yet")

        # 2. The current SALARY CYCLE (Phase 8.1) - the caption names the
        #    cycle's own month, so the user knows which window they are
        #    looking at. With the default start day of 1 that month is
        #    simply the calendar month, exactly as before.
        #
        #    Phase 8.3: the caption gained a SECOND line with the cycle's
        #    exact days ("10 Nov – 9 Dec"), formatted in reports.py from
        #    the same cycle key as the month name. "November" alone was
        #    ambiguous the moment the start day shifted the window - the
        #    range removes it. Two lines in one label, so no other tile
        #    and no grid row had to change.
        self._stats[1]["caption"].configure(
            text=(f"SPENT IN {stats['month_name'].upper()}\n"
                  f"{stats['month_range']}")
        )
        self._stats[1]["value"].configure(
            text=f"Rs. {stats['month_total']:,}",
            text_color=theme.color("text"),
        )
        self._stats[1]["detail"].configure(
            text=f"of Rs. {stats['salary']:,} salary"
        )

        # 3. All-time spent.
        self._stats[2]["value"].configure(
            text=f"Rs. {stats['total_spent']:,}",
            text_color=theme.color("text"),
        )
        self._stats[2]["detail"].configure(
            text=(f"{stats['entries']} expense"
                  f"{'' if stats['entries'] == 1 else 's'} logged")
        )

        # 4. Still available. Green while there is anything left, muted
        #    at zero - the Dashboard already owns the alarming version
        #    (its warn/danger thresholds), so a plain report card should
        #    state the number rather than shout it.
        remaining_colour = (theme.color("success") if stats["remaining"] > 0
                            else theme.color("text_secondary"))
        self._stats[3]["value"].configure(
            text=f"Rs. {stats['remaining']:,}",
            text_color=remaining_colour,
        )
        self._stats[3]["detail"].configure(
            text=f"of Rs. {stats['salary']:,} salary"
        )

    def _apply_history(self) -> None:
        """(Re)build the History tab's rows from self._data["history"].

        Phase 8.3. Rebuilt from scratch rather than updated in place: the
        row set changes whenever a cycle rolls over or an expense is
        logged, and a teardown is far easier to reason about than a diff
        when the widgets are this few. refresh_theme() calls it too, so
        every colour derived from the theme - and from the saved /
        overspent state - is re-derived on a dark/light flip.
        """
        for child in self._history_list.winfo_children():
            child.destroy()

        # The footnote answers "which salary was this saving measured
        # against?" - and since the 8.3 fix the honest answer depends on
        # the LIST: every cycle the feature has lived through carries its
        # own recorded salary, while cycles older than the feature fell
        # back to today's. The per-record flag (reports.cycle_history()
        # sets it from the cycle_salary table) tells the two apart, so
        # the note only claims "your current salary" about the cycles
        # where that is actually true. Both texts are restated on every
        # reload, and refresh_theme() calls this too, so the wording
        # can never go stale after a settings change or a flip.
        rows = self._data["history"]
        salary = self._data["stats"]["salary"]
        # A record missing the flag counts as UNrecorded: if the two
        # ever disagree, the note should over-admit the fallback rather
        # than claim a figure is that cycle's own.
        unrecorded = any(not record.get("salary_recorded", False)
                         for record in rows)
        if unrecorded:
            note = (
                "Saved = what you spent that cycle taken off the salary "
                "that cycle paid. Cycles from before salary history was "
                "recorded have no salary of their own on file - those "
                f"are measured against your CURRENT salary "
                f"(Rs. {salary:,})."
            )
        else:
            note = (
                "Saved = what you spent that cycle taken off the salary "
                "that cycle paid. Each cycle's salary is recorded "
                "automatically as you go, so every figure in this list "
                "is that cycle's own arithmetic."
            )
        self._history_note.configure(text=note)
        if not rows:
            # Friendly, not blank: the tab exists, it simply has nothing
            # FINISHED to show yet. The current cycle is deliberately not
            # here - it is not history, and its figures are already on
            # the tiles above.
            headline = ctk.CTkLabel(
                self._history_list,
                text="No finished salary cycles yet",
                font=theme.font("section"), anchor="center",
                justify="center", text_color=theme.color("text"),
            )
            headline.grid(
                row=0, column=0,
                pady=(theme.spacing("xl"), theme.spacing("sm")),
            )
            body = ctk.CTkLabel(
                self._history_list,
                text=("History appears once a salary cycle ends. Your "
                      "current cycle is in the statistics above."),
                font=theme.font("body"), anchor="center",
                justify="center", text_color=theme.color("text_secondary"),
            )
            body.grid(row=1, column=0, padx=theme.spacing("lg"))
            return

        gap = theme.spacing("sm")
        for index, record in enumerate(rows):
            saved = record["saved"]
            positive = saved >= 0

            card = ctk.CTkFrame(
                self._history_list,
                corner_radius=theme.radius("md"), border_width=1,
                # Painted here as well as in refresh_theme(): this card
                # is created AFTER that pass whenever a cycle rolls over,
                # so it must arrive already wearing the active palette.
                fg_color=theme.color("card_bg"),
                border_color=theme.color("border"),
            )
            # One card per cycle, stacked newest-first. Every card keeps
            # the same bottom gap, so the list never ends flush against
            # the scrollbar.
            card.grid(row=index, column=0, sticky="ew", pady=(0, gap))
            # Column 0 grows, column 1 keeps its natural width - which
            # pins the verdict to the right-hand edge, where the eye
            # looks for a verdict on every other card in this app.
            card.grid_columnconfigure(0, weight=1)

            name = ctk.CTkLabel(
                card, text=record["label"],
                font=theme.font("value"), anchor="w",
                text_color=theme.color("text"),
            )
            name.grid(
                row=0, column=0, sticky="w",
                padx=(theme.spacing("md"), theme.spacing("sm")),
                pady=(theme.spacing("sm"), 0),
            )

            detail = ctk.CTkLabel(
                card,
                text=(f"{record['range']}   ·   "
                      f"Rs. {record['spent']:,} spent"),
                font=theme.font("caption"), anchor="w",
                text_color=theme.color("text_secondary"),
            )
            detail.grid(
                row=1, column=0, sticky="w",
                padx=(theme.spacing("md"), theme.spacing("sm")),
                pady=(theme.spacing("xs"), theme.spacing("sm")),
            )

            verdict = (f"Saved Rs. {saved:,} this cycle" if positive
                       else f"Overspent Rs. {-saved:,} this cycle")
            message = ctk.CTkLabel(
                card, text=verdict,
                font=theme.font("value"), anchor="e",
                # The state colours the app already uses for good and
                # bad news everywhere else, so a saved cycle and an
                # overspent one are told apart at a glance in BOTH
                # palettes - never by a colour invented here.
                text_color=theme.color("success" if positive else "danger"),
            )
            # Rows 0-1, so the verdict sits vertically centred against
            # the two lines of text on its left.
            message.grid(
                row=0, column=1, rowspan=2, sticky="e",
                padx=(0, theme.spacing("md")),
            )

    def _apply_compare(self) -> None:
        """Fill the Compare tab from self._data["history"] (Phase 8.4).

        Restated on every reload AND from refresh_theme() - the same
        contract _apply_history() has - so a month rolling over, an
        expense logged elsewhere or a dark/light flip can never leave
        stale cycle names, salaries or a stale note on this tab.

        Visibility first: with fewer than two FINISHED cycles there is
        nothing to compare, and the body (dropdowns + salary line +
        chart card, all one frame) hides in favour of the friendly
        note. The current cycle never counts - it is still running,
        exactly as on the History tab.
        """
        history = self._data["history"]

        if len(history) < 2:
            self._compare_body.grid_remove()
            self._compare_empty.grid(row=1, column=0, sticky="ew",
                                     pady=(theme.spacing("xl"), 0))
            # No stale data at all: a redraw that lands while the note
            # is up must draw _draw_compare()'s "nothing yet" sentence,
            # not a chart of cycles that no longer exist - and the
            # salary line must not keep quoting a pair nobody sees.
            self._compare_data = []
            self._compare_salary.configure(text="")
            return

        self._compare_body.grid(row=0, column=0, sticky="nsew")
        self._compare_empty.grid_remove()

        # Both dropdowns offer every finished cycle, newest first - the
        # order History lists them in.
        labels = [record["label"] for record in history]
        label_to_key = {record["label"]: record["key"] for record in history}
        self._label_to_key = label_to_key
        key_of = {record["key"]: record["label"] for record in history}

        # Keep the pair the user already chose for as long as both
        # cycles still exist (a wiped ledger is the only way a key can
        # vanish); otherwise default to the two newest, which is the
        # most interesting pair to open on.
        available = set(key_of)
        keys = self._compare_keys
        key_a = keys[0] if keys and keys[0] in available else history[0]["key"]
        key_b = (keys[1] if keys and keys[1] in available
                 else next(record["key"] for record in history
                           if record["key"] != key_a))
        self._compare_keys = (key_a, key_b)

        for menu in (self._compare_menu_a, self._compare_menu_b):
            menu.configure(values=labels)
        self._compare_menu_a.set(key_of[key_a])
        self._compare_menu_b.set(key_of[key_b])

        # The figures themselves. compare_cycles() copies them straight
        # from cycle_history(), so this tab and History can never show
        # two different numbers for the same month.
        self._compare_data = reports.compare_cycles([key_a, key_b])
        self._fill_compare()

    def _fill_compare(self) -> None:
        """Put the chosen pair's salary line on screen.

        Split out of _apply_compare() because the dropdown command needs
        exactly this much (the pickers' own values do not change when
        the user picks) - and because it is the only text on this tab
        that depends on WHICH cycles are selected.
        """
        rows = self._compare_data
        if not rows:
            self._compare_salary.configure(text="")
            return

        # One line per cycle, left to right - the same order the chart's
        # groups sit in below it.
        line = "Salary: " + "  ·  ".join(
            f"{row['label']} Rs. {row['salary']:,}" for row in rows
        )

        # The 8.3 honesty rule, carried over: a cycle with no salary of
        # its own on file is measured against TODAY's salary, and this
        # tab must admit that rather than imply the figure is that
        # month's own. (The flag comes from the cycle_salary table via
        # cycle_history() - never inferred by comparing values, because
        # a recorded salary can legitimately equal today's.)
        unrecorded = [row for row in rows
                      if not row.get("salary_recorded", False)]
        if unrecorded:
            salary = self._data["stats"]["salary"]
            line += ("\n\u2020 Some of these cycles have no salary of their "
                     "own on file - their saved figure is measured against "
                     f"your CURRENT salary (Rs. {salary:,}).")
        self._compare_salary.configure(text=line)

    def _apply_state(self) -> None:
        """Swap between the chart tabs and the empty panel.

        This is the only place that puts anything into row 4. The tab view
        and the empty panel share that row, so exactly one of them is ever
        gridded - the weighted row can never end up holding a gap while a
        collapsed row below it is left carrying the visible panel.

        The chart cards themselves are NOT touched: they were gridded once
        inside their own tab in _build_charts() and stay there. While the
        tab view is out of the grid they are simply unmapped, which is why
        no figure gets built for a first-time empty account.
        """
        empty = self._data["empty"]
        pad = theme.spacing("lg")

        if empty:
            self._tabs.grid_remove()
            # "new" pins it to the top of the tall row; "nsew" would leave
            # a chart-sized void under a panel that is only two lines tall.
            # md, not lg, underneath: CTkTabview already puts its own
            # corner_radius worth of padding INSIDE its border, so an lg
            # outside it was two bottom margins stacked.
            self._empty_card.grid(
                row=4, column=0, sticky="new",
                padx=pad, pady=(0, theme.spacing("md")),
            )
        else:
            self._empty_card.grid_remove()
            self._tabs.grid(
                row=4, column=0, sticky="nsew",
                padx=pad, pady=(0, theme.spacing("md")),
            )

        # Nothing to filter when there is nothing to show.
        self._picker.configure(state="disabled" if empty else "normal")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_picker_changed(self, value: str) -> None:
        """The user picked a budget for the category chart."""
        self._budget = PICKER_KEYS.get(value, None)
        # Only the category chart depends on this choice, so only that
        # figure is rebuilt - the other two would be redrawn identically.
        self._data = reports.report(self._budget)
        self._redraw("categories")

    def _on_compare_changed(self, value: str) -> None:
        """One of the Compare tab's dropdowns picked a different cycle.

        Phase 8.4. Only the compare chart (and the salary line quoting
        the pair) depend on this choice, so only those are rebuilt -
        exactly the bargain _on_picker_changed() makes for the category
        chart.

        BOTH menus are read back rather than trusting `value`: whichever
        one fired, the pair on screen is the pair to compare. A month
        NAME that no longer maps to a cycle (possible for a moment
        after a data change) is left alone - the next reload rebuilds
        the menus from fresh history anyway.
        """
        key_a = self._label_to_key.get(self._compare_menu_a.get())
        key_b = self._label_to_key.get(self._compare_menu_b.get())
        if key_a is None or key_b is None:
            return

        self._compare_keys = (key_a, key_b)
        # Same read reports.py does for the tab itself: the cycle keys
        # go in, history's own figures (plus the breakdown) come out.
        self._compare_data = reports.compare_cycles([key_a, key_b])
        self._fill_compare()
        self._redraw("compare")

    def _on_data_changed(self) -> None:
        """One of the four holders changed - bring the report up to date."""
        # Screens are meant to live for the whole session, but a test may
        # destroy one while a holder still holds its callback. Checking
        # first keeps that from raising back into the holder's _notify().
        if not self.winfo_exists():
            return
        self._reload()
        self._draw_all()

    def _on_box_resized(self, key: str, event=None) -> None:
        """A chart's box changed size - redraw the figure to match.

        Debounced: dragging the window edge fires <Configure> dozens of
        times a second, and rebuilding three figures on each one would
        make the whole app feel sticky. Also self-limiting: a redraw
        never asks for a size larger than the box it was given, so this
        cannot feed back into another resize.
        """
        if event is None:
            return
        if event.width < MIN_CHART_W or event.height < MIN_CHART_H:
            return  # not laid out yet (or momentarily collapsed)
        if self._drawn_at.get(key) == (event.width, event.height):
            return  # nothing actually moved

        job = self._resize_jobs.get(key)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass  # already fired; harmless either way
        self._resize_jobs[key] = self.after(
            REDRAW_DELAY_MS, lambda: self._redraw(key)
        )

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_all(self) -> None:
        """Rebuild all four charts at their current sizes.

        Deliberately does NOT check winfo_ismapped() first. It looks like
        a sensible optimisation ("don't draw what nobody can see"), but
        CustomTkinter's set_appearance_mode() - which main.py calls
        BEFORE it walks the screens on a theme flip - briefly unmaps
        everything while it repaints. Guarding on the mapped state would
        therefore skip exactly the redraw the theme flip is supposed to
        cause, and the charts would keep the previous palette until
        something else happened to redraw them.

        Drawing an unmapped chart is harmless: winfo_width() still
        reports the size the box last had, so the figure comes out at the
        right size and is simply waiting on screen for its box to
        reappear. The MAX floor covers a box that has never been mapped
        at all (it reports 1x1).
        """
        for key in ("split", "categories", "comparison", "compare"):
            self._redraw(key)

    def _redraw(self, key: str) -> None:
        """Build (or rebuild) one figure inside its box and paint it."""
        job = self._resize_jobs.pop(key, None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass

        box = self._boxes[key]["box"]
        # winfo_width() is 1 until the widget has been laid out at least
        # once - which for a chart on a tab the user has not opened yet
        # stays 1 for as long as that tab stays shut. Drawing then would
        # bake a 240x140 canvas into the box. Waiting for the first real
        # Configure costs one frame and lets the layout decide the size
        # first; visiting the tab is what produces that Configure.
        # Once laid out, the size sticks even while unmapped (switching
        # tabs, or a theme flip remapping everything), which is what lets
        # refresh_theme() repaint every figure at the right size.
        if box.winfo_width() <= 1:
            return

        width = max(box.winfo_width(), MIN_CHART_W)
        height = max(box.winfo_height(), MIN_CHART_H)

        # Everything matplotlib colours itself gets OUR palette first, so
        # no figure can be created with its light-mode defaults showing.
        _apply_matplotlib_palette()
        face = theme.color("card_bg")

        figure = self._figures.get(key)
        if figure is None:
            # First draw: make the figure and its canvas, and hang on to
            # them - a redraw then only clears the figure, so the Tk
            # widget is never destroyed and rebuilt behind the user's eye.
            figure = Figure(figsize=(width / CHART_DPI, height / CHART_DPI),
                            dpi=CHART_DPI, facecolor=face)
            canvas = FigureCanvasTkAgg(figure, master=box)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._figures[key] = figure
            self._canvases[key] = canvas
        else:
            figure.clf()                       # drop last draw's axes
            # forward=False: matplotlib must NOT resize the Tk canvas in
            # response - it is packed with fill/expand, so Tk owns its
            # geometry and a size request from matplotlib could push the
            # card wider and set off a resize loop.
            figure.set_size_inches(width / CHART_DPI, height / CHART_DPI,
                                   forward=False)
            figure.set_facecolor(face)

        if key == "split":
            self._draw_split(figure, width, height)
        elif key == "categories":
            self._draw_categories(figure, width, height)
        elif key == "compare":
            self._draw_compare(figure, width, height)
        else:
            self._draw_comparison(figure, width, height)

        self._canvases[key].draw()
        self._drawn_at[key] = (width, height)

    # -- chart 1: the donut ------------------------------------------------

    def _draw_split(self, figure: Figure, width: int, height: int) -> None:
        """Spending split across the three budgets.

        The legend - not the wedges - carries the numbers. Text painted
        ON a coloured slice would have to flip between white and dark ink
        depending on whether the app is in dark mode (our info/warning/
        success are dark in LIGHT mode and bright in DARK mode), and the
        palette has no single key that contrasts with both. Putting the
        figures in the legend keeps every one of them on card_bg, where
        the app's own text contrast has already been checked.
        """
        split = self._data["split"]
        with_money = [row for row in split if row["amount"] > 0]
        total = sum(row["amount"] for row in split)

        # Reserve the bottom band for the legend: three stacked rows come
        # to roughly 66 px, expressed as a fraction of this box.
        legend_band = max(0.24, min(0.4, 66.0 / max(height, 1)))
        left, right, top = 0.03, 0.97, 0.99
        figure.subplots_adjust(left=left, right=right, top=top,
                               bottom=legend_band)
        axes = figure.add_subplot(111)
        axes.set_facecolor(theme.color("card_bg"))
        axes.axis("off")           # a ring needs no frame, ticks or grid

        if with_money and total > 0:
            axes.pie(
                [row["amount"] for row in with_money],
                colors=[_budget_colour(row["key"]) for row in with_money],
                startangle=90,          # first budget starts at 12 o'clock
                counterclock=False,     # and they run clockwise, in order
                wedgeprops={
                    # 0.30 of the radius is the ring; the other 0.70 is
                    # the hole the total sits in. Thinning the ring is
                    # half of how the label got its margin back (the
                    # other half is the taller box the tabs give us).
                    "width": DONUT_RING,
                    "edgecolor": theme.color("card_bg"),  # slice separators
                    "linewidth": 2,
                },
            )
            axes.set_aspect("equal")

            # --- how big is the hole, in PIXELS? ------------------------
            # The two centre lines are placed in DATA units, where the
            # ring's radius is 1, so we need that radius in pixels before
            # we can put anything inside it. Axes.get_position() is NOT a
            # plain read: it calls apply_aspect() first, which is what
            # shrinks the box from the full subplots_adjust rectangle down
            # to the square an equal-aspect ring needs. matplotlib's own
            # docstring says to call it yourself when you want the real
            # box before the figure is drawn - which is exactly here.
            # The ring's radius is then one data unit = side / span.
            #
            # Units: width/height are canvas pixels, and _pt() turns a
            # theme size into points that 96 dpi hands straight back as
            # canvas pixels - so theme FONT_SPECS sizes, theme.spacing()
            # values and this radius are all the same currency below.
            position = axes.get_position()
            side = min(position.width * width, position.height * height)
            span = axes.get_xlim()[1] - axes.get_xlim()[0]  # pie() sets this
            radius_px = max(side / span if span > 0 else 1.0, 1.0)
            hole_px = 2.0 * (1.0 - DONUT_RING) * radius_px  # hole DIAMETER

            money = f"Rs. {total:,}"
            money_px = float(theme.FONT_SPECS["amount"]["size"])
            spent_px = float(theme.FONT_SPECS["caption"]["size"])

            # A hole can only hold so much type. If a very large total
            # would push the headline out to the colour, step the size
            # down until it fits with clear air on each side, rather than
            # let the digits touch the ring. The size still originates in
            # theme.py - this only ever SHRINKS it, and only when the
            # hole cannot take it whole. Half a character-em each is a
            # safe upper bound for digits plus the "Rs. " prefix
            # (measured: "Rs. 63,200" is 4.9 em wide).
            #
            # The clear air is theme.spacing("sm"), but never more than
            # an eighth of the hole. A FIXED sm is 20 px, which is a
            # comfortable sixth of the 134 px hole at the default window
            # but over a third of the 57 px hole at the app's minimum
            # window, where it starves the headline for no gain. Capping
            # the reserve as a FRACTION of the hole keeps the same
            # proportion of air at every size; the theme value still
            # decides it everywhere the hole is big enough to afford it.
            #
            # There is deliberately NO minimum size: a floor would put
            # the digits back into the ring at the app's minimum window,
            # which is the very bug this replaced. And "spent" comes
            # down with the amount, never larger than the figure it
            # labels - a caption bigger than the number reads upside
            # down. At the default window neither line moves at all.
            reserve_px = min(theme.spacing("sm"), hole_px * 0.125)
            room_px = hole_px - 2 * reserve_px
            widest_px = len(money) * money_px * 0.5
            if widest_px > room_px and len(money) > 0:
                money_px = room_px / (len(money) * 0.5)
                spent_px = min(spent_px, money_px)

            # The gap between the two lines used to be a FIXED DATA offset
            # (+0.08 / -0.16) - a distance measured in ring radii, so the
            # bigger the donut grew the further apart they drifted, and the
            # smaller it got the closer they sat. Work the gap out in
            # PIXELS instead (one line is about as tall as its own font
            # size, plus theme.spacing("xs") of clear air) and convert it
            # back to data units with the radius above. The pair then reads
            # as one tight block centred in the hole at ANY window size.
            offset_px = ((money_px + spent_px) / 4.0
                         + theme.spacing("xs") / 2.0)
            offset = offset_px / radius_px

            axes.text(0, offset, money, ha="center", va="center",
                      color=theme.color("text"),
                      fontsize=_pt(money_px), fontweight="bold")
            axes.text(0, -offset, "spent", ha="center", va="center",
                      color=theme.color("text_secondary"),
                      fontsize=_pt(spent_px))

        # Every budget appears, including the ones at Rs. 0 - a slice
        # with no area would otherwise leave "where did Savings go?"
        # unanswered. Percentages are worked out here for the same reason.
        handles = [
            Patch(
                facecolor=_budget_colour(row["key"]),
                label=(f"{row['label']}   Rs. {row['amount']:,}"
                       f"   {round(row['amount'] / total * 100) if total else 0}%"),
            )
            for row in split
        ]
        figure.legend(
            handles=handles, loc="lower center",
            frameon=True, framealpha=1.0,   # fully our palette, not 80% of it
            fontsize=_font("caption"),
        )

    # -- chart 2: spending by category ------------------------------------

    def _draw_categories(self, figure: Figure, width: int, height: int) -> None:
        """Horizontal bars, one per category, biggest at the top.

        Horizontal because category names are long ("Shopping +
        Installment payments"); on a vertical chart they would have to be
        rotated or truncated.
        """
        rows = self._data["categories"]

        axes = figure.add_subplot(111)
        axes.set_facecolor(theme.color("card_bg"))

        if not rows:
            # A budget the user has not spent in yet - a sentence, not an
            # empty pair of axes.
            axes.axis("off")
            budget_name = (BUDGET_LABELS[self._budget]
                           if self._budget in BUDGET_LABELS else "your budgets")
            axes.text(
                0.5, 0.5, f"Nothing spent in {budget_name} yet.",
                ha="center", va="center",
                color=theme.color("text_secondary"),
                fontsize=_font("body"),
                transform=axes.transAxes,
            )
            return

        labels = [row["label"] for row in rows]
        amounts = [row["amount"] for row in rows]
        # Grey for money with no category of its own - "text_secondary"
        # rather than "warning", because warning already means Wants and
        # a Wants chart would then have two colours meaning one budget.
        colours = [
            _budget_colour(row["budget"]) if row["budget"]
            else theme.color("text_secondary")
            for row in rows
        ]

        # Horizontal bars (barh): category names are long ("Shopping +
        # Installment payments"), and on a vertical chart they would have
        # to be rotated or truncated. The X axis is therefore the money
        # axis and the Y axis the category axis - which is what the
        # margins, grid, formatter and inverted Y below all assume.
        # NOTE barh's signature: barh(y, width, height=...) - the second
        # POSITIONAL is the bar's LENGTH (the money), while `height` is
        # its thickness in category units. Passing width= here would
        # collide with that positional and raise.
        axes.barh(labels, amounts, color=colours, height=0.62)

        # Horizontal space to the left of the bars for the longest name.
        # y tick labels are drawn OUTSIDE the axes and matplotlib does
        # not make room for them, so the margin is estimated from the
        # longest label (about half a font size per character at 12 px)
        # and clamped so a short name cannot leave a huge empty gutter.
        longest = max(len(label) for label in labels)
        estimated = (longest * 0.5 * _font("caption") * CHART_DPI / 72.0) + 16
        left = min(0.5, max(0.2, estimated / max(width, 1)))
        figure.subplots_adjust(left=left, right=0.97, top=0.95, bottom=0.12)

        # Room for "Rs. 12,000" past the end of the longest bar.
        top_amount = max(amounts)
        axes.set_xlim(0, top_amount * 1.5)

        # The exact figure at the end of each bar - a finance report has
        # to be readable to the rupee, and the axis alone only gets you
        # within a few hundred.
        for index, row in enumerate(rows):
            axes.text(
                row["amount"] * 1.03, index, f"Rs. {row['amount']:,}",
                ha="left", va="center",
                color=theme.color("text"),
                fontsize=_font("caption"),
            )

        # Biggest first: bar() drew them bottom-up, so flip the axis.
        axes.invert_yaxis()

        self._style_axes(axes, grid_axis="x")
        axes.xaxis.set_major_formatter(MONEY)

    # -- chart 3: allocated vs planned vs spent ---------------------------

    def _draw_comparison(self, figure: Figure, width: int, height: int) -> None:
        """Three bars per budget: what it owns, what is planned in it,
        and what was actually spent.

        The over/under note above each group is the point of the chart -
        it answers "am I alright?" directly instead of making the user
        subtract two bars in their head.
        """
        rows = self._data["comparison"]
        axes = figure.add_subplot(111)
        axes.set_facecolor(theme.color("card_bg"))

        positions = list(range(len(rows)))
        offset = 0.26          # how far each bar sits from its group's centre
        bar_width = 0.24

        # Allocated is the neutral reference, planned is the brand's plan
        # colour, spent is the budget's own colour - so the bar that
        # means "money actually gone" keeps the identity Needs/Wants/
        # Savings have everywhere else in the app.
        axes.bar([p - offset for p in positions],
                 [row["allocated"] for row in rows], bar_width,
                 label="Allocated", color=theme.color("text_secondary"))
        axes.bar(positions,
                 [row["planned"] for row in rows], bar_width,
                 label="Planned (fixed)", color=theme.color("accent"))
        axes.bar([p + offset for p in positions],
                 [row["spent"] for row in rows], bar_width,
                 label="Spent", color=[_budget_colour(row["key"])
                                       for row in rows])

        # Headroom for the over/under note that sits above each group.
        tallest = max(max(row["allocated"], row["planned"], row["spent"])
                      for row in rows)
        axes.set_ylim(0, tallest * 1.28)

        # The over/under verdict, one per budget, in the colour the app
        # already uses for good news and bad news.
        for index, row in enumerate(rows):
            difference = row["allocated"] - row["spent"]
            if difference < 0:
                note, colour = f"OVER by Rs. {-difference:,}", theme.color("danger")
            else:
                note, colour = f"under Rs. {difference:,}", theme.color("success")
            group_top = max(row["allocated"], row["planned"], row["spent"])
            axes.text(index, group_top * 1.04, note,
                      ha="center", va="bottom",
                      color=colour, fontsize=_font("caption"),
                      fontweight="bold")

        axes.set_xticks(positions)
        axes.set_xticklabels([row["label"] for row in rows])

        # Fixed margins rather than tight_layout(): the legend sits in the
        # band this reserves above the axes, and tight_layout does not
        # know that band exists.
        figure.subplots_adjust(left=0.11, right=0.97, top=0.82, bottom=0.14)

        self._style_axes(axes, grid_axis="y")
        axes.yaxis.set_major_formatter(MONEY)
        axes.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3,
                    frameon=True, framealpha=1.0, fontsize=_font("caption"))

    # -- chart 4: two finished cycles side by side (Phase 8.4) -----------

    def _draw_compare(self, figure: Figure, width: int, height: int) -> None:
        """The chosen cycles side by side: three budget bars in each.

        GROUPS ARE THE CYCLES, BARS ARE THE BUDGETS - so the Needs bar
        of the left month sits directly above the Needs bar of the right
        month, and one glance at the gap between two same-coloured bars
        says where the spending moved. Each bar therefore wears its
        BUDGET's colour (info/warning/success), which is the house rule:
        a bar that means Needs is Needs-coloured on every screen in the
        app, and the legend names the budgets the same way the donut
        does.

        Above each group, stacked like the comparison chart's over/under
        note: what the cycle SPENT, then what it SAVED - saved in the
        colour the app already uses for good and bad news, so an
        overspent month says OVERSPENT in red without a new colour
        entering the palette. Exact figures live there rather than in a
        table because the chart already has the two cycles side by
        side; the salary (the one figure that is not spending) sits on
        its own line above the card, in _fill_compare().

        The x labels carry the cycle's name AND its exact range: month
        names alone were ambiguous the moment a shifted start day moved
        the window - the 8.3 lesson, applied here too.

        Geometry (offset, width, margins, legend) deliberately mirrors
        _draw_comparison(): two charts of the same family should sit
        identically on their cards.
        """
        rows = self._compare_data
        axes = figure.add_subplot(111)
        axes.set_facecolor(theme.color("card_bg"))

        if not rows:
            # The card can be briefly visible with nothing to draw (the
            # underfilled note hides it, but a redraw may still land
            # while it is up) - a sentence, not a crash on max() of an
            # empty sequence.
            axes.axis("off")
            axes.text(
                0.5, 0.5, "Pick two finished cycles to compare.",
                ha="center", va="center",
                color=theme.color("text_secondary"),
                fontsize=_font("body"), transform=axes.transAxes,
            )
            return

        positions = list(range(len(rows)))
        offset = 0.26          # how far each bar sits from its group's centre
        bar_width = 0.24

        # Three series around each centre: -offset, 0, +offset. The
        # colours come from _budget_colour() - the same info/warning/
        # success every other budget bar and wedge in the app wears.
        for index, budget in enumerate(reports.BUDGET_KEYS):
            shift = (index - 1) * offset
            axes.bar([p + shift for p in positions],
                     [row["budgets"][budget] for row in rows],
                     bar_width, label=BUDGET_LABELS[budget],
                     color=_budget_colour(budget))

        # Headroom for the two stacked notes above each group. The
        # comparison chart reserves 1.28 for its SINGLE line at 1.04;
        # a second line at 1.20 needs more, and 1.40 still leaves the
        # notes clear of the top edge even at the minimum chart height
        # (where a 12 px line is at its tallest in data units).
        tallest = max(max(row["budgets"][budget]
                          for budget in reports.BUDGET_KEYS)
                      for row in rows)
        axes.set_ylim(0, tallest * 1.40)

        for index, row in enumerate(rows):
            group_top = max(row["budgets"][budget]
                            for budget in reports.BUDGET_KEYS)
            axes.text(index, group_top * 1.04,
                      f"spent Rs. {row['spent']:,}",
                      ha="center", va="bottom",
                      color=theme.color("text"),
                      fontsize=_font("caption"), fontweight="bold")

            # The same saved/overspent wording the History cards use,
            # so the two tabs tell the verdict identically.
            saved = row["saved"]
            verdict = (f"saved Rs. {saved:,}" if saved >= 0
                       else f"OVERSPENT Rs. {-saved:,}")
            axes.text(index, group_top * 1.20, verdict,
                      ha="center", va="bottom",
                      color=theme.color("success" if saved >= 0 else "danger"),
                      fontsize=_font("caption"), fontweight="bold")

        # Name over window, on two lines - the cycle's full identity.
        axes.set_xticks(positions)
        axes.set_xticklabels(
            [f"{row['label']}\n{row['range']}" for row in rows])

        # Fixed margins rather than tight_layout(): the legend sits in
        # the band this reserves above the axes (same as the comparison
        # chart), and the bottom is a touch deeper because the x labels
        # are two lines tall.
        figure.subplots_adjust(left=0.11, right=0.97, top=0.82, bottom=0.17)

        self._style_axes(axes, grid_axis="y")
        axes.yaxis.set_major_formatter(MONEY)
        axes.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3,
                    frameon=True, framealpha=1.0, fontsize=_font("caption"))

    # -- shared chart styling ---------------------------------------------

    def _style_axes(self, axes, grid_axis: str) -> None:
        """Apply the palette to everything the drawing helpers did not set.

        Kept in one place so the two bar charts cannot drift apart: grid,
        frame, ticks and labels all come from theme.py here, on every
        single draw.
        """
        colour = theme.color("text_secondary")
        axes.tick_params(axis="both", colors=colour,
                         labelsize=_font("caption"))

        axes.set_axisbelow(True)      # bars sit ON the grid, not under it
        # "grid", not "border" - see the comment on rcParams above. The
        # width stays at 0.8 pt (about one pixel at 96 dpi): the line was
        # too COLOURFUL, not too thick, and the same width keeps the two
        # bar charts identical in both modes. redrawn from theme.py on
        # every draw, so a theme flip re-colours it with everything else.
        axes.grid(axis=grid_axis, color=theme.color("grid"), linewidth=0.8)

        for side in ("bottom", "left"):
            axes.spines[side].set_visible(True)
            axes.spines[side].set_color(theme.color("border"))
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def _paint_segment_seams(self, control) -> None:
        """Hide the hairline that CustomTkinter leaves between segments.

        A CTkSegmentedButton is not one widget but a ROW of separate
        CTkButtons, each with its own Tk canvas. Tk paints a canvas's
        BACKGROUND wherever the widget's rounded rectangle does not
        reach - and that includes the single pixel column where two
        neighbouring values meet. So the "grid line" between
        All|Needs|Wants|Savings, and between
        Spending|Plan vs Actual|History|Compare, is nobody's deliberate
        stroke: it is the SEAM between two canvases showing through.

        CustomTkinter seeds that background from ITS OWN stock theme.
        The segments are built inside CTkSegmentedButton.__init__,
        before we ever pass fg_color, so _detect_color_of_master()
        reads the stock value - CTkSegmentedButton's default fg_color,
        a mid grey in light mode and "gray29" in dark. Worse,
        configure(fg_color=...) only propagates border_color to the
        segments (ctk_segmented_button.py), never bg_color, so after a
        dark->light toggle the seam keeps a stale DARK card_bg painted
        on a light screen.

        The fix is to seed it ourselves from the bar's own fg_color
        (card_bg for both of these controls), which is exactly the
        colour of the gap around each value - so the seam becomes
        invisible instead of off-palette. configure(bg_color=...) sets
        _bg_color AND calls _draw(), so it survives every later
        repaint, hover and resize.
        """
        # Find the segmented bar. It may BE the control (the picker) or
        # sit one level inside it (the tab view's bar).
        #
        # control.winfo_children() is NOT good enough for the second
        # case: CTkTabview OVERRIDES winfo_children() and deliberately
        # strips its segmented button out of the list, because it
        # treats the bar as part of itself rather than as a child.
        # Calling tkinter.Frame.winfo_children() unbound gets Tk's real
        # child list back, so we still touch no private attribute.
        bars = []
        if isinstance(control, ctk.CTkSegmentedButton):
            bars.append(control)
        for child in tk.Frame.winfo_children(control):
            if isinstance(child, ctk.CTkSegmentedButton):
                bars.append(child)

        for bar in bars:
            # The bar's fg_color is what the gap around each value is
            # painted with. refresh_theme() has already configured it by
            # now, so this is a plain string rather than CustomTkinter's
            # stock [light, dark] pair.
            colour = bar.cget("fg_color")
            if not isinstance(colour, str):
                continue
            for segment in tk.Frame.winfo_children(bar):
                if isinstance(segment, ctk.CTkButton):
                    segment.configure(bg_color=colour)

    def refresh_theme(self) -> None:
        """Re-read every colour from theme.py and repaint this screen.

        main.py calls this each time the dark/light switch is flipped, so
        EVERY widget built in _build() is configured here - and so are
        all four figures: _draw_all() rebuilds them, and the first thing
        each draw does is push the new palette into matplotlib's
        rcParams. That is the whole mechanism behind charts that follow
        the theme.
        """
        self.configure(fg_color=theme.color("bg"))
        self._title.configure(text_color=theme.color("text"))
        self._subtitle.configure(text_color=theme.color("text_secondary"))
        self._picker_caption.configure(text_color=theme.color("text_secondary"))

        # Budget picker. CustomTkinter draws each value as its own
        # button: fg_color becomes that button's BORDER, *_color its
        # face. Every choice below differs from its neighbour in both
        # palettes (surface -> border is darker in light mode and lighter
        # in dark mode, which is all hover feedback needs to be visible).
        self._picker.configure(
            fg_color=theme.color("card_bg"),            # the ring around each value
            selected_color=theme.color("accent"),       # the chosen value
            selected_hover_color=theme.color("accent_hover"),
            unselected_color=theme.color("surface"),
            unselected_hover_color=theme.color("border"),
            text_color=theme.color("text"),
            text_color_disabled=theme.color("text_secondary"),
        )
        # ...and close the hairline CustomTkinter leaves between the four
        # values (see _paint_segment_seams). fg_color must be set first:
        # the helper reads it back to decide what to paint the seam with.
        self._paint_segment_seams(self._picker)

        # The tab view. CTkTabview draws two things that carry colour:
        # the panel behind the tabs (fg_color / border_*) and the tab BAR,
        # which is a CTkSegmentedButton wearing segmented_button_* - so it
        # is themed exactly like the picker above it, and text_color is
        # the tab titles' ink. Passing them together in one configure()
        # is safe: CTkTabview.configure() handles each of those keys
        # itself and forwards the rest, leaving require_redraw=True so
        # CTkBaseClass.configure() calls _draw(), which repaints the
        # panel AND each tab's frame from the new _fg_color.
        self._tabs.configure(
            fg_color=theme.color("bg"),
            border_color=theme.color("border"),
            segmented_button_fg_color=theme.color("card_bg"),
            segmented_button_selected_color=theme.color("accent"),
            segmented_button_selected_hover_color=theme.color("accent_hover"),
            segmented_button_unselected_color=theme.color("surface"),
            segmented_button_unselected_hover_color=theme.color("border"),
            segmented_button_font=theme.font("caption"),
            text_color=theme.color("text"),
            text_color_disabled=theme.color("text_secondary"),
        )
        # ...and the same hairline between the tab titles - "Spending",
        # "Plan vs Actual", "History" and "Compare" - which are one
        # segmented bar inside the tab view.
        self._paint_segment_seams(self._tabs)

        # The four statistic tiles.
        for tile in self._stats:
            tile["card"].configure(
                fg_color=theme.color("card_bg"),
                border_color=theme.color("border"),
            )
            tile["caption"].configure(text_color=theme.color("text_secondary"))
            tile["detail"].configure(text_color=theme.color("text_secondary"))
        # Value colours are state-driven, so re-derive them rather than
        # paint them all the same (the top category wears its budget's
        # accent, the remaining balance goes green only when positive).
        self._apply_text()

        # The four chart cards (their captions only - the figures are
        # repainted by _draw_all() below).
        for key, parts in self._boxes.items():
            parts["card"].configure(
                fg_color=theme.color("card_bg"),
                border_color=theme.color("border"),
            )
            parts["caption"].configure(text_color=theme.color("text_secondary"))

        # The empty panel.
        self._empty_card.configure(
            fg_color=theme.color("card_bg"),
            border_color=theme.color("border"),
        )
        self._empty_headline.configure(text_color=theme.color("text"))
        self._empty_body.configure(text_color=theme.color("text_secondary"))

        # The History tab (Phase 8.3): its scrollbar, its footnote, and
        # every colour inside the rows - which are REBUILT rather than
        # repainted, because their verdict colours are state-derived
        # (saved = success, overspent = danger) exactly like the tiles'
        # values above.
        #
        # fg_color="transparent" is NOT redundant: CustomTkinter paints
        # the list's canvas and inner frame from _parent_frame's
        # bg_color, and only a configure(fg_color=...) call copies that
        # value across (ctk_scrollable_frame.py, the fg_color branch).
        # The tabview's own re-theme above updates _parent_frame's
        # bg_color, but without this line the copy never happens, so the
        # empty area below the cards keeps the PREVIOUS mode's colour
        # after a flip (white block in dark mode, black in light). The
        # other three screens' lists pass fg_color="transparent" here
        # for exactly this reason.
        self._history_list.configure(
            fg_color="transparent",
            scrollbar_fg_color=theme.color("surface"),
            scrollbar_button_color=theme.color("text_secondary"),
            scrollbar_button_hover_color=theme.color("text"),
        )
        self._history_note.configure(text_color=theme.color("text_secondary"))
        self._apply_history()

        # The Compare tab (Phase 8.4): the two dropdowns take the same
        # palette Settings gives its day menu, the static captions take
        # the theme's ink, and then _apply_compare() re-derives every
        # DATA-driven piece (which cycles are selected, the salary line
        # and its footnote) - the same order as _apply_history() above,
        # for the same reason: their text quotes figures that a flip
        # does not change but a reload might.
        self._compare_caption.configure(
            text_color=theme.color("text_secondary"))
        self._compare_vs.configure(text_color=theme.color("text_secondary"))
        for menu in (self._compare_menu_a, self._compare_menu_b):
            menu.configure(
                fg_color=theme.color("surface"),
                button_color=theme.color("border"),
                button_hover_color=theme.color("accent_soft"),
                text_color=theme.color("text"),
                text_color_disabled=theme.color("text_secondary"),
                dropdown_fg_color=theme.color("card_bg"),
                dropdown_hover_color=theme.color("border"),
                dropdown_text_color=theme.color("text"),
            )
        self._compare_salary.configure(
            text_color=theme.color("text_secondary"))
        self._compare_empty_headline.configure(
            text_color=theme.color("text"))
        self._compare_empty_body.configure(
            text_color=theme.color("text_secondary"))
        self._apply_compare()

        # Finally, repaint the charts themselves in the new palette.
        self._draw_all()
