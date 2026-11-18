"""
text_rules.py - the gentle "capitalise the first letter" rule (Phase 6).

WHY THIS FILE EXISTS
  Two different places need the SAME behaviour on free text:

    * while the user is TYPING in a screen (instant feedback), and
    * when a record is STORED (so data is consistent no matter which
      screen - or future test, or future SQLite layer - wrote it).

  If each place had its own copy, "gentle" would slowly drift apart: one
  would end up title-casing, another would capitalise on submit only.
  One definition here keeps them identical.

WHAT "GENTLE" MEANS (the whole point of this rule)
  Capitalise the FIRST LETTER and change nothing else:

      "netflix"             -> "Netflix"
      "netflix and chill"   -> "Netflix and chill"   (NOT "Netflix And Chill")
      "FD"                  -> "FD"                  (already capital - untouched)
      "Spotify/Apple Music" -> "Spotify/Apple Music" (first letter already
                               upper - untouched, inner capitals untouched)
      ""                    -> ""

  So: never title-case, never lower-case, never touch anything past index
  0. An empty string stays empty (there is no first letter to fix).

  A lower-case-initial proper noun such as "iPhone" DOES get its first
  letter raised ("IPhone") - that is what "capitalise the first letter,
  leave the rest exactly as typed" means, and it is deliberate: guessing
  which words are brands would be a title-caser wearing a disguise.

RETROACTIVE? NO.
  cap_first() is applied to text as it is TYPED (see
  bind_gentle_capitalise) and to records as they are ADDED or EDITED.
  Nothing in the app ever rewrites what is already stored, and a name
  the user typed in an earlier phase is left exactly as it was until
  they edit it themselves.
"""

# ---------------------------------------------------------------------------
# 1. THE RULE ITSELF
# ---------------------------------------------------------------------------

def cap_first(text) -> str:
    """Return `text` with only its first character upper-cased.

    Accepts a str; anything else comes back unchanged (the holders pass
    through their own type checks first - this function never raises,
    it only applies the rule).

    Implementation note: only index 0 is touched. `"abc".upper()` would
    also raise the rest of the string ("ABC"), which is exactly the
    behaviour this rule exists to avoid, so it is deliberately NOT used.
    """
    if not isinstance(text, str) or not text:
        return text
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------
# 2. THE LIVE BINDING - apply the rule while the user types.
# ---------------------------------------------------------------------------

def bind_gentle_capitalise(entry) -> None:
    """Make a CTkEntry capitalise its first letter as the user types.

    HOW IT BEHAVES
      On every keystroke (and every paste) the entry's text is read,
      cap_first() is applied, and - if that changed anything - the entry
      is rewritten with the fixed text. The caret is saved first and put
      back afterwards, so typing at position 0 stays at position 0 and
      editing in the middle of the line does not jump to the end.

    WHY <KeyRelease> AND <<Paste>>
      A keystroke fires <KeyRelease>; Ctrl+V / right-click paste fire
      <<Paste>> instead, so binding only the first would let
      "netflix" arrive as-is through the clipboard. Both are bound with
      add=True so neither replaces the other (CTkEntry.bind forwards to
      its inner tk entry - see customtkinter/windows/widgets/ctk_entry.py).

    WHY IT DOES NOT RECURSE
      entry.set() rewrites the widget programmatically. Tk only fires
      keyboard / paste VIRTUAL EVENTS for real user input, so the
      rewrite never re-triggers this handler.

    The rule itself is idempotent - running cap_first() on text that is
    already fixed changes nothing - so calling it on every event is
    free: it does nothing 99% of the time.
    """
    def _apply_rule(_event=None):
        current = entry.get()
        fixed = cap_first(current)
        if fixed != current:
            # Remember where the caret was, rewrite, put it back. A
            # capital letter is the same length as the lower-case one
            # (the rare multi-character upper-case such as "ss" -> "SS"
            # only ever grows the text, and Tcl clamps an index that is
            # past the end, so the caret can never be lost either way).
            caret = entry.index("insert")
            entry.set(fixed)
            entry.icursor(caret)
        return None   # keep the event flowing - we never swallow input

    # add=True appends instead of replacing any binding the entry already
    # has (the screens also bind <Return> to submit the form).
    entry.bind("<KeyRelease>", _apply_rule, add=True)
    entry.bind("<<Paste>>", _apply_rule, add=True)
