# Budget Tracker — project instructions

Python/CustomTkinter desktop app. Venv: `.venv` (Python 3.14). Run scripts with
`.venv\Scripts\python.exe`.

## Hard rules

- **Never edit `main.py`.** It owns the shell, sidebar, screen switching and the
  theme toggle. Screens are added/changed only inside `app/ui/`.
- **Every colour, font, spacing and corner radius comes from `app/core/theme.py`.**
  Nothing hardcoded in a screen. If a value is missing, add it to *both* LIGHT and
  DARK dicts (an import-time guard fails the app if they drift apart) and report it.
- **Every screen implements `refresh_theme()`** and must recolour *every* widget it
  creates — main.py walks all screens on each dark/light flip.
- **Stay inside the requested phase.** No categories, expense entry or database work
  unless the prompt asks for it.
- Comment code clearly; the user reads every file.
- Final reports must state: files changed, new theme.py values, and an explicit
  confirmation of each requirement in the prompt.

## Verification (reuse — do not rebuild)

Tests and screenshot scripts live in `C:\Users\diese\AppData\Local\Temp\opencode\`
(outside the project, so they never pollute it):

- `phase3_test.py` — 74-check suite for settings/validation/colours
- `balance_capture.py` + `balance_sheet.ps1` — 6-panel banner contact sheet
- `contrast_pick.py`, `measure_swap.py` — WCAG contrast measurement

Screenshots use ctypes `PrintWindow` → BMP → PowerShell `System.Drawing` → PNG.
**Pillow is not installed and should not be added** to the venv or requirements.txt.

## Resume

When the user types **`resume`** (or asks where we left off):

1. Read `PROGRESS.md` in the project root.
2. Reply with a short summary of where we are (a few lines).
3. **STOP.** Do not edit, create or delete any file, and do not run tests,
   screenshots or exploratory commands. Loading memory is read-only — wait
   for the user's next prompt before doing anything at all.

Do not re-explore the repo or re-read old session history first.
