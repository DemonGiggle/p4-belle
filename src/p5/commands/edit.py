"""p5 edit — open files for edit."""
from __future__ import annotations

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel, local_to_depot

console = Console()


@click.command()
@click.argument("files", nargs=-1, required=True)
@click.option("-c", "--cl", default=None, help="Add to changelist")
def edit_cmd(files: tuple[str, ...], cl: str | None) -> None:
    """Open file(s) for edit."""
    args = ["edit"]
    if cl:
        args += ["-c", cl]
    args += [local_to_depot(f) for f in files]

    try:
        raw = run_p4(args)
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    for line in raw.splitlines():
        # p4 output: //depot/path/file.cpp#1 - opened for edit
        if " - opened for edit" in line:
            depot_path = line.split("#")[0]
            rel = any_to_rel(depot_path)
            t = Text()
            t.append("  opened  ", style=f"bold {theme.MODIFIED}")
            t.append(rel)
            console.print(t)
        elif " - currently opened for edit" in line:
            depot_path = line.split("#")[0]
            rel = any_to_rel(depot_path)
            console.print(f"  [dim]already opened:[/dim]  {rel}")
        else:
            console.print(f"  [dim]{line}[/dim]")
