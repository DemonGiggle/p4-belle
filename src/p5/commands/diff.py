"""p5 diff — colored unified diff output."""
from __future__ import annotations

import os
import re

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.workspace import any_to_rel, check_cwd_in_workspace

console = Console()

_HUNK_RE   = re.compile(r"^(@@ .+? @@)(.*)")
_HEADER_RE = re.compile(r"^==== (.+?)#(\d+) ")


def _render_diff(raw: str) -> None:
    """Parse and pretty-print a p4 diff output."""
    for line in raw.splitlines():
        # p4 diff file header: ==== //depot/.../foo.cpp#41 (text)
        m = _HEADER_RE.match(line)
        if m:
            rel = any_to_rel(m.group(1))
            rev = m.group(2)
            console.rule(
                Text(f"diff {rel}  (#{rev} \u2192 working copy)", style=theme.DIFF_HEADER),
                style="dim",
            )
            continue

        if line.startswith("--- "):
            console.print(Text(line, style=theme.DIFF_DEL))
        elif line.startswith("+++ "):
            console.print(Text(line, style=theme.DIFF_ADD))
        elif line.startswith("@@"):
            hm = _HUNK_RE.match(line)
            if hm:
                t = Text()
                t.append(hm.group(1), style=f"bold {theme.DIFF_HUNK}")
                t.append(hm.group(2), style="dim")
                console.print(t)
            else:
                console.print(Text(line, style=f"bold {theme.DIFF_HUNK}"))
        elif line.startswith("+"):
            console.print(Text(line, style=theme.DIFF_ADD))
        elif line.startswith("-"):
            console.print(Text(line, style=theme.DIFF_DEL))
        else:
            console.print(line)


def _get_cl_files(cl: str) -> list[str]:
    """Get depot file paths opened in a specific changelist."""
    try:
        records = run_p4_tagged(["opened", "-c", cl])
    except P4Error:
        return []
    return [r["depotFile"] for r in records if r.get("depotFile")]


def _get_changed_files(path: str) -> list[str] | None:
    """Use 'p4 diff -sa' to find files that actually differ.

    Returns a list of depot paths, or None if the pre-filter failed
    (caller should fall back to full diff).
    """
    try:
        records = run_p4_tagged(["diff", "-sa", path])
        return [r["depotFile"] for r in records if r.get("depotFile")]
    except P4Error:
        return None


from p5.completion import complete_opened_files, complete_pending_cls  # noqa: E402


@click.command()
@click.argument("files", nargs=-1, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Diff files in a specific changelist",
              shell_complete=complete_pending_cls)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Diff all opened files across the entire depot")
def diff_cmd(files: tuple[str, ...], cl: str | None, show_all: bool) -> None:
    """Show colored diff of opened files."""
    if not show_all:
        check_cwd_in_workspace()

    # Determine which files to diff
    if files:
        # Explicit files — use them directly
        diff_targets = [os.path.abspath(f) for f in files]
    elif cl:
        # Specific changelist — get its files via p4 opened -c
        diff_targets = _get_cl_files(cl)
        if not diff_targets:
            console.print("[dim]no files in this changelist[/dim]")
            return
    elif show_all:
        diff_targets = ["//..."]
    else:
        diff_targets = [os.getcwd().rstrip("/") + "/..."]

    # Fast path for directory-wide diffs: pre-filter to only files that
    # actually differ. 'p4 diff -sa' is fast (stat only, no content read).
    if not files and not cl:
        changed = _get_changed_files(diff_targets[0])
        if changed is not None:
            if not changed:
                console.print("[dim]no differences[/dim]")
                return
            diff_targets = changed

    # Run the actual unified diff
    args = ["diff", "-du"] + diff_targets
    try:
        raw = run_p4(args)
    except P4Error as e:
        if "not opened" in str(e).lower() or not str(e).strip():
            console.print("[dim]no differences[/dim]")
            return
        raise

    if not raw.strip():
        console.print("[dim]no differences[/dim]")
        return

    _render_diff(raw)
