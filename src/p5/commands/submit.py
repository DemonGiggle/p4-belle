"""p5 submit — submit a changelist."""
from __future__ import annotations

import re

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_pending_cls
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.workspace import any_to_rel, check_cwd_in_workspace

console = Console()


def _show_pending(cl: str | None) -> bool:
    """Print files in the pending changelist. Returns False if nothing to submit."""
    try:
        args = ["opened"]
        if cl:
            args += ["-c", cl]
        opened = run_p4_tagged(args)
    except P4Error:
        opened = []

    if not opened:
        console.print("[dim]nothing to submit[/dim]")
        return False

    cl_label = f"CL {cl}" if cl else "default changelist"
    console.print(Text(f"Files in {cl_label}:", style=theme.SECTION))
    for rec in opened:
        path   = any_to_rel(rec.get("depotFile", ""))
        action = rec.get("action", "edit")
        letter = theme.STATE_LETTER.get(action, "M")
        color  = theme.ACTION_COLOR.get(action, "white")
        t = Text()
        t.append(f"  {letter}  ", style=f"bold {color}")
        t.append(path)
        console.print(t)
    console.print()
    return True


@click.command()
@click.option("-c", "--cl", default=None, help="Submit a specific numbered changelist",
              shell_complete=complete_pending_cls)
@click.option("-d", "--description", default=None, help="Changelist description (skips editor)")
@click.option("-y", "--yes", "no_confirm", is_flag=True, help="Skip confirmation prompt")
def submit_cmd(cl: str | None, description: str | None, no_confirm: bool) -> None:
    """Submit pending changes to the depot."""
    check_cwd_in_workspace()
    if not _show_pending(cl):
        return

    if not no_confirm:
        click.confirm("Submit these changes?", abort=True)

    args = ["submit"]
    if cl:
        args += ["-c", cl]
    if description:
        args += ["-d", description]

    console.print()
    try:
        # If no description given, let p4 open $EDITOR
        if not description:
            import subprocess
            cmd = ["p4", "submit"]
            if cl:
                cmd += ["-c", cl]
            result = subprocess.run(cmd, capture_output=False)
            if result.returncode != 0:
                console.print("[red]submit failed[/red]")
            return

        raw = run_p4(args)
        # Extract submitted CL number
        m = re.search(r"Change (\d+) submitted", raw)
        if m:
            console.print(
                Text("  submitted  ", style=f"bold {theme.ADDED}") +
                Text(f"CL {m.group(1)}", style=theme.CL_NUM)
            )
        else:
            console.print(raw.strip())
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
