"""p5 status — git-like pending changes overview."""
from __future__ import annotations

import os
from collections import defaultdict

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_depot_path
from p5.p4 import P4Error, run_p4_tagged
from p5.workspace import any_to_rel, check_cwd_in_workspace

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


@click.command()
@click.argument("path", default=None, required=False,
                shell_complete=complete_depot_path)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Show entire depot, not just current directory")
def status_cmd(path: str | None, show_all: bool) -> None:
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

    if not opened and not reconcile:
        console.print("[dim]nothing to commit, working tree clean[/dim]")
        return

    # Group opened files by changelist
    cl_files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rec in opened:
        cl   = rec.get("change", "default")
        path = any_to_rel(rec.get("depotFile", ""))
        action = rec.get("action", "edit")
        cl_files[cl].append((action, path))

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

    # Reconcile / untracked
    if reconcile:
        console.print(Text("Local changes not opened in p4:", style=theme.SECTION))
        for rec in reconcile:
            path   = any_to_rel(rec.get("depotFile", rec.get("clientFile", "")))
            action = rec.get("action", "?")
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
