"""p5 sync — sync workspace with colored summary."""
from __future__ import annotations

import re

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_depot_path
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel

console = Console()

# p4 sync output line patterns
_UPDATED_RE = re.compile(r"^(.+?)#(\d+) - updating (.+)")
_ADDED_RE   = re.compile(r"^(.+?)#(\d+) - added as (.+)")
_DELETED_RE = re.compile(r"^(.+?)#(\d+) - deleted as (.+)")
_REV_RE     = re.compile(r"^(.+?)#(\d+) - is sync'd at #(\d+)")


@click.command()
@click.argument("path", default=None, required=False, shell_complete=complete_depot_path)
@click.option("-f", "--force", is_flag=True, help="Force resync")
@click.option("-n", "--dry-run", "dry_run", is_flag=True, help="Preview only")
@click.option("-a", "--all", "sync_all", is_flag=True, help="Sync entire depot (//...)")
def sync_cmd(path: str | None, force: bool, dry_run: bool, sync_all: bool) -> None:
    """Sync current directory to head (or a specific path/revision).

    With no arguments, syncs the current directory recursively.
    Use -a / --all to sync the entire depot.
    """
    import os
    args = ["sync"]
    if force:
        args.append("-f")
    if dry_run:
        args.append("-n")

    if sync_all:
        p4_path = "//..."
    elif path is None:
        # Default: sync current directory recursively using local path
        p4_path = os.getcwd().rstrip("/") + "/..."
    elif path.startswith("//"):
        # Depot path — pass through as-is
        p4_path = path
    else:
        # Local path — resolve to absolute; append /... for directories
        abs_path = os.path.abspath(path)
        if not re.search(r"#\d+$|@\d+$|@.+$", abs_path):
            from pathlib import Path as PathLib
            if PathLib(path).is_dir() or path.endswith("/") or path == ".":
                p4_path = abs_path.rstrip("/") + "/..."
            else:
                p4_path = abs_path
        else:
            p4_path = abs_path
    args.append(p4_path)

    display = "//..." if p4_path == "//..." else any_to_rel(p4_path.removesuffix("/...") or p4_path)
    console.print(f"[dim]Syncing {display} to head...[/dim]")
    console.print()

    try:
        raw = run_p4(args)
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
