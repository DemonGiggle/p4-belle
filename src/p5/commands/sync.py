"""p5 sync — sync workspace with colored summary."""
from __future__ import annotations

import re

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel, local_to_depot

console = Console()

# p4 sync output line patterns
_UPDATED_RE = re.compile(r"^(.+?)#(\d+) - updating (.+)")
_ADDED_RE   = re.compile(r"^(.+?)#(\d+) - added as (.+)")
_DELETED_RE = re.compile(r"^(.+?)#(\d+) - deleted as (.+)")
_REV_RE     = re.compile(r"^(.+?)#(\d+) - is sync'd at #(\d+)")


@click.command()
@click.argument("path", default="//...", required=False)
@click.option("-f", "--force", is_flag=True, help="Force resync")
@click.option("-n", "--dry-run", "dry_run", is_flag=True, help="Preview only")
def sync_cmd(path: str, force: bool, dry_run: bool) -> None:
    """Sync workspace to head (or a specific revision)."""
    args = ["sync"]
    if force:
        args.append("-f")
    if dry_run:
        args.append("-n")
    depot_path = local_to_depot(path) if not path.startswith("//") else path
    args.append(depot_path)

    console.print("[dim]Syncing to head...[/dim]")
    console.print()

    try:
        raw = run_p4(args, check=False)
    except P4Error as e:
        console.print(f"[red]error:[/red] {e}")
        return

    updated = added = deleted = 0

    for line in raw.splitlines():
        if m := _UPDATED_RE.match(line):
            rel = any_to_rel(m.group(1))
            rev = m.group(2)
            t = Text()
            t.append("  updated  ", style=f"bold {theme.SYNC_UPDATED}")
            t.append(f"{rel}  ")
            t.append(f"#{rev}", style=theme.DATE)
            console.print(t)
            updated += 1
        elif m := _ADDED_RE.match(line):
            rel = any_to_rel(m.group(1))
            rev = m.group(2)
            t = Text()
            t.append("  added    ", style=f"bold {theme.SYNC_ADDED}")
            t.append(f"{rel}  ")
            t.append(f"#{rev}", style=theme.DATE)
            console.print(t)
            added += 1
        elif m := _DELETED_RE.match(line):
            rel = any_to_rel(m.group(1))
            t = Text()
            t.append("  deleted  ", style=f"bold {theme.SYNC_DELETED}")
            t.append(rel)
            console.print(t)
            deleted += 1
        elif "up-to-date" in line:
            console.print("[dim]already up-to-date[/dim]")
            return

    if updated or added or deleted:
        console.print()
        parts: list[str] = []
        if updated:
            parts.append(f"[{theme.SYNC_UPDATED}]{updated} updated[/{theme.SYNC_UPDATED}]")
        if added:
            parts.append(f"[{theme.SYNC_ADDED}]{added} added[/{theme.SYNC_ADDED}]")
        if deleted:
            parts.append(f"[{theme.SYNC_DELETED}]{deleted} deleted[/{theme.SYNC_DELETED}]")
        console.print("  " + ", ".join(parts))
    else:
        console.print("[dim]already up-to-date[/dim]")
