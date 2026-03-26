# p5

A Perforce CLI with git-like UX — relative paths, colored output, and an interactive changelist browser.

`p4` speaks in absolute depot paths. `p5` speaks like a human.

```
# instead of:
p4 edit //depot/project/src/auth/login.cpp

# you write:
p5 edit src/auth/login.cpp
```

## Features

- **Relative paths** everywhere — input and output strip the depot/workspace root automatically
- **Colored output** — file states, diffs, and logs styled like `git`
- **Interactive `changes` browser** — navigate changelists with `j/k`, expand diffs with `Enter`
- Zero configuration — depot root is detected automatically from `p4 info`

## Requirements

- Python 3.9+
- Perforce `p4` client installed and configured (P4PORT, P4USER, P4CLIENT set)

## Install

```sh
git clone <this-repo>
cd p4-belle
python3.9 -m pip install -e .
```

The `p5` command will be installed to `~/.local/bin/p5`. Make sure that directory is on your `PATH`:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Commands

### `p5 status`

Show all pending changes, grouped by changelist — like `git status`.

```
Changes to be submitted (default changelist):
  M  src/auth/login.cpp
  A  src/auth/token.h

Other pending changelists:
  CL 123450  "Refactor network layer"
    M  src/net/socket.cpp

Local changes not opened in p4:
  ?  src/scratch.cpp
```

### `p5 diff [files...]`

Colored unified diff of opened files — like `git diff`.

```
diff src/auth/login.cpp  (#41 → working copy)
──────────────────────────────────────────────
@@ -10,6 +10,8 @@ int authenticate(User& u) {
     validate(u);
+    log_attempt(u.name);
-    old_log(u);
     return check_token(u);
```

### `p5 edit / add / delete <files...>`

Open files for edit, add, or delete. Accepts relative paths or globs.

```sh
p5 edit src/auth/login.cpp
p5 add  src/auth/new_feature.h
p5 delete src/auth/old_helper.cpp

# target a specific changelist
p5 edit -c 123450 src/net/socket.cpp
```

### `p5 sync [path]`

Sync workspace to head with a clean summary.

```
Syncing to head...

  updated   src/auth/login.cpp     #42
  added     src/net/retry.cpp      #1
  deleted   src/net/old_proto.cpp

2 updated, 1 added, 1 deleted
```

Options: `-f` force resync, `-n` dry run.

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
 ▶123456  2026-03-25  gigo     Fix null pointer in auth
  123455  2026-03-24  alice    Add retry logic to network
  123454  2026-03-23  bob      Update third-party deps
 ────────────────────────────────────────────────────────────
 [j/k: navigate]  [Enter: expand]  [/: filter]  [q: quit]
```

Press `Enter` to expand a changelist and see its files and full colored diff. Press `Esc` to go back.

Options:

```sh
p5 changes -u alice          # filter by user
p5 changes -m 100            # load up to 100 CLs
p5 changes -s pending        # show pending CLs instead
```

### `p5 change [cl]`

Create a new changelist or edit an existing one. Opens `$EDITOR`.

```sh
p5 change          # new CL
p5 change 123456   # edit CL 123456
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
