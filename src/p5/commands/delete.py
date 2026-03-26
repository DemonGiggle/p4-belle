"""p5 delete — mark files for delete, with confirmation."""
from __future__ import annotations

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_opened_files, complete_pending_cls
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel, local_to_depot

console = Console()


@click.command()
@click.argument("files", nargs=-1, required=True, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Add to changelist",
              shell_complete=complete_pending_cls)
@click.option("-y", "--yes", "no_confirm", is_flag=True, help="Skip confirmation prompt")
def delete_cmd(files: tuple[str, ...], cl: str | None, no_confirm: bool) -> None:
    """Mark file(s) for delete (with confirmation)."""
    rel_paths = [any_to_rel(local_to_depot(f)) for f in files]

    if not no_confirm:
        console.print(Text("Files to be deleted:", style=theme.SECTION))
        for p in rel_paths:
            t = Text()
            t.append("  D  ", style=f"bold {theme.DELETED}")
            t.append(p)
            console.print(t)
        console.print()
        click.confirm("Mark these files for delete?", abort=True)
        console.print()

    args = ["delete"]
    if cl:
        args += ["-c", cl]
    args += [local_to_depot(f) for f in files]

    try:
        raw = run_p4(args)
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    for line in raw.splitlines():
        if " - opened for delete" in line:
            depot_path = line.split("#")[0]
            rel = any_to_rel(depot_path)
            t = Text()
            t.append("  deleted  ", style=f"bold {theme.DELETED}")
            t.append(rel)
            console.print(t)
        else:
            console.print(f"  [dim]{line}[/dim]")
