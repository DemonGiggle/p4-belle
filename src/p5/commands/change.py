"""p5 change — create or edit a changelist."""
from __future__ import annotations

import click
from rich.console import Console

from p5.p4 import P4Error, run_p4

console = Console()


@click.command()
@click.argument("cl_number", default=None, required=False)
@click.option("-d", "--delete", "do_delete", is_flag=True, help="Delete an empty changelist")
def change_cmd(cl_number: str | None, do_delete: bool) -> None:
    """Create a new changelist or edit an existing one.

    With no arguments, opens an editor to create a new changelist.
    With a CL number, opens that changelist for editing.
    """
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

    args = ["change"]
    if cl_number:
        args.append(cl_number)

    try:
        # Pass through to p4 which opens $EDITOR
        import subprocess
        subprocess.run(["p4"] + args[1:] if cl_number else ["p4", "change"])
    except Exception as e:
        console.print(f"[red]error:[/red] {e}")
