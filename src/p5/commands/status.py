"""p5 status — git-like pending changes overview."""
from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_depot_path
from p5.p4 import P4Error, run_p4_tagged
from p5.workspace import check_cwd_in_workspace, get_workspace

console = Console()


def _letter(action: str) -> str:
    return theme.STATE_LETTER.get(action, action[0].upper())


def _color(action: str) -> str:
    return theme.ACTION_COLOR.get(action, "white")


def _render_file_line(action: str, rel_path: str) -> Text:
    letter = _letter(action)
    color  = _color(action)
    t = Text()
    t.append(f"  {letter}  ", style=f"bold {color}")
    t.append(rel_path)
    return t


def _to_cwd_rel(rec: dict) -> str:
    """Get a cwd-relative display path from a p4 record.

    Tries clientFile and depotFile, converting either to a local absolute
    path via the workspace mapping, then makes it relative to cwd.
    """
    ws = get_workspace()
    cwd = os.getcwd()

    # Try clientFile first — may be //client/... syntax or absolute local
    client_file = rec.get("clientFile", "")
    if client_file:
        if client_file.startswith("//"):
            # Client-syntax path: //client-name/rest → strip to get ws-relative
            # e.g. //my-ws/src/foo.cpp → src/foo.cpp
            client_prefix = "//" + ws.client_name + "/"
            if client_file.startswith(client_prefix):
                ws_rel = client_file[len(client_prefix):]
                abs_path = str(Path(ws.client_root) / ws_rel)
                return os.path.relpath(abs_path, cwd)
        else:
            # Absolute local path
            return os.path.relpath(client_file, cwd)

    # Fallback: depot path → workspace-relative → cwd-relative
    depot_file = rec.get("depotFile", "")
    prefix = ws.depot_prefix.rstrip("/") + "/"
    if depot_file.startswith(prefix):
        ws_rel = depot_file[len(prefix):]
        abs_path = str(Path(ws.client_root) / ws_rel)
        return os.path.relpath(abs_path, cwd)

    return depot_file  # can't resolve, show raw


def _is_excluded(rel_path: str, excludes: tuple[str, ...]) -> bool:
    """Check if a cwd-relative path starts with any exclude prefix.

    Both rel_path and excludes are relative to cwd, so direct prefix
    matching works.
    """
    for ex in excludes:
        ex_clean = ex.rstrip("/")
        if ex_clean == ".":
            return True  # '.' means everything under cwd
        if rel_path == ex_clean or rel_path.startswith(ex_clean + "/"):
            return True
    return False


@click.command()
@click.argument("path", default=None, required=False,
                shell_complete=complete_depot_path)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Show entire depot, not just current directory")
@click.option("-x", "--exclude", "excludes", multiple=True,
              help="Exclude paths matching this prefix (repeatable)")
def status_cmd(path: str | None, show_all: bool, excludes: tuple[str, ...]) -> None:
    """Show pending changes in the current directory (like git status)."""
    if not show_all:
        check_cwd_in_workspace()
    if show_all:
        p4_path = "//..."
    elif path is not None:
        # Accept depot paths (//...) or local paths; append /... for directories
        if path.startswith("//"):
            p4_path = path.rstrip("/") + "/..."
        else:
            p4_path = os.path.abspath(path).rstrip("/") + "/..."
    else:
        # Use the local filesystem path directly — avoids depot path mapping issues
        p4_path = os.getcwd().rstrip("/") + "/..."

    try:
        opened = run_p4_tagged(["opened", p4_path])
    except P4Error as e:
        # "file(s) not opened on this client" → nothing open
        if "not opened" in str(e).lower():
            opened = []
        else:
            raise

    # Also get reconcile / untracked status
    try:
        reconcile = run_p4_tagged(["reconcile", "-n", "-e", "-a", "-d", p4_path])
    except P4Error:
        reconcile = []

    # Group opened files by changelist, applying excludes
    # All paths are relative to cwd for both display and exclude matching
    cl_files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rec in opened:
        cl     = rec.get("change", "default")
        rel    = _to_cwd_rel(rec)
        action = rec.get("action", "edit")
        if excludes and _is_excluded(rel, excludes):
            continue
        cl_files[cl].append((action, rel))

    # Print default CL first
    if "default" in cl_files:
        console.print(Text("Changes to be submitted (default changelist):", style=theme.SECTION))
        for action, path in cl_files["default"]:
            console.print(_render_file_line(action, path))
        console.print()

    # Other named CLs
    other_cls = [cl for cl in cl_files if cl != "default"]
    if other_cls:
        console.print(Text("Other pending changelists:", style=theme.SECTION))
        for cl in other_cls:
            console.print(f"  [bold blue]CL {cl}[/bold blue]")
            for action, path in cl_files[cl]:
                t = Text("    ")
                t.append(_letter(action), style=f"bold {_color(action)}")
                t.append(f"  {path}")
                console.print(t)
        console.print()

    # Reconcile / untracked (filter by excludes)
    filtered_reconcile: list[tuple[str, str]] = []
    if reconcile:
        for rec in reconcile:
            rel = _to_cwd_rel(rec)
            if excludes and _is_excluded(rel, excludes):
                continue
            filtered_reconcile.append((rel, rec.get("action", "?")))

    if not cl_files and not filtered_reconcile:
        console.print("[dim]nothing to commit, working tree clean[/dim]")
        return

    if filtered_reconcile:
        console.print(Text("Local changes not opened in p4:", style=theme.SECTION))
        for path, action in filtered_reconcile:
            if action not in theme.STATE_LETTER:
                letter = "?"
                color  = theme.UNTRACKED
            else:
                letter = _letter(action)
                color  = _color(action)
            t = Text()
            t.append(f"  {letter}  ", style=f"bold {color}")
            t.append(path)
            console.print(t)

    console.print()
    console.print(
        "  [dim]use [/dim][bold]p4 edit <file>[/bold][dim] to open for edit, "
        "[/dim][bold]p4 add <file>[/bold][dim] to mark new files, "
        "[/dim][bold]p5 delete <file>[/bold][dim] to mark for delete  "
        "([/dim][bold]p5 status -a[/bold][dim] for entire depot)[/dim]"
    )
