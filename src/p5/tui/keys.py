"""Unified TUI key specification for all p5 interactive programs.

Covers the five TUIs: changes, change, ws, submit, diff (DiffApp).

Core keys are identical everywhere (breaking renames applied):
- j/down, k/up ........ move cursor, or scroll diff when detail open
- n / p ............... aliases for next/prev item (same as j/k in lists;
                        next/prev file in diff viewer)
- Enter / space ....... primary action (expand CL, toggle select, switch
                        workspace, select CL, next file in diff)
- Esc ................. back one level (close detail / cancel filter),
                        quit when already at top level
- / (slash) ........... filter list (by CL/user/desc, path, workspace, file)
- r ................... reload / refresh from p4
- w ................... toggle whitespace (ignored <-> significant)
- b ................... toggle view (unified <-> side-by-side)
- ctrl+f / ctrl+b ..... page down / page up in diff/detail views
- ? ................... show this help
- q ................... quit

App-specific keys (reserved everywhere else, no collisions):
- change: c=new CL (was n), x=revert (was r), a=select all, m=move
- submit: x=revert (was r), m=move, u=revert unchanged, e=edit desc, s=submit
- diff:   [/]=prev/next tab (category), n/p=prev/next file
- changes/ws have no app-specific single-letter keys beyond core.

Reserved (documented as no-op where not applicable):
- w/b in ws (no diffs to toggle)
"""

from __future__ import annotations

# Canonical key strings as used in textual Binding definitions.
NAV_DOWN_KEYS = "j,down,n"
NAV_UP_KEYS = "k,up,p"
PRIMARY_ENTER = "enter"
PRIMARY_SPACE = "space"
BACK = "escape"
FILTER = "slash"
RELOAD = "r"
REVERT = "x"
CREATE_CL = "c"
MOVE = "m"
SELECT_ALL = "a"
WHITESPACE = "w"
VIEW = "b"
PAGE_DOWN = "ctrl+f"
PAGE_UP = "ctrl+b"
HELP = "question_mark"
QUIT = "q"
EDIT_DESC = "e"
DO_SUBMIT = "s"
REVERT_UNCHANGED = "u"
TAB_PREV = "["
TAB_NEXT = "]"
NEXT_FILE = "n"
PREV_FILE = "p"

CORE_HELP = """core: j/k or n/p move · Enter/space primary · Esc back · / filter · r reload · w whitespace · b view · ctrl+f/b page · ? help · q quit"""

APP_HELP = {
    "changes": "changes: " + CORE_HELP,
    "change": "change: " + CORE_HELP + " · c new CL · m move · a all · x revert",
    "ws": "ws: j/k or n/p move · Enter/space switch · / filter · r reload · ? help · q quit (w/b reserved)",
    "submit": "submit: " + CORE_HELP + " · m move · x revert · u revert-unchanged · e edit desc · s submit",
    "diff": "diff: j/k scroll · n/p or Enter next/prev file · [/] tabs · w whitespace · b view · ctrl+f/b page · / filter · r reload · ? help · q quit",
}

UNIFIED_FOOTER_CORE = "[dim]j/k[/dim] move  [dim]n/p[/dim] next/prev  [dim]Enter/space[/dim] primary  [dim]Esc[/dim] back  [dim]/[/dim] filter  [dim]r[/dim] reload  [dim]?[/dim] help  [dim]q[/dim] quit"
