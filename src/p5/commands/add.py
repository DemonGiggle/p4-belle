"""p5 add — mark new files for add."""
from __future__ import annotations

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_opened_files, complete_pending_cls
from p5.dummy_data import render_add
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel, local_to_depot

console = Console()


@click.command()
@click.argument("files", nargs=-1, required=True, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Add to a specific changelist",
              shell_complete=complete_pending_cls)
@click.option("--dummy-data", is_flag=True,
              help="Display sample output instead of querying Perforce")
def add_cmd(files: tuple[str, ...], cl: str | None, dummy_data: bool) -> None:
    """Mark file(s) for add."""
    if dummy_data:
        render_add(files or ("src/auth/token_cache.cpp",))
        return
    args = ["add"]
    if cl:
        args += ["-c", cl]
    args += [local_to_depot(f) for f in files]

    try:
        raw = run_p4(args)
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    for line in raw.splitlines():
        if " - opened for add" in line:
            depot_path = line.split("#")[0]
            rel = any_to_rel(depot_path)
            t = Text()
            t.append("  opened  ", style=f"bold {theme.ADDED}")
            t.append(rel)
            console.print(t)
        else:
            console.print(f"  [dim]{line}[/dim]")
