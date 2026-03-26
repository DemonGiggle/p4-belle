"""p5 ws — list and switch Perforce client workspaces."""
from __future__ import annotations

import os

import click
from rich.console import Console
from rich.text import Text

from p5 import theme as T
from p5.p4 import P4Error, run_p4, run_p4_tagged

console = Console()


def _get_current_client() -> str:
    try:
        info = run_p4_tagged(["info"])
        return info[0].get("clientName", "") if info else ""
    except P4Error:
        return os.environ.get("P4CLIENT", "")


@click.command()
@click.option("-u", "--user", default=None,
              help="List workspaces for a specific user (default: current user)")
@click.option("--no-tui", is_flag=True,
              help="Print workspace list without the interactive selector")
def ws_cmd(user: str | None, no_tui: bool) -> None:
    """List and switch Perforce client workspaces.

    Launches an interactive selector by default. Press Enter to switch,
    q to quit without switching.
    """
    if no_tui:
        _print_list(user)
        return

    try:
        from p5.tui.ws_app import WorkspaceApp
        app = WorkspaceApp(user=user)
        app.run()
        if app.selected_client:
            console.print(
                Text("  switched to  ", style=f"bold {T.ADDED}") +
                Text(app.selected_client, style=T.CL_NUM)
            )
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
    except ImportError as e:
        console.print(f"[red]error:[/red] textual is required: pip install textual\n{e}")


def _print_list(user: str | None) -> None:
    """Non-interactive fallback: print all workspaces as a table."""
    from rich.table import Table

    args = ["clients"]
    if user:
        args += ["-u", user]

    try:
        records = run_p4_tagged(args)
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    current = _get_current_client()

    table = Table(show_header=True, header_style=f"bold {T.SECTION}", box=None, padding=(0, 2))
    table.add_column("", width=2)
    table.add_column("Workspace", style=f"bold {T.CL_NUM}", no_wrap=True)
    table.add_column("Root")
    table.add_column("Host", style=T.AUTHOR)
    table.add_column("Last Access", style=T.DATE)

    from datetime import datetime, timezone

    def epoch(ts: str) -> str:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return ts or ""

    for r in records:
        name   = r.get("client", "")
        root   = r.get("Root", r.get("root", ""))
        host   = r.get("Host", r.get("host", ""))
        access = epoch(r.get("Access", r.get("access", "")))
        marker = f"[bold {T.ADDED}]◆[/bold {T.ADDED}]" if name == current else ""
        table.add_row(marker, name, root, host, access)

    console.print(table)
    console.print(f"\n  [dim]current:[/dim] [{T.CL_NUM}]{current}[/{T.CL_NUM}]")
    console.print(f"  [dim]to switch:[/dim]  p5 ws  (interactive)  or  p4 set P4CLIENT=<name>")
