# p5

A Perforce CLI with git-like UX — relative paths, colored output, and interactive terminal UIs.

`p4` speaks in absolute depot paths. `p5` speaks like a human.

## Features

- **Relative paths** everywhere — output strips the depot/workspace root automatically
- **Colored output** — file states, diffs, and logs styled like `git`
- **Interactive `changes` browser** — navigate changelists with `j/k`, expand syntax-highlighted diffs with `Enter`
- **Interactive workspace selector** (`p5 ws`) — list all client workspaces and switch with `Enter`
- **Tab completion** — file paths, depot paths, and changelist numbers for bash, zsh, and fish
- Zero configuration — depot root is detected automatically from `p4 info`

## Requirements

- Python 3.9+
- Perforce `p4` client installed and configured (P4PORT, P4USER, P4CLIENT set)

## Install

```sh
git clone <this-repo>
cd p4-belle
python3 -m pip install -e .
```

The `p5` command will be installed to `~/.local/bin/p5`. Make sure that directory is on your `PATH`:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Shell Completion

The quickest way to install completion for your current shell:

```sh
p5 completion --install
```

This appends the completion hook to your shell profile (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`) and skips if already installed. Then reload:

```sh
source ~/.bashrc   # or ~/.zshrc, etc.
```

For a specific shell, or to see the line before installing:

```sh
p5 completion zsh            # show the line to add
p5 completion zsh --install  # install it automatically
```

Completions supported:
- `p5 diff [file]` — completes opened files
- `p5 delete [file]` — completes opened files
- `p5 filelog [file]` — completes depot paths
- `p5 sync [path]` — completes depot paths
- `p5 diff -c`, `p5 delete -c`, `p5 submit -c`, `p5 change` — completes pending CLs

## Commands

### `p5 status`

Show pending changes in the current directory, grouped by changelist — like `git status`.

```
Changes to be submitted (default changelist):
  M  src/auth/login.cpp
  A  src/auth/token.h

Other pending changelists:
  CL 123450
    M  src/net/socket.cpp

Local changes not opened in p4:
  ?  src/scratch.cpp

  use p4 edit <file> to open for edit, p4 add <file> to mark new files,
  p5 delete <file> to mark for delete  (p5 status -a for entire depot)
```

```sh
p5 status              # current directory (default)
p5 status src/auth     # specific subdirectory
p5 status -a           # entire depot
```

`p5 status` intentionally does not wrap `p4 edit` or `p4 add` — those commands add little value as wrappers and are faster to type directly. `p5 delete` is the exception because it adds a confirmation prompt.

### `p5 diff [files...]`

Colored unified diff of opened files — like `git diff`.

```
diff src/auth/login.cpp  (#41 → working copy)
──────────────────────────────────────────────
@@ -10,6 +10,8 @@ int authenticate(User& u) {
     validate(u);
+    log_attempt(u.name);      ← green background
-    old_log(u);               ← red background
     return check_token(u);
```

Options: `-c CL` to diff a specific changelist.

> For syntax-highlighted diffs, use `p5 changes` and press `Enter` to expand a changelist.

### `p5 delete <files...>`

Mark file(s) for delete, with a confirmation prompt.

```
Files to be deleted:
  D  src/auth/old_helper.cpp
  D  src/auth/legacy.h

Mark these files for delete? [y/N]: y

  deleted  src/auth/old_helper.cpp
  deleted  src/auth/legacy.h
```

Options: `-c CL` to target a specific changelist, `-y` to skip confirmation.

### `p5 sync [path]`

Sync the current directory (or a specific path) to head, with a clean summary.

```
Syncing src/auth to head...

  updated   src/auth/login.cpp     #42
  added     src/auth/retry.cpp     #1
  deleted   src/auth/old.cpp

2 updated, 1 added, 1 deleted
```

```sh
p5 sync             # sync current directory recursively
p5 sync src/auth    # sync a specific subdirectory
p5 sync -a          # sync entire depot (//...)
p5 sync -n          # dry run (preview only)
p5 sync -f          # force resync
```

### `p5 filelog <file>`

Revision history in `git log` style.

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

### `p5 changes`

Interactive TUI for browsing submitted (or pending) changelists.

```
 p5 changes
 ────────────────────────────────────────────────────────────
  CL      Date        Author   Description
 ────────────────────────────────────────────────────────────
  123456  2026-03-25  gigo     Fix null pointer in auth
  123455  2026-03-24  alice    Add retry logic to network
  123454  2026-03-23  bob      Update third-party deps
 ────────────────────────────────────────────────────────────
 [j/k: navigate]  [Enter: expand]  [/: filter]  [q: quit]
```

Press `Enter` to expand a changelist — shows files changed and a full colored, syntax-highlighted diff. Press `Esc` to go back.

```sh
p5 changes -u alice          # filter by user
p5 changes -m 100            # load up to 100 CLs
p5 changes -s pending        # show pending CLs instead
```

### `p5 change [cl]`

Create a new changelist or edit an existing one. Opens `$EDITOR`.

```sh
p5 change            # new CL
p5 change 123456     # edit CL 123456
p5 change -d 123456  # delete empty CL
```

### `p5 submit [-c cl]`

Show pending files, confirm, then submit.

```sh
p5 submit             # submit default changelist
p5 submit -c 123450   # submit a specific CL
p5 submit -d "Fix login bug"  # provide description inline
p5 submit -y          # skip confirmation prompt
```

### `p5 ws`

Interactive workspace selector — lists all your Perforce client workspaces and lets you switch with `Enter`.

```
 p5 ws
 ──────────────────────────────────────────────────────────
 ◆ gigo-main          (current)
   /home/gigo/workspace/main
   2026-03-25   build-server   Main integration workspace

   gigo-feature-x
   /home/gigo/workspace/feature-x
   2026-03-20   laptop         Feature branch workspace
 ──────────────────────────────────────────────────────────
 [j/k: navigate]  [Enter: switch]  [/: filter]  [q: quit]
```

Switching runs `p4 set P4CLIENT=<name>`, which persists in `~/.p4enviro` and applies to all shells immediately.

```sh
p5 ws                  # interactive TUI
p5 ws --no-tui         # plain table output
p5 ws -u alice         # list workspaces for another user
```

### `p5 completion`

Print shell completion setup instructions, or install directly with `--install`.

```sh
p5 completion                # show instructions for current shell (auto-detected)
p5 completion zsh            # show instructions for zsh
p5 completion --install      # append hook to ~/.bashrc (or ~/.zshrc / fish config)
p5 completion zsh --install  # install for zsh specifically
```

Running `--install` is idempotent — it checks for an existing hook before writing and prints the `source` command to activate immediately.

## Color Reference

| Color | Meaning |
|---|---|
| Yellow | Modified file |
| Green | Added file |
| Red | Deleted file |
| Dim | Untracked / unchanged |
| Bold blue | Changelist number |
| Yellow | Author name |
| Cyan | Diff hunk header (`@@`) |
| Green background | Added line in diff |
| Red background | Removed line in diff |
