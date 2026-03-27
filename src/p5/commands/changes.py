"""p5 changes — interactive TUI for browsing changelists."""
from __future__ import annotations

import os

import click
from rich.console import Console

from p5.p4 import P4Error

console = Console()


@click.command()
@click.argument("path", default=None, required=False)
@click.option("-u", "--user", default=None, help="Filter by user")
@click.option("-m", "--max", "max_cls", default=50, show_default=True, help="Max CLs to load")
@click.option("-s", "--status", "cl_status", default="submitted",
              type=click.Choice(["submitted", "pending", "shelved", "all"]),
              help="Filter by CL status")
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Show changes across entire depot")
def changes_cmd(path: str | None, user: str | None, max_cls: int,
                cl_status: str, show_all: bool) -> None:
    """Browse changelist history in an interactive TUI.

    By default, shows changes touching the current directory.
    Use -a / --all for the entire depot, or pass a specific path.
    """
    if show_all:
        p4_path = "//..."
    elif path is not None:
        if path.startswith("//"):
            p4_path = path.rstrip("/") + "/..."
        else:
            p4_path = os.path.abspath(path).rstrip("/") + "/..."
    else:
        p4_path = os.getcwd().rstrip("/") + "/..."

    try:
        from p5.tui.changes_app import ChangesApp
        app = ChangesApp(
            user=user,
            max_cls=max_cls,
            cl_status=cl_status,
            p4_path=p4_path,
        )
        app.run()
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
    except ImportError as e:
        console.print(f"[red]error:[/red] textual is required: pip install textual\n{e}")
