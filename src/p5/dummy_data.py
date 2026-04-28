"""Shared dummy data renderers and datasets for CLI demos and debugging."""
from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console
from rich.table import Table
from rich.text import Text

from p5 import theme

console = Console()

DEFAULT_CL = "123456"
OTHER_CL = "123460"
SUBMITTED_CL = "123472"
LARGE_DUMMY_DATASET_SIZE = 120

_DEMO_USERS = ("alice", "bob", "carol", "dave", "erin", "frank", "gigo", "heidi")
_DEMO_HOSTS = ("build-box", "ci-runner", "desktop", "laptop", "perf-lab", "staging-box")
_DEMO_AREAS = ("auth", "net", "ui", "data", "infra", "tools")
_DEMO_ACTIONS = ("edit", "add", "delete")


def _demo_date(offset: int) -> str:
    return (date(2026, 4, 21) - timedelta(days=offset)).isoformat()


def _fill_to_size(items: list, factories: list, target_size: int = LARGE_DUMMY_DATASET_SIZE) -> list:
    idx = 0
    while len(items) < target_size:
        items.append(factories[idx]())
        idx += 1
    return items


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
            FileEntry(
                depot_path="//depot/demo/src/auth/session.cpp",
                local_path="/tmp/p5-demo/src/auth/session.cpp",
                action="edit",
                file_type="text",
                display_path="src/auth/session.cpp",
            ),
            FileEntry(
                depot_path="//depot/demo/src/net/socket.cpp",
                local_path="/tmp/p5-demo/src/net/socket.cpp",
                action="edit",
                file_type="text",
                display_path="src/net/socket.cpp",
            ),
            FileEntry(
                depot_path="//depot/demo/src/net/retry.cpp",
                local_path="/tmp/p5-demo/src/net/retry.cpp",
                action="edit",
                file_type="text",
                display_path="src/net/retry.cpp",
            ),
            FileEntry(
                depot_path="//depot/demo/src/ui/login_view.cpp",
                local_path="/tmp/p5-demo/src/ui/login_view.cpp",
                action="edit",
                file_type="text",
                display_path="src/ui/login_view.cpp",
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
            FileEntry(
                depot_path="//depot/demo/src/auth/retry_cache.cpp",
                local_path="/tmp/p5-demo/src/auth/retry_cache.cpp",
                action="add",
                file_type="text",
                display_path="src/auth/retry_cache.cpp",
            ),
            FileEntry(
                depot_path="//depot/demo/src/tools/demo_seed.cpp",
                local_path="/tmp/p5-demo/src/tools/demo_seed.cpp",
                action="add",
                file_type="text",
                display_path="src/tools/demo_seed.cpp",
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
            FileEntry(
                depot_path="//depot/demo/src/legacy/old_policy.cpp",
                local_path="",
                action="delete",
                file_type="text",
                display_path="src/legacy/old_policy.cpp",
            ),
            FileEntry(
                depot_path="//depot/demo/src/legacy/old_login_ui.cpp",
                local_path="",
                action="delete",
                file_type="text",
                display_path="src/legacy/old_login_ui.cpp",
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
        "//depot/demo/src/auth/session.cpp": [
            ("@@ -22,6 +22,9 @@", f"bold {T.DIFF_HUNK}"),
            (" if (!session.valid()) return false;", ""),
            ("+session.refresh();", T.DIFF_ADD),
            ("+session.touch();", T.DIFF_ADD),
            (" return session.persist();", ""),
        ],
        "//depot/demo/src/net/socket.cpp": [
            ("@@ -50,4 +50,5 @@", f"bold {T.DIFF_HUNK}"),
            (" connect_once();", ""),
            ("+record_backoff_metric();", T.DIFF_ADD),
            (" return true;", ""),
        ],
        "//depot/demo/src/net/retry.cpp": [
            ("@@ -1,5 +1,7 @@", f"bold {T.DIFF_HUNK}"),
            (" int attempts = 0;", ""),
            ("+const int max_attempts = 5;", T.DIFF_ADD),
            ("-const int max_attempts = 3;", T.DIFF_DEL),
            (" while (attempts < max_attempts) {}", ""),
        ],
        "//depot/demo/src/ui/login_view.cpp": [
            ("@@ -80,3 +80,5 @@", f"bold {T.DIFF_HUNK}"),
            (" render_header();", ""),
            ("+render_retry_hint();", T.DIFF_ADD),
            (" render_form();", ""),
        ],
        "//depot/demo/src/auth/token_cache.cpp": [
            ("new file: src/auth/token_cache.cpp", f"bold {T.DIFF_ADD}"),
            ("+class TokenCache {", T.DIFF_ADD),
            ("+    bool warm = true;", T.DIFF_ADD),
            ("+};", T.DIFF_ADD),
        ],
        "//depot/demo/src/auth/retry_cache.cpp": [
            ("new file: src/auth/retry_cache.cpp", f"bold {T.DIFF_ADD}"),
            ("+struct RetryCache {", T.DIFF_ADD),
            ("+    int attempts = 0;", T.DIFF_ADD),
            ("+};", T.DIFF_ADD),
        ],
        "//depot/demo/src/tools/demo_seed.cpp": [
            ("new file: src/tools/demo_seed.cpp", f"bold {T.DIFF_ADD}"),
            ("+void seed_demo_data();", T.DIFF_ADD),
        ],
        "//depot/demo/src/legacy/old_auth.cpp": [
            ("deleted file: src/legacy/old_auth.cpp", f"bold {T.DIFF_DEL}"),
            ("-int legacy_auth() {", T.DIFF_DEL),
            ("-    return 0;", T.DIFF_DEL),
            ("-}", T.DIFF_DEL),
        ],
        "//depot/demo/src/legacy/old_policy.cpp": [
            ("deleted file: src/legacy/old_policy.cpp", f"bold {T.DIFF_DEL}"),
            ("-bool legacy_policy_enabled();", T.DIFF_DEL),
        ],
        "//depot/demo/src/legacy/old_login_ui.cpp": [
            ("deleted file: src/legacy/old_login_ui.cpp", f"bold {T.DIFF_DEL}"),
            ("-void render_old_login_ui();", T.DIFF_DEL),
        ],
    }


def build_changes_records() -> list:
    from p5.tui.changes_app import ChangeRecord

    records = [
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
    records.extend([
        ChangeRecord(
            cl=str(123468 - i),
            date=_demo_date(i + 2),
            user=_DEMO_USERS[i % len(_DEMO_USERS)],
            description=f"Demo follow-up change {i + 1} for paging and filtering",
            status="submitted",
            files=[
                ("edit", f"src/demo/module_{i}/file_{i}.cpp"),
                ("add", f"src/demo/module_{i}/helper_{i}.h"),
            ],
            diff=_demo_change_diff(
                f"src/demo/module_{i}/file_{i}.cpp",
                [
                    "@@ -1,2 +1,3 @@",
                    " int main() {",
                    "+    return 0;",
                    " }",
                ],
            ),
            loaded=True,
        )
        for i in range(12)
    ])
    _fill_to_size(
        records,
        [
            lambda i=i: ChangeRecord(
                cl=str(123300 - i),
                date=_demo_date(i + 14),
                user=_DEMO_USERS[i % len(_DEMO_USERS)],
                description=(
                    f"{_DEMO_AREAS[i % len(_DEMO_AREAS)].title()} pagination sample "
                    f"{i + 1} for scrolling and filtering"
                ),
                status="submitted",
                files=[
                    (_DEMO_ACTIONS[i % len(_DEMO_ACTIONS)], f"src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/demo_{i}.cpp"),
                    ("edit", f"src/{_DEMO_AREAS[(i + 1) % len(_DEMO_AREAS)]}/helper_{i}.h"),
                ],
                diff=_demo_change_diff(
                    f"src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/demo_{i}.cpp",
                    [
                        "@@ -3,3 +3,5 @@",
                        " void refresh_demo_state() {",
                        f'+    log_demo_metric("sample_{i}");',
                        f"+    apply_demo_step({(i % 5) + 1});",
                        " }",
                    ],
                ),
                loaded=True,
            )
            for i in range(LARGE_DUMMY_DATASET_SIZE)
        ],
    )
    return records


def build_change_files() -> list:
    from p5.tui.change_app import FileRecord

    files = [
        FileRecord("//depot/demo/src/auth/login.cpp", "edit", "src/auth/login.cpp"),
        FileRecord("//depot/demo/src/auth/token_cache.cpp", "add", "src/auth/token_cache.cpp"),
        FileRecord("//depot/demo/src/net/socket.cpp", "edit", "src/net/socket.cpp"),
        FileRecord("//depot/demo/src/legacy/old_auth.cpp", "delete", "src/legacy/old_auth.cpp"),
        FileRecord("//depot/demo/src/auth/session.cpp", "edit", "src/auth/session.cpp"),
        FileRecord("//depot/demo/src/auth/retry_cache.cpp", "add", "src/auth/retry_cache.cpp"),
        FileRecord("//depot/demo/src/net/retry.cpp", "edit", "src/net/retry.cpp"),
        FileRecord("//depot/demo/src/ui/login_view.cpp", "edit", "src/ui/login_view.cpp"),
        FileRecord("//depot/demo/src/ui/login_state.cpp", "edit", "src/ui/login_state.cpp"),
        FileRecord("//depot/demo/src/data/session_store.cpp", "edit", "src/data/session_store.cpp"),
        FileRecord("//depot/demo/src/data/session_store.h", "add", "src/data/session_store.h"),
        FileRecord("//depot/demo/src/tools/demo_seed.cpp", "add", "src/tools/demo_seed.cpp"),
        FileRecord("//depot/demo/src/legacy/old_policy.cpp", "delete", "src/legacy/old_policy.cpp"),
        FileRecord("//depot/demo/src/legacy/old_login_ui.cpp", "delete", "src/legacy/old_login_ui.cpp"),
    ]
    _fill_to_size(
        files,
        [
            lambda i=i: FileRecord(
                f"//depot/demo/src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/bulk_{i}.cpp",
                _DEMO_ACTIONS[i % len(_DEMO_ACTIONS)],
                f"src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/bulk_{i}.cpp",
            )
            for i in range(LARGE_DUMMY_DATASET_SIZE)
        ],
    )
    return files


def build_change_diffs() -> dict[str, str]:
    diffs: dict[str, str] = {}
    for idx, record in enumerate(build_change_files()):
        if record.action == "add":
            body = [
                "@@ -0,0 +1,4 @@",
                f"+// demo file {idx + 1}",
                "+int main() {",
                "+    return 0;",
                "+}",
            ]
        elif record.action == "delete":
            body = [
                "@@ -1,4 +0,0 @@",
                f"-// deleted demo file {idx + 1}",
                "-int main() {",
                "-    return 0;",
                "-}",
            ]
        else:
            body = [
                "@@ -1,3 +1,4 @@",
                " int main() {",
                f"+    log_demo_metric({idx + 1});",
                "     return 0;",
                " }",
            ]
        diffs[record.depot_file] = _demo_change_diff(record.rel_path, body)
    return diffs


def build_submit_cls() -> list:
    from p5.tui.submit_app import FileRecord, PendingCL

    pending_cls = [
        PendingCL(
            "default",
            "Demo default changelist for the auth flow",
            [
                FileRecord("//depot/demo/src/auth/login.cpp", "edit", "src/auth/login.cpp"),
                FileRecord("//depot/demo/src/auth/token_cache.cpp", "add", "src/auth/token_cache.cpp"),
                FileRecord("//depot/demo/src/auth/session.cpp", "edit", "src/auth/session.cpp"),
                FileRecord("//depot/demo/src/ui/login_view.cpp", "edit", "src/ui/login_view.cpp"),
                FileRecord("//depot/demo/src/net/retry.cpp", "edit", "src/net/retry.cpp"),
                FileRecord("//depot/demo/src/net/socket.cpp", "edit", "src/net/socket.cpp"),
            ],
        ),
        PendingCL(
            OTHER_CL,
            "Retry cache follow-ups",
            [
                FileRecord("//depot/demo/src/auth/retry_cache.cpp", "edit", "src/auth/retry_cache.cpp"),
                FileRecord("//depot/demo/src/auth/retry_ui.cpp", "add", "src/auth/retry_ui.cpp"),
                FileRecord("//depot/demo/src/auth/retry_policy.cpp", "edit", "src/auth/retry_policy.cpp"),
                FileRecord("//depot/demo/src/auth/retry_policy.h", "add", "src/auth/retry_policy.h"),
            ],
        ),
        PendingCL(
            "123461",
            "UI polish for auth states",
            [
                FileRecord("//depot/demo/src/ui/login_state.cpp", "edit", "src/ui/login_state.cpp"),
                FileRecord("//depot/demo/src/ui/login_dialog.cpp", "edit", "src/ui/login_dialog.cpp"),
                FileRecord("//depot/demo/src/ui/login_dialog.h", "add", "src/ui/login_dialog.h"),
            ],
        ),
        PendingCL(
            "123462",
            "Legacy cleanup demo batch",
            [
                FileRecord("//depot/demo/src/legacy/old_auth.cpp", "delete", "src/legacy/old_auth.cpp"),
                FileRecord("//depot/demo/src/legacy/old_policy.cpp", "delete", "src/legacy/old_policy.cpp"),
                FileRecord("//depot/demo/src/legacy/old_login_ui.cpp", "delete", "src/legacy/old_login_ui.cpp"),
            ],
        ),
        *[
            PendingCL(
                str(123463 + i),
                f"Additional demo changelist {i + 1} for pagination",
                [
                    FileRecord(
                        f"//depot/demo/src/demo/cl_{i}/file_{j}.cpp",
                        "edit" if j % 2 == 0 else "add",
                        f"src/demo/cl_{i}/file_{j}.cpp",
                    )
                    for j in range(1, 4)
                ],
            )
            for i in range(8)
        ],
    ]
    _fill_to_size(
        pending_cls,
        [
            lambda i=i: PendingCL(
                str(123600 + i),
                f"{_DEMO_AREAS[i % len(_DEMO_AREAS)].title()} follow-up batch {i + 1} for list density",
                [
                    FileRecord(
                        f"//depot/demo/src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/submit_{i}_{j}.cpp",
                        _DEMO_ACTIONS[(i + j) % len(_DEMO_ACTIONS)],
                        f"src/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}/submit_{i}_{j}.cpp",
                    )
                    for j in range(1, 4)
                ],
            )
            for i in range(LARGE_DUMMY_DATASET_SIZE)
        ],
    )
    return pending_cls


def build_ws_records() -> list:
    from p5.tui.ws_app import ClientRecord

    records = [
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
        ClientRecord(
            name="gigo-feature-auth",
            root="/home/gigo/workspace/feature-auth",
            host="desktop",
            description="Feature branch for auth rewrite",
            access="2026-04-17",
            update="2026-04-17",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-staging",
            root="/home/gigo/workspace/staging",
            host="staging-box",
            description="Staging validation workspace",
            access="2026-04-16",
            update="2026-04-16",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-ux-demo",
            root="/home/gigo/workspace/ux-demo",
            host="laptop",
            description="UI walkthrough workspace",
            access="2026-04-15",
            update="2026-04-15",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-hotfix",
            root="/home/gigo/workspace/hotfix",
            host="desktop",
            description="Hotfix validation",
            access="2026-04-14",
            update="2026-04-14",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-benchmark",
            root="/home/gigo/workspace/benchmark",
            host="perf-lab",
            description="Performance comparison workspace",
            access="2026-04-13",
            update="2026-04-13",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-archive",
            root="/home/gigo/workspace/archive",
            host="backup-node",
            description="Archive and migration workspace",
            access="2026-04-12",
            update="2026-04-12",
            is_current=False,
        ),
        ClientRecord(
            name="gigo-sandbox",
            root="/home/gigo/workspace/sandbox",
            host="tablet",
            description="Scratch sandbox for demos",
            access="2026-04-11",
            update="2026-04-11",
            is_current=False,
        ),
    ]
    _fill_to_size(
        records,
        [
            lambda i=i: ClientRecord(
                name=f"gigo-{_DEMO_AREAS[i % len(_DEMO_AREAS)]}-demo-{i:03d}",
                root=f"/home/gigo/workspace/{_DEMO_AREAS[i % len(_DEMO_AREAS)]}-demo-{i:03d}",
                host=_DEMO_HOSTS[i % len(_DEMO_HOSTS)],
                description=(
                    f"{_DEMO_AREAS[i % len(_DEMO_AREAS)].title()} dummy workspace "
                    f"{i + 1} for scrolling and filter demos"
                ),
                access=_demo_date(i),
                update=_demo_date(i),
                is_current=False,
            )
            for i in range(LARGE_DUMMY_DATASET_SIZE)
        ],
    )
    return records


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
        "[/dim][bold]p5 delete <file>[/bold][dim] to mark for delete[/dim]"
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
