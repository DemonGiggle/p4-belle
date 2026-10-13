"""p5 revert — discard local changes, with confirmation."""
from __future__ import annotations

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_opened_files, complete_pending_cls
from p5.dummy_data import render_revert
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel, check_cwd_in_workspace, local_to_depot

console = Console()


@click.command()
@click.argument("files", nargs=-1, required=False, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Only revert files in changelist",
              shell_complete=complete_pending_cls)
@click.option("-a", "--unchanged", is_flag=True,
              help="Only revert files that are unchanged (passthrough to p4 revert -a)")
@click.option("-y", "--yes", "no_confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--dummy-data", is_flag=True,
              help="Display sample output instead of querying Perforce")
def revert_cmd(files: tuple[str, ...], cl: str | None, unchanged: bool,
               no_confirm: bool, dummy_data: bool) -> None:
    """Revert local change(s) (with confirmation)."""
    if dummy_data:
        render_revert(files or ("src/auth/login.cpp", "src/net/socket.cpp"))
        return

    if not files:
        raise click.UsageError("Missing argument 'FILES...'")

    check_cwd_in_workspace()
    depot_paths = [local_to_depot(f) for f in files]
    rel_paths = [any_to_rel(dp) for dp in depot_paths]

    if not no_confirm:
        console.print(Text("Files to be reverted:", style=theme.SECTION))
        for p in rel_paths:
            t = Text()
            t.append("  R  ", style=f"bold {theme.DELETED}")
            t.append(p)
            console.print(t)
        console.print()
        click.confirm("Revert these files?", abort=True)
        console.print()

    args = ["revert"]
    if unchanged:
        args.append("-a")
    if cl:
        args += ["-c", cl]
    args += depot_paths

    try:
        raw = run_p4(args)
    except P4Error as e:
        # Issue #10 convention: non-zero exit via ClickException, not silent return.
        raise click.ClickException(str(e))

    for line in raw.splitlines():
        if " - reverted" in line:
            depot_path = line.split("#")[0]
            rel = any_to_rel(depot_path)
            t = Text()
            t.append("  reverted  ", style=f"bold {theme.DELETED}")
            t.append(rel)
            console.print(t)
        else:
            console.print(f"  [dim]{line}[/dim]")
