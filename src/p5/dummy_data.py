"""Shared dummy data renderers and datasets for CLI demos and debugging."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from p5 import theme

console = Console()

DEFAULT_CL = "123456"
OTHER_CL = "123460"
SUBMITTED_CL = "123472"


def build_diff_groups() -> dict[str, list]:
    from p5.commands.diff import FileEntry, GROUP_ADDED, GROUP_DELETED, GROUP_MODIFIED

    return {
        GROUP_MODIFIED: [
            FileEntry(
                depot_path="//depot/demo/src/auth/login.cpp",
                local_path="/tmp/p5-demo/src/auth/login.cpp",
                action="edit",
                file_type="text",
                display_path="src/auth/login.cpp",
            ),
        ],
        GROUP_ADDED: [
            FileEntry(
                depot_path="//depot/demo/src/auth/token_cache.cpp",
                local_path="/tmp/p5-demo/src/auth/token_cache.cpp",
                action="add",
                file_type="text",
                display_path="src/auth/token_cache.cpp",
            ),
        ],
        GROUP_DELETED: [
            FileEntry(
                depot_path="//depot/demo/src/legacy/old_auth.cpp",
                local_path="",
                action="delete",
                file_type="text",
                display_path="src/legacy/old_auth.cpp",
            ),
        ],
    }


def build_diff_cache() -> dict[str, list[tuple[str, str]]]:
    from p5 import theme as T

    return {
        "//depot/demo/src/auth/login.cpp": [
            ("@@ -10,6 +10,8 @@", f"bold {T.DIFF_HUNK}"),
            (" validate(user);", ""),
            ("+log_attempt(user.name);", T.DIFF_ADD),
            ("-old_log(user);", T.DIFF_DEL),
            (" return check_token(user);", ""),
        ],
        "//depot/demo/src/auth/token_cache.cpp": [
            ("new file: src/auth/token_cache.cpp", f"bold {T.DIFF_ADD}"),
            ("+class TokenCache {", T.DIFF_ADD),
            ("+    bool warm = true;", T.DIFF_ADD),
            ("+};", T.DIFF_ADD),
        ],
        "//depot/demo/src/legacy/old_auth.cpp": [
            ("deleted file: src/legacy/old_auth.cpp", f"bold {T.DIFF_DEL}"),
            ("-int legacy_auth() {", T.DIFF_DEL),
            ("-    return 0;", T.DIFF_DEL),
            ("-}", T.DIFF_DEL),
        ],
    }


def build_changes_records() -> list:
    from p5.tui.changes_app import ChangeRecord

    return [
        ChangeRecord(
            cl="123472",
            date="2026-04-20",
            user="gigo",
            description="Fix login race in auth flow",
            status="submitted",
            files=[
                ("edit", "src/auth/login.cpp"),
                ("add", "src/auth/token_cache.cpp"),
            ],
            diff=_demo_change_diff(
                "src/auth/login.cpp",
                [
                    "@@ -10,6 +10,8 @@ int authenticate(User& user) {",
                    "     validate(user);",
                    "+    log_attempt(user.name);",
                    "-    old_log(user);",
                    "     return check_token(user);",
                ],
            ),
            loaded=True,
        ),
        ChangeRecord(
            cl="123470",
            date="2026-04-20",
            user="alice",
            description="Add retry cache for auth tokens",
            status="submitted",
            files=[("add", "src/auth/retry_cache.cpp")],
            diff=_demo_change_diff(
                "src/auth/retry_cache.cpp",
                [
                    "@@ -0,0 +1,4 @@",
                    "+class RetryCache {",
                    "+public:",
                    "+    bool enabled = true;",
                    "+};",
                ],
            ),
            loaded=True,
        ),
        ChangeRecord(
            cl="123469",
            date="2026-04-19",
            user="bob",
            description="Remove legacy auth branch",
            status="submitted",
            files=[("delete", "src/legacy/old_auth.cpp")],
            diff=_demo_change_diff(
                "src/legacy/old_auth.cpp",
                [
                    "@@ -1,3 +0,0 @@",
                    "-int legacy_auth() {",
                    "-    return 0;",
                    "-}",
                ],
            ),
            loaded=True,
        ),
    ]


def build_change_files() -> list:
    from p5.tui.change_app import FileRecord

    return [
        FileRecord("//depot/demo/src/auth/login.cpp", "edit", "src/auth/login.cpp"),
        FileRecord("//depot/demo/src/auth/token_cache.cpp", "add", "src/auth/token_cache.cpp"),
        FileRecord("//depot/demo/src/net/socket.cpp", "edit", "src/net/socket.cpp"),
        FileRecord("//depot/demo/src/legacy/old_auth.cpp", "delete", "src/legacy/old_auth.cpp"),
    ]


def build_submit_cls() -> list:
    from p5.tui.submit_app import FileRecord, PendingCL

    return [
        PendingCL(
            "default",
            "Demo default changelist for the auth flow",
            [
                FileRecord("//depot/demo/src/auth/login.cpp", "edit", "src/auth/login.cpp"),
                FileRecord("//depot/demo/src/auth/token_cache.cpp", "add", "src/auth/token_cache.cpp"),
            ],
        ),
        PendingCL(
            OTHER_CL,
            "Retry cache follow-ups",
            [
                FileRecord("//depot/demo/src/auth/retry_cache.cpp", "edit", "src/auth/retry_cache.cpp"),
                FileRecord("//depot/demo/src/auth/retry_ui.cpp", "add", "src/auth/retry_ui.cpp"),
            ],
        ),
    ]


def build_ws_records() -> list:
    from p5.tui.ws_app import ClientRecord

    return [
        ClientRecord(
            name="gigo-main",
            root="/home/gigo/workspace/main",
            host="build-box",
            description="Main integration workspace",
            access="2026-04-21",
            update="2026-04-21",
            is_current=True,
        ),
        ClientRecord(
            name="gigo-demo",
            root="/home/gigo/workspace/demo",
            host="laptop",
            description="Demo workspace for p5 feature walkthroughs",
            access="2026-04-20",
            update="2026-04-20",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-release",
            root="/home/gigo/workspace/release",
            host="ci-runner",
            description="Release branch validation",
            access="2026-04-18",
            update="2026-04-18",
            is_current=False,
        ),
    ]


def render_status() -> None:
    console.print(Text("Changes to be submitted (default changelist):", style=theme.SECTION))
    for action, path in [
        ("edit", "src/auth/login.cpp"),
        ("add", "src/auth/token_cache.cpp"),
    ]:
        console.print(_file_line(action, path))
    console.print()

    console.print(Text("Other pending changelists:", style=theme.SECTION))
    console.print(f"  [bold blue]CL {OTHER_CL}[/bold blue]")
    line = Text("    ")
    line.append("D", style=f"bold {theme.DELETED}")
    line.append("  src/legacy/old_auth.cpp")
    console.print(line)
    console.print()

    console.print(Text("Local changes not opened in p4:", style=theme.SECTION))
    console.print(_file_line("?", "scratch/demo_notes.txt"))
    console.print()
    console.print(
        "  [dim]use [/dim][bold]p4 edit <file>[/bold][dim] to open for edit, "
        "[/dim][bold]p4 add <file>[/bold][dim] to mark new files, "
        "[/dim][bold]p5 delete <file>[/bold][dim] to mark for delete  "
        "([/dim][bold]p5 status -r[/bold][dim] to scan for untracked changes)[/dim]"
    )


def render_diff() -> None:
    console.print(Text("diff src/auth/login.cpp  (#41 -> working copy)", style=theme.SECTION))
    console.print(Text("@@ -10,6 +10,8 @@", style=f"bold {theme.DIFF_HUNK}"))
    console.print(" validate(user);")
    console.print(Text("+log_attempt(user.name);", style=theme.DIFF_ADD))
    console.print(Text("-old_log(user);", style=theme.DIFF_DEL))
    console.print(" return check_token(user);")
    console.print()
    console.print(Text("diff src/auth/token_cache.cpp  (new file)", style=theme.SECTION))
    console.print(Text("+class TokenCache {", style=theme.DIFF_ADD))
    console.print(Text("+    bool warm = true;", style=theme.DIFF_ADD))
    console.print(Text("+};", style=theme.DIFF_ADD))


def render_delete() -> None:
    console.print(Text("Files to be deleted:", style=theme.SECTION))
    for path in ["src/legacy/old_auth.cpp", "src/legacy/unused_policy.h"]:
        console.print(_file_line("delete", path))
    console.print()
    console.print("Mark these files for delete? [y/N]: y")
    console.print()
    for path in ["src/legacy/old_auth.cpp", "src/legacy/unused_policy.h"]:
        line = Text()
        line.append("  deleted  ", style=f"bold {theme.DELETED}")
        line.append(path)
        console.print(line)


def render_sync() -> None:
    console.print("[dim]Syncing src/auth to head...[/dim]")
    console.print()
    console.print(_summary_line("updated", "src/auth/login.cpp", "#42", theme.SYNC_UPDATED))
    console.print(_summary_line("added", "src/auth/retry.cpp", "#1", theme.SYNC_ADDED))
    console.print(_summary_line("deleted", "src/auth/old_auth.cpp", "", theme.SYNC_DELETED))
    console.print()
    console.print(
        f"  [{theme.SYNC_UPDATED}]1 updated[/{theme.SYNC_UPDATED}], "
        f"[{theme.SYNC_ADDED}]1 added[/{theme.SYNC_ADDED}], "
        f"[{theme.SYNC_DELETED}]1 deleted[/{theme.SYNC_DELETED}]"
    )
    console.print()
    console.print(Text("Changelists synced:", style=theme.SECTION))
    console.print(_cl_line("123470", "alice", "Refine login retry handling"))
    console.print(_cl_line("123469", "bob", "Remove legacy auth branch"))


def render_change(cl_number: str | None, do_delete: bool) -> None:
    if do_delete:
        target = cl_number or DEFAULT_CL
        console.print(f"[green]Change {target} deleted.[/green]")
        return

    if cl_number:
        console.print(f"[dim]Dummy data: would open changelist {cl_number} in $EDITOR[/dim]")
        console.print(Text(f"Change {cl_number}", style=theme.SECTION))
        console.print("  Fix login race in auth flow")
        console.print("  Files:")
        console.print(_file_line("edit", "src/auth/login.cpp"))
        console.print(_file_line("add", "src/auth/token_cache.cpp"))
        return

    console.print(Text("Selected for a new changelist:", style=theme.SECTION))
    console.print(_file_line("edit", "src/auth/login.cpp"))
    console.print(_file_line("add", "src/auth/token_cache.cpp"))
    console.print()
    console.print(Text("Still in default changelist:", style=theme.SECTION))
    console.print(_file_line("edit", "src/net/socket.cpp"))
    console.print(_file_line("delete", "src/legacy/old_auth.cpp"))
    console.print()
    console.print(Text("[space: toggle] [n: new CL] [m: move] [/: filter] [q: quit]", style="dim"))


def render_submit(cl: str | None, description: str | None) -> None:
    target = cl or DEFAULT_CL
    console.print(Text(f"Files in CL {target}:", style=theme.SECTION))
    console.print(_file_line("edit", "src/auth/login.cpp"))
    console.print(_file_line("add", "src/auth/token_cache.cpp"))
    console.print()
    if description:
        console.print(f"[dim]Description:[/dim] {description}")
        console.print()
    console.print(
        Text("  submitted  ", style=f"bold {theme.ADDED}") +
        Text(f"CL {SUBMITTED_CL}", style=theme.CL_NUM)
    )


def render_changes() -> None:
    table = Table(show_header=True, header_style=f"bold {theme.SECTION}", box=None, padding=(0, 2))
    table.add_column("CL", style=theme.CL_NUM, no_wrap=True)
    table.add_column("Date", style=theme.DATE, no_wrap=True)
    table.add_column("Author", style=theme.AUTHOR, no_wrap=True)
    table.add_column("Description")
    table.add_row("123472", "2026-04-20", "gigo", "Fix login race in auth flow")
    table.add_row("123470", "2026-04-20", "alice", "Add retry cache for auth tokens")
    table.add_row("123469", "2026-04-19", "bob", "Remove legacy auth branch")
    console.print(table)
    console.print()
    console.print("[dim]Press Enter in the real TUI to expand a changelist diff.[/dim]")


def render_filelog() -> None:
    console.print(Text("src/auth/login.cpp", style=f"bold {theme.DIFF_HEADER}"))
    console.print()
    for is_last, rev, cl, date, user, action, desc in [
        (False, "42", "123472", "2026-04-20", "gigo", "edit", "Fix login race in auth flow"),
        (False, "41", "123470", "2026-04-20", "alice", "edit", "Add retry cache for auth tokens"),
        (True, "40", "123430", "2026-04-11", "bob", "add", "Initial implementation"),
    ]:
        connector = " " if is_last else "│"
        header = Text()
        header.append("● ", style=f"bold {theme.CL_NUM}")
        header.append(f"#{rev}  ", style=f"bold {theme.BRANCH}")
        header.append(f"CL {cl}  ", style=theme.CL_NUM)
        header.append(date, style=theme.DATE)
        header.append("  ")
        header.append(user, style=theme.AUTHOR)
        header.append(f"  [{action}]", style=f"dim {theme.ACTION_COLOR.get(action, 'white')}")
        console.print(header)
        console.print(Text(f"{connector}  {desc}", style="dim"))
        if not is_last:
            console.print(Text(connector, style="dim"))


def render_ws() -> None:
    table = Table(show_header=True, header_style=f"bold {theme.SECTION}", box=None, padding=(0, 2))
    table.add_column("", width=2)
    table.add_column("Workspace", style=f"bold {theme.CL_NUM}", no_wrap=True)
    table.add_column("Root")
    table.add_column("Host", style=theme.AUTHOR)
    table.add_column("Last Access", style=theme.DATE)
    table.add_row("◆", "gigo-main", "/home/gigo/workspace/main", "build-box", "2026-04-21")
    table.add_row("", "gigo-demo", "/home/gigo/workspace/demo", "laptop", "2026-04-20")
    table.add_row("", "gigo-release", "/home/gigo/workspace/release", "ci-runner", "2026-04-18")
    console.print(table)
    console.print("\n  [dim]current:[/dim] [cyan]gigo-main[/cyan]")
    console.print("  [dim]to switch:[/dim]  p5 ws  (interactive)  or  p4 set P4CLIENT=<name>")


def render_completion(shell: str | None, install: bool) -> None:
    resolved = shell or "zsh"
    profile_map = {
        "bash": "~/.bashrc",
        "zsh": "~/.zshrc",
        "fish": "~/.config/fish/config.fish",
    }
    script_map = {
        "bash": 'eval "$(_P5_COMPLETE=bash_source p5)"',
        "zsh": 'eval "$(_P5_COMPLETE=zsh_source p5)"',
        "fish": "_P5_COMPLETE=fish_source p5 | source",
    }
    profile = profile_map[resolved]
    script = script_map[resolved]

    if install:
        console.print(f"[green]✓[/green] Dummy install mode: would append to [cyan]{profile}[/cyan]")
        console.print(f"[dim]{script}[/dim]")
        return

    console.print(f"\n[bold]Enable p5 tab completion for {resolved}[/bold]\n")
    console.print(f"Add this line to [cyan]{profile}[/cyan]:\n")
    console.print(f"  [green]{script}[/green]\n")
    console.print(f"  [dim]p5 completion {resolved} --install[/dim]\n")


def _file_line(action: str, rel_path: str) -> Text:
    letter = theme.STATE_LETTER.get(action, action[:1].upper())
    color = theme.ACTION_COLOR.get(action, theme.UNTRACKED if action == "?" else "white")
    line = Text()
    line.append(f"  {letter}  ", style=f"bold {color}")
    line.append(rel_path)
    return line


def _summary_line(label: str, path: str, rev: str, color: str) -> Text:
    line = Text()
    line.append(f"  {label:<8} ", style=f"bold {color}")
    line.append(path)
    if rev:
        line.append("  ")
        line.append(rev, style=theme.DATE)
    return line


def _cl_line(cl: str, user: str, desc: str) -> Text:
    line = Text()
    line.append(f"  CL {cl:<8}", style=theme.CL_NUM)
    line.append(f"  {user:<12}", style=theme.AUTHOR)
    line.append(desc, style="dim")
    return line


def _demo_change_diff(display_path: str, lines: list[str]) -> str:
    return "\n".join(
        [
            f"diff {display_path}",
            f"--- a/{display_path}",
            f"+++ b/{display_path}",
            *lines,
            "",
        ]
    )
