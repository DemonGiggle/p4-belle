"""p5 change — manage changelists (TUI or edit)."""
from __future__ import annotations

import click
from rich.console import Console

from p5.completion import complete_pending_cls
from p5.dummy_data import build_change_diffs, build_change_files, render_change
from p5.p4 import P4Error, run_p4
from p5.workspace import check_cwd_in_workspace

console = Console()


@click.command()
@click.argument("cl_number", default=None, required=False, shell_complete=complete_pending_cls)
@click.option("-d", "--delete", "do_delete", is_flag=True, help="Delete an empty changelist")
@click.option("--dummy-data", is_flag=True,
              help="Display sample output instead of querying Perforce")
def change_cmd(cl_number: str | None, do_delete: bool, dummy_data: bool) -> None:
    """Manage changelists.

    \b
    With no arguments: interactive TUI to select files from the default
    changelist and group them into a new or existing CL.

    With a CL number: open that changelist for editing in $EDITOR.
    """
    if dummy_data:
        if cl_number is None and not do_delete:
            from p5.tui.change_app import ChangeApp
            ChangeApp(
                files=build_change_files(),
                demo_mode=True,
                demo_diffs=build_change_diffs(),
            ).run()
            return
        render_change(cl_number, do_delete)
        return

    if do_delete:
        if not cl_number:
            console.print("[red]error:[/red] specify a CL number to delete")
            return
        try:
            out = run_p4(["change", "-d", cl_number])
            console.print(f"[green]{out.strip()}[/green]")
        except P4Error as e:
            console.print(f"[red]error:[/red] {e}")
        return

    if cl_number:
        # Edit existing CL in $EDITOR
        try:
            import subprocess
            subprocess.run(["p4", "change", cl_number])
        except Exception as e:
            console.print(f"[red]error:[/red] {e}")
        return

    # No arguments — launch TUI for managing default changelist
    check_cwd_in_workspace()
    try:
        from p5.tui.change_app import ChangeApp
        app = ChangeApp()
        app.run()
    except ImportError as e:
        console.print(f"[red]error:[/red] textual is required: pip install textual\n{e}")
