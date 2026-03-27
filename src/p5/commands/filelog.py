"""p5 filelog — git-log style file history."""
from __future__ import annotations

from datetime import datetime, timezone

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_depot_path
from p5.p4 import P4Error, run_p4_tagged
from p5.workspace import any_to_rel, check_cwd_in_workspace, local_to_depot

console = Console()


@click.command()
@click.argument("file", shell_complete=complete_depot_path)
@click.option("-n", "--max-revisions", "max_rev", default=20, show_default=True,
              help="Max number of revisions to show")
def filelog_cmd(file: str, max_rev: int) -> None:
    """Show revision history of a file (git log style)."""
    check_cwd_in_workspace()
    depot_path = local_to_depot(file)
    rel        = any_to_rel(depot_path)

    try:
        records = run_p4_tagged(["filelog", "-m", str(max_rev), depot_path])
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    if not records:
        console.print("[dim]no history found[/dim]")
        return

    console.print(Text(rel, style=f"bold {theme.DIFF_HEADER}"))
    console.print()

    for rec in records:
        revs = rec.get("rev")
        if not isinstance(revs, list):
            revs = [revs] if revs else []
        changes  = rec.get("change") or []
        dates    = rec.get("time") or []
        users    = rec.get("user") or []
        descs    = rec.get("desc") or []
        actions  = rec.get("action") or []

        if not isinstance(changes, list):
            changes = [changes]
            dates   = [dates]   if not isinstance(dates, list)   else dates
            users   = [users]   if not isinstance(users, list)   else users
            descs   = [descs]   if not isinstance(descs, list)   else descs
            actions = [actions] if not isinstance(actions, list) else actions

        total = len(changes)
        for i, (rev, cl, ts, user, desc, action) in enumerate(
            zip(revs, changes, dates, users, descs, actions)
        ):
            is_last = i == total - 1

            # Format timestamp (p4 gives Unix epoch)
            try:
                dt_str = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                dt_str = str(ts)

            bullet = "●"
            connector = "│" if not is_last else " "

            # Header line
            t = Text()
            t.append(f"{bullet} ", style=f"bold {theme.CL_NUM}")
            t.append(f"#{rev}  ", style=f"bold {theme.BRANCH}")
            t.append(f"CL {cl}  ", style=theme.CL_NUM)
            t.append(dt_str, style=theme.DATE)
            t.append("  ")
            t.append(user or "", style=theme.AUTHOR)
            if action:
                color = theme.ACTION_COLOR.get(action, "white")
                t.append(f"  [{action}]", style=f"dim {color}")
            console.print(t)

            # Description
            desc_lines = (desc or "").strip().splitlines()
            for dl in desc_lines[:2]:  # Show up to 2 lines
                console.print(Text(f"{connector}  {dl}", style="dim"))

            if not is_last:
                console.print(Text(connector, style="dim"))
