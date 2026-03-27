"""p5 changes — interactive TUI for browsing changelists."""
from __future__ import annotations

import click
from rich.console import Console

from p5.p4 import P4Error

console = Console()


@click.command()
@click.option("-u", "--user", default=None, help="Filter by user")
@click.option("-m", "--max", "max_cls", default=50, show_default=True, help="Max CLs to load")
@click.option("-s", "--status", "cl_status", default="submitted",
              type=click.Choice(["submitted", "pending", "shelved", "all"]),
              help="Filter by CL status")
def changes_cmd(user: str | None, max_cls: int, cl_status: str) -> None:
    """Browse changelist history in an interactive TUI."""
    try:
        from p5.tui.changes_app import ChangesApp
        app = ChangesApp(
            user=user,
            max_cls=max_cls,
            cl_status=cl_status,
        )
        app.run()
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
    except ImportError as e:
        console.print(f"[red]error:[/red] textual is required: pip install textual\n{e}")
