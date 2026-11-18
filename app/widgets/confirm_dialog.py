"""
confirm_dialog.py - the shared "are you sure?" box (Phase 5).

WHY IT LIVES HERE
  Phase 4 built a confirmation dialog inside categories_screen.py because
  it was the only screen that needed one. Phase 5's Fixed Expenses screen
  needs exactly the same box before it deletes anything, and copying a
  ~120 line dialog into a second file would be the kind of duplication
  that rots. So the class moved out of the screen and into
  app/widgets/ - the placeholder package Phase 1 left for shared widgets.

  Both screens now do:

      from app.widgets.confirm_dialog import ConfirmDialog

  and pass a message plus a callback. The dialog knows nothing about
  categories or fixed expenses; the CALLER builds the sentence, which is
  what keeps it reusable.

HOW IT IS USED
  ConfirmDialog(
      self,                                   # any widget; used to find
      title="Confirm delete",                 #   the window to centre on
      message="Delete X?\n\nThis cannot be undone.",
      on_confirm=lambda: self._do_the_delete(),
  )
  The dialog closes ITSELF first and only then runs `on_confirm`, so the
  caller's list rebuild never happens underneath a live modal window.
  Keep a reference to it (the screens store it on self) so it cannot be
  garbage-collected while open.

THEMING
  It colours itself once, at construction, from the active palette. It
  needs no refresh_theme(): while it holds the input grab the sidebar's
  dark/light switch cannot be clicked, so the palette cannot change
  underneath it.
"""

import customtkinter as ctk

from app.core import theme

# Button size for this dialog, in PIXELS. Same precedent as the Settings
# screen's input widths and main.py's sidebar width: control dimensions
# are not colours/fonts/spacing/radius, so they do not belong in theme.py.
DIALOG_BUTTON_W = 136
DIALOG_BUTTON_H = 32


class ConfirmDialog(ctk.CTkToplevel):
    """Modal yes/no box shown before anything is deleted."""

    def __init__(self, master, *, title: str, message: str, on_confirm) -> None:
        super().__init__(master)
        self._on_confirm = on_confirm
        self._grabbed = False

        self.title(title)
        self.transient(master.winfo_toplevel())  # stay above our own window
        self.resizable(False, False)
        self.configure(fg_color=theme.color("bg"))

        pad = theme.spacing("lg")

        # The sentence. wraplength keeps it a paragraph, not one long line.
        label = ctk.CTkLabel(
            self, text=message,
            font=theme.font("body"), text_color=theme.color("text"),
            justify="left", anchor="w", wraplength=360,
        )
        label.grid(
            row=0, column=0, columnspan=2, sticky="ew",
            padx=pad, pady=(pad, theme.spacing("md")),
        )
        # Cancel and the destructive action sit side by side along the
        # bottom, each in its own column so they right-align as a pair.
        self.grid_columnconfigure(1, weight=1)

        cancel = ctk.CTkButton(
            self, text="Cancel",
            width=DIALOG_BUTTON_W, height=DIALOG_BUTTON_H,
            corner_radius=theme.radius("sm"), font=theme.font("button"),
            fg_color=theme.color("surface"),
            hover_color=theme.color("border"),
            text_color=theme.color("text"),
            command=self._close,
        )
        cancel.grid(
            row=1, column=0, sticky="e",
            padx=(pad, theme.spacing("sm")), pady=(0, pad),
        )

        # The confirm button is always styled as "danger"; the CALLER
        # chooses its label ("Delete", "Remove", ...).
        confirm = ctk.CTkButton(
            self, text="Delete",
            width=DIALOG_BUTTON_W, height=DIALOG_BUTTON_H,
            corner_radius=theme.radius("sm"), font=theme.font("button"),
            fg_color=theme.color("danger"),
            hover_color=theme.color("danger_hover"),
            text_color=theme.color("text_on_danger"),
            command=self._confirm,
        )
        confirm.grid(
            row=1, column=1, sticky="e",
            padx=(0, pad), pady=(0, pad),
        )

        # Keyboard shortcuts, because a confirm box should not force the
        # mouse: Enter confirms, Escape backs out.
        self.bind("<Return>", lambda _e: self._confirm())
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)  # the title-bar X

        # CTkToplevel withdraws the window while it repaints the Windows
        # titlebar colour, then deiconifies on a later event-loop tick.
        # Deiconify now so the dialog is on screen (and grab-able)
        # straight away instead of a tick later.
        self.deiconify()
        self.update_idletasks()
        self._center_over(master)
        self._grab()

    # -- modality -----------------------------------------------------------

    def _grab(self) -> None:
        """Take the input grab so clicks behind the dialog are ignored.

        grab_set() can fail if the window is not on screen yet; the
        dialog then simply behaves as a non-modal box rather than
        crashing the click that opened it.
        """
        try:
            self.grab_set()
            self._grabbed = True
        except Exception:  # TclError, before the window is viewable
            self._grabbed = False
        self.focus_force()

    def _center_over(self, master) -> None:
        """Place the dialog in the middle of the window it belongs to."""
        parent = master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # -- closing ------------------------------------------------------------

    def _close(self) -> None:
        """Dismiss without doing anything (Cancel / Escape / X)."""
        if self._grabbed:
            try:
                self.grab_release()
            except Exception:  # TclError if the grab is already gone
                pass
        self.destroy()

    def _confirm(self) -> None:
        """Dismiss first, THEN run the caller's action - so the dialog is
        never around while the list rebuilds underneath it."""
        callback = self._on_confirm
        self._close()
        callback()
