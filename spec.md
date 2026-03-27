# p5 — Specification

**p5** is a Perforce CLI wrapper that replaces `p4` with a git-like UX: relative paths everywhere, colored output, and interactive terminal UIs for browsing changelists and workspaces.

---

## Table of Contents

1. [Goals & Design Principles](#goals--design-principles)
2. [Installation](#installation)
3. [Architecture](#architecture)
4. [Color Scheme](#color-scheme)
5. [Commands](#commands)
   - [status](#status)
   - [diff](#diff)
   - [delete](#delete)
   - [sync](#sync)
   - [change](#change)
   - [submit](#submit)
   - [filelog](#filelog)
   - [changes (TUI)](#changes-tui)
   - [ws (TUI)](#ws-tui)
   - [completion](#completion)

---

## Goals & Design Principles

| Principle | Detail |
|---|---|
| **Relative paths** | All input and output use paths relative to the client root. Absolute depot paths (`//depot/...`) are accepted as input but never shown. |
| **Git-familiar UX** | Command names, output format, and keybindings mirror git where natural. |
| **Colored by default** | Every command uses semantic color: green = added, yellow = modified, red = deleted. |
| **Interactive TUIs** | `changes` and `ws` launch full-screen terminal UIs. All other commands are plain CLI. |
| **Thread-safe I/O** | TUI commands run all p4 subprocess calls on background threads; the UI never blocks. |
| **Graceful errors** | All `P4Error` exceptions are caught and printed as `[red]error:[/red] message`. Missing results show a friendly empty-state message. |
| **Confirmation on risk** | `submit` asks for confirmation before writing to the depot (skippable with `-y`). |

---

## Installation

**Requirements**: Python 3.9+, `p4` CLI configured (P4PORT / P4USER / P4CLIENT set).

```sh
git clone <repo>
cd p4-belle
python3 -m pip install -e .
```

This installs `p5` to `~/.local/bin/p5`. Add to PATH if needed:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

**Dependencies** (declared in `pyproject.toml`):

| Package | Purpose |
|---|---|
| `click` | CLI argument parsing and command groups |
| `rich` | Terminal colors, tables, and markup rendering |
| `textual` | Full-screen TUI framework (required for `changes` and `ws`) |

---

## Architecture

```
src/p5/
├── cli.py               — click group, registers all commands (incl. completion)
├── p4.py                — subprocess wrapper (run_p4, run_p4_tagged, P4Error)
├── workspace.py         — path resolution (depot ↔ local ↔ relative)
├── theme.py             — shared color/style constants
├── completion.py        — shell completion helpers (opened files, CLs, depot paths)
├── commands/
│   ├── status.py
│   ├── diff.py
│   ├── delete.py
│   ├── sync.py
│   ├── change.py
│   ├── submit.py
│   ├── filelog.py
│   ├── changes.py       — launches tui/changes_app.py
│   └── ws.py            — launches tui/ws_app.py (or prints table with --no-tui)
└── tui/
    ├── change_app.py    — Textual app for managing default changelist
    ├── changes_app.py   — Textual app for browsing changelists
    └── ws_app.py        — Textual app for workspace selection
```

### `p4.py` — subprocess wrapper

```python
run_p4(args, *, cwd=None, check=True) -> str
run_p4_tagged(args, *, cwd=None) -> list[dict]
```

- `run_p4` executes `p4 <args>` and returns stdout. Raises `P4Error` on non-zero exit.
- `run_p4_tagged` adds `-ztag` and parses the key/value output into a list of dicts.
  Indexed keys (`depotFile0`, `depotFile1`, …) are automatically collapsed into lists under the base key (`depotFile`).

### `workspace.py` — path resolution

Auto-detects workspace on first use via `p4 info` and `p4 client -o`. Results are cached.

| Function | Input | Output |
|---|---|---|
| `local_to_depot(path)` | relative or absolute local path | `//depot/...` depot path |
| `depot_to_rel(path)` | `//depot/...` depot path | `src/foo.cpp` relative path |
| `local_to_rel(path)` | `/abs/path/src/foo.cpp` | `src/foo.cpp` relative path |
| `any_to_rel(path)` | any of the above | `src/foo.cpp` relative path |

Depot paths (starting with `//`) pass through `local_to_depot` unchanged.

---

## Color Scheme

All colors are defined in `theme.py` as Rich markup strings.

### File State Colors

| State | Letter | Color |
|---|---|---|
| Modified (edit) | `M` | yellow |
| Added (add/branch) | `A` | green |
| Deleted (delete) | `D` | red |
| Integrated | `I` | cyan |
| Moved | `R` / `D` | cyan / red |
| Untracked | `?` | dim white |

### Diff Colors

| Element | Color | Notes |
|---|---|---|
| `+` prefix | bold bright_green | |
| `-` prefix | bold bright_red | |
| Added line background | `on #1a3a1a` | dark green tint — lets syntax colors show through |
| Removed line background | `on #3a1a1a` | dark red tint — lets syntax colors show through |
| Context lines | dim | slightly dimmed, still syntax-highlighted |
| `@@` hunk header | bold cyan | |
| File header | bold white | |

### Syntax Highlight Token Colors (VS Code Dark+ theme)

Applied to code content within diff lines using Pygments. Lexer is auto-detected from the file extension.

| Token type | Color |
|---|---|
| Keywords (`if`, `return`, …) | bold `#569CD6` (blue) |
| Types / classes | `#4EC9B0` (teal) |
| Function names | `#DCDCAA` (yellow) |
| Strings | `#CE9178` (warm orange) |
| Numbers | `#B5CEA8` (light green) |
| Comments | italic `#6A9955` (green) |
| Operators / punctuation | `#D4D4D4` (light gray) |
| Decorators | `#C586C0` (pink/purple) |
| Identifiers / names | `#9CDCFE` (light blue) |

### Metadata Colors

| Element | Color |
|---|---|
| Changelist number | bold blue |
| Date | dim |
| Author / user | yellow |
| Depot branch / revision | bold cyan |
| Section headers | bold white |

---

## Commands

All commands accept `-h` / `--help`.

---

### `status`

Show pending changes in the current directory grouped by changelist — like `git status`.

```
p5 status [PATH] [-a]
```

| Option | Default | Description |
|---|---|---|
| `PATH` | current directory | Local or depot path to check |
| `-a, --all` | off | Show entire depot (`//...`) |

**Output sections** (only shown when non-empty):

```
Changes to be submitted (default changelist):
  M  src/auth/login.cpp
  A  src/auth/token.h

Other pending changelists:
  CL 123450
    M  src/net/socket.cpp

Local changes not opened in p4:
  ?  src/scratch.cpp
```

**Footer hint**: After the file list, status always prints:
```
  use p4 edit <file> to open for edit, p4 add <file> to mark new files,
  p5 delete <file> to mark for delete
```
This is intentional — `p5 edit` and `p5 add` are not provided because they add no meaningful UX improvement over `p4 edit`/`p4 add` directly. `p5 delete` is the exception because it adds a confirmation prompt.

**Implementation**:
- `p4 opened <depot_path>/...` → groups by changelist (scoped to current directory by default)
- `p4 reconcile -n -e -a -d <depot_path>/...` → untracked / local-only changes
- Empty state: prints `nothing to commit, working tree clean`

---

### `diff`

Show a colored unified diff of opened files.

```
p5 diff [FILES...] [-c CL]
```

| Option | Default | Description |
|---|---|---|
| `FILES` | none (all opened) | Files to diff; accepts relative paths |
| `-c CL` | default changelist | Diff files in a specific changelist |

**Output**:

```
─── diff src/auth/login.cpp  (#41 → working copy) ───
--- //depot/project/src/auth/login.cpp  (dim)
+++ //depot/project/src/auth/login.cpp  (dim)
@@ -10,6 +10,7 @@ int authenticate(User& u) {   ← cyan bold
     validate(u);                                     ← dim context
+    log_attempt(u.name);                             ← green bg + syntax
-    old_log(u);                                      ← red bg + syntax
     return check_token(u);
```

**Implementation**: `p4 diff -du`, parses `==== path#rev` headers to track current file and lexer.

---

### `delete`

Mark file(s) for delete, with a confirmation prompt before calling `p4 delete`.

```
p5 delete FILES... [-c CL] [-y]
```

| Option | Description |
|---|---|
| `FILES` | One or more paths (relative or absolute) |
| `-c CL` | Add to a specific changelist instead of default |
| `-y` | Skip confirmation prompt |

**Output**:

```
Files to be deleted:
  D  src/auth/old_helper.cpp

Mark these files for delete? [y/N]: y

  deleted  src/auth/old_helper.cpp
```

**Rationale**: `p5 edit` and `p5 add` are intentionally absent — they wrap `p4 edit`/`p4 add` with minimal UX gain. Delete is the exception because it is irreversible enough to warrant a confirmation step.

**Implementation**: Resolves relative paths to depot paths, shows the list, confirms, then calls `p4 delete [-c CL] <depot_paths>`. Parses "opened for delete" lines for display; other lines shown dimmed.

---

### `sync`

Sync workspace to head with a summary.

```
p5 sync [PATH] [-f] [-n] [-a]
```

| Option | Default | Description |
|---|---|---|
| `PATH` | current directory | Local or depot path to sync recursively |
| `-f` | off | Force resync |
| `-n` | off | Dry run (preview only) |
| `-a, --all` | off | Sync entire depot (`//...`) |

**Output**:

```
Syncing to head...

  updated   src/auth/login.cpp     #42     ← yellow
  added     src/net/retry.cpp      #1      ← green
  deleted   src/net/old_proto.cpp          ← red

  2 updated, 1 added, 1 deleted
```

**Implementation**: `p4 sync [flags] <path>`. Each output line is matched against patterns:
- `#N - updating` → updated
- `#N - added as` → added
- `#N - deleted as` → deleted
- `up-to-date` anywhere → shows "already up-to-date"

---

### `change`

Interactive TUI to manage files in the default changelist — select, group into a new CL, or move to an existing one.

```
p5 change [CL_NUMBER] [-d]
```

| Option | Description |
|---|---|
| *(no args)* | Launch interactive TUI for the default changelist |
| `CL_NUMBER` | Opens that changelist in `$EDITOR` for editing |
| `-d` | Delete an empty changelist (requires `CL_NUMBER`) |

**TUI layout** (no args):

```
p5 change — manage default changelist
 ── Selected (2) ──
   ✓  M  src/auth/login.cpp
   ✓  A  src/auth/token.h
 ── Default changelist (3) ──
      M  src/net/socket.cpp
   ▶  A  src/ui/main.cpp
      M  src/ui/helper.h
 [space: toggle] [a: all] [d: none] [n: new CL] [m: move] [/: filter] [q: quit]
```

**Keybindings**:

| Key | Action |
|---|---|
| `space` | Toggle selection of file under cursor |
| `a` | Select all files (filtered) |
| `d` | Deselect all files (filtered) |
| `n` | Create new CL — opens modal with description input and file preview. Files are moved via `p4 change -i` + `p4 reopen -c <new_cl>` |
| `m` | Move to existing CL — opens modal listing pending CLs + default. Uses `p4 reopen -c <target>` |
| `/` | Filter files by path substring |
| `j/k` or `↑/↓` | Move cursor (skips section headers) |
| `Enter` | Toggle selection (same as space) |
| `q` | Quit |

**Modals**:

- **New CL screen**: text input for description, file preview, creates CL via `p4 change -i` with minimal spec, then moves files with `p4 reopen -c <cl>`.
- **CL selector screen**: lists current user's pending CLs (via `p4 changes -s pending -u <user>`) plus "default". Enter confirms and moves files.

**Implementation**: With a CL number, passes directly to `p4 change` via `subprocess.run` (not captured) to preserve interactive editor behavior. Delete uses `p4 change -d CL`.

---

### `submit`

Submit a pending changelist to the depot.

```
p5 submit [-c CL] [-d DESCRIPTION] [-y]
```

| Option | Default | Description |
|---|---|---|
| `-c CL` | default | Submit a specific numbered changelist |
| `-d TEXT` | none | Inline description (skips editor) |
| `-y` | off | Skip confirmation prompt |

**UX flow**:
1. Shows files in the target CL (using `p4 opened -c CL`)
2. Prompts "Submit these changes? [y/N]" (skipped with `-y`)
3. If `-d` provided: submits with `p4 submit -d TEXT`
4. Otherwise: opens `$EDITOR` for description via `p4 submit`

**Output on success**:

```
  submitted  CL 123457     ← green label + bold blue CL number
```

**Implementation**: Regex `r"Change (\d+) submitted"` extracts the submitted CL number from p4 output.

---

### `filelog`

Show revision history of a single file in git-log style.

```
p5 filelog FILE [-n MAX]
```

| Option | Default | Description |
|---|---|---|
| `FILE` | required | File to show history for |
| `-n MAX` | 20 | Maximum revisions to show |

**Output**:

```
src/auth/login.cpp

● #42  CL 123456  2026-03-25  gigo    [edit]
│  Fix null pointer in auth module
│
● #41  CL 123450  2026-03-20  alice   [edit]
│  Add retry logic
│
● #40  CL 123440  2026-03-15  bob     [add]
   Initial implementation
```

| Element | Color |
|---|---|
| `●` bullet + CL number | bold blue |
| `#N` revision | bold cyan |
| Date | dim |
| Author | yellow |
| `[action]` | dim + action color (e.g. dim green for add) |
| `│` connector | dim |
| Description | dim, max 2 lines per revision |

**Implementation**: `p4 filelog -m MAX <depot_path>` with `-ztag`. Indexed fields (`rev0`, `change0`, `time0`, …) are automatically collapsed into lists.

---

### `changes` (TUI)

Interactive full-screen browser for submitted (or pending) changelists.

```
p5 changes [-u USER] [-m MAX] [-s STATUS]
```

| Option | Default | Description |
|---|---|---|
| `-u USER` | all users | Filter by user |
| `-m MAX` | 50 | Maximum CLs to load |
| `-s STATUS` | submitted | `submitted`, `pending`, `shelved`, or `all` |

#### Layout

```
 p5 changes — Perforce changelist browser
 ────────────────────────────────────────────────────────────────
    CL        Date        Author        Description
 ────────────────────────────────────────────────────────────────
  123456  2026-03-25  gigo          Fix null pointer in auth
  123455  2026-03-24  alice         Add retry logic to network
  123454  2026-03-23  bob           Update third-party deps
 ────────────────────────────────────────────────────────────────
 [j/k: navigate]  [Enter: expand]  [/: filter]  [r: reload]  [q: quit]
```

#### Keybindings

| Key | Action |
|---|---|
| `j` / `↓` | Move cursor down (or scroll diff if detail open) |
| `k` / `↑` | Move cursor up (or scroll diff if detail open) |
| `Enter` | Expand selected CL → show files + colored diff |
| `Escape` | Close detail view / cancel filter |
| `/` | Enter filter mode (search by CL, user, description) |
| `r` | Reload changelist from p4 |
| `q` | Quit |

#### Detail view (after pressing Enter)

```
CL 123456  2026-03-25  gigo
  Fix null pointer in auth module

Files:
  M  src/auth/login.cpp
  M  src/auth/session.h

Diff:
────────────────────────────────────────────
diff src/auth/login.cpp
--- src/auth/login.cpp  (dim)
+++ src/auth/login.cpp  (dim)
@@ -42,7 +42,7 @@ User::authenticate()    ← cyan
     if (!user) {                            ← dim, syntax
-        return user->token;                 ← red bg + syntax
+        return nullptr;                     ← green bg + syntax
     }
```

`Escape` returns to the list.

#### Filter mode

Press `/` to enter filter mode. The filter bar appears at the bottom:

```
Filter: auth_
```

- Type to narrow the list by CL number, user, or description
- `Enter` commits the filter (bar stays visible showing active query)
- `Escape` clears the filter and hides the bar
- While typing: `j`/`k` and `Enter` do **not** move the cursor or expand CLs

#### Data loading

- CL list: `p4 changes -l -m MAX -s STATUS [-u USER] //...`
- CL detail: `p4 describe -du CL` (submitted) or `p4 describe -du -S CL` (shelved/pending)
- File list: `p4 describe -s CL`
- All I/O runs on background threads (`@work(thread=True)`)
- Detail is loaded lazily when a CL is first expanded

#### Data model

```python
@dataclass
class ChangeRecord:
    cl: str
    date: str          # YYYY-MM-DD
    user: str
    description: str   # first line only, newlines collapsed
    status: str        # "submitted" | "pending" | "shelved"
    files: list[tuple[str, str]]  # [(action, rel_path), ...]
    diff: str          # raw p4 describe output
    loaded: bool       # True once files+diff have been fetched
```

---

### `ws` (TUI)

Interactive workspace selector — lists all your Perforce clients and switches between them.

```
p5 ws [-u USER] [--no-tui]
```

| Option | Default | Description |
|---|---|---|
| `-u USER` | current user (from `p4 info`) | List workspaces for a specific user |
| `--no-tui` | off | Print a plain table instead of launching the TUI |

#### Interactive TUI layout

```
 p5 ws — Perforce workspace selector
 ──────────────────────────────────────────────────────────────
 ◆ gigo-main                    (current)
   /home/gigo/workspace/main
   2026-03-25   build-server   Main integration workspace

   gigo-feature-x
   /home/gigo/workspace/feature-x
   2026-03-20   laptop         Feature branch workspace
 ──────────────────────────────────────────────────────────────
 2 workspaces  [Enter] switch  [/] filter  [r] reload  [q] quit
```

Each item is 3 lines:
1. `◆ NAME  (current)` — `◆` and name are bold green for the current workspace
2. `  /workspace/root` — dim
3. `  YYYY-MM-DD   hostname   description (truncated to 60 chars)` — dim date, yellow host

#### Keybindings

| Key | Action |
|---|---|
| `j` / `↓` | Move cursor down |
| `k` / `↑` | Move cursor up |
| `Enter` | Switch to selected workspace |
| `/` | Enter filter mode |
| `r` | Reload workspaces from p4 |
| `q` | Quit without switching |

#### Switching behavior

- `Enter` on the current workspace: shows "already active" in status bar, no-op.
- `Enter` on another workspace: runs `p4 set P4CLIENT=<name>`, which writes to `~/.p4enviro` and persists across all shells.
- On quit: if a switch occurred, prints `  switched to  WORKSPACE` to stdout.

#### Filter mode

Same behavior as `p5 changes`. Filters across workspace name, root path, host, and description.

#### Non-interactive mode (`--no-tui`)

Prints a Rich table:

```
  Workspace        Root                         Host           Last Access
  ◆ gigo-main      /home/gigo/workspace/main    build-server   2026-03-25
    gigo-feature   /home/gigo/workspace/feat    laptop         2026-03-20

  current:   gigo-main
  to switch: p5 ws  (interactive)  or  p4 set P4CLIENT=<name>
```

#### Data model

```python
@dataclass
class ClientRecord:
    name: str
    root: str
    host: str
    description: str
    access: str        # YYYY-MM-DD last access
    update: str        # YYYY-MM-DD last update
    is_current: bool   # True if matches p4 info clientName
```

Current workspace determined from `p4 info` → `clientName` field. User determined from `p4 info` → `userName` field (same call, no extra round-trip). Workspaces sorted: current first, then alphabetically.

---

---

### `completion`

Print shell completion setup instructions or install the hook directly.

```
p5 completion [SHELL] [--install]
```

| Option | Default | Description |
|---|---|---|
| `SHELL` | auto-detected from `$SHELL` | `bash`, `zsh`, or `fish` |
| `--install` | off | Append the completion hook to the shell profile and exit |

**Without `--install`**: prints the line to add to the shell profile and a reminder to `source` it.

**With `--install`**:
1. Resolves the profile path (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`)
2. Checks for `_P5_COMPLETE` in the file; skips if already present
3. Appends a `# p5 shell completion` comment block and the hook line
4. Prints the `source` command to activate immediately

**Implementation**: Uses Click's built-in `_P5_COMPLETE=<shell>_source` mechanism. Completers in `completion.py` are wrapped with `@_safe` which silently returns `[]` on any exception (e.g. when not inside a Perforce workspace).

**Completers registered per command**:

| Command | Argument | Completer |
|---|---|---|
| `diff` | `FILES` | `complete_opened_files` |
| `diff` | `-c` | `complete_pending_cls` |
| `delete` | `FILES` | `complete_opened_files` |
| `delete` | `-c` | `complete_pending_cls` |
| `filelog` | `FILE` | `complete_depot_path` |
| `sync` | `PATH` | `complete_depot_path` |
| `change` | `CL_NUMBER` | `complete_pending_cls` |
| `submit` | `-c` | `complete_pending_cls` |

---

## Known Limitations / Future Work

- `p5 change` and `p5 submit` (without `-d`) shell out to `p4` directly for editor support; they do not use the Rich/Textual UI.
- `p5 diff` does not support syntax highlighting — only the `p5 changes` detail view does (via Pygments).
- No support for `p4 shelve` / `p4 unshelve` yet.
- No support for streams or task streams.
