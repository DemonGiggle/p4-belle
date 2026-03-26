"""Shared Rich color/style constants for p5."""

# File state colors
MODIFIED  = "yellow"
ADDED     = "green"
DELETED   = "red"
UNTRACKED = "dim white"
RENAMED   = "cyan"

# Diff colors
DIFF_ADD    = "bright_green"
DIFF_DEL    = "bright_red"
DIFF_HUNK   = "cyan"
DIFF_HEADER = "bold white"

# Changelist / log colors
CL_NUM  = "bold blue"
DATE    = "dim"
AUTHOR  = "yellow"
DESC    = "white"
BRANCH  = "bold cyan"

# Sync colors
SYNC_UPDATED = "yellow"
SYNC_ADDED   = "green"
SYNC_DELETED = "red"

# Section headers
SECTION = "bold white"

# Status letter → color mapping
ACTION_COLOR: dict[str, str] = {
    "edit":       MODIFIED,
    "add":        ADDED,
    "delete":     DELETED,
    "branch":     ADDED,
    "integrate":  RENAMED,
    "move/add":   RENAMED,
    "move/delete": DELETED,
}

STATE_LETTER: dict[str, str] = {
    "edit":        "M",
    "add":         "A",
    "delete":      "D",
    "branch":      "A",
    "integrate":   "I",
    "move/add":    "R",
    "move/delete": "D",
}
