"""p5 diff — colored unified diff output."""
from __future__ import annotations

import re

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.p4 import P4Error, run_p4
from p5.workspace import any_to_rel

console = Console()

_HUNK_RE   = re.compile(r"^(@@ .+? @@)(.*)")
_HEADER_RE = re.compile(r"^==== (.+?)#(\d+) ")


def _render_diff(raw: str) -> None:
    """Parse and pretty-print a p4 diff output."""
    current_file: str | None = None

    for line in raw.splitlines():
        # p4 diff file header: ==== //depot/.../foo.cpp#41 (text)
        m = _HEADER_RE.match(line)
        if m:
            rel = any_to_rel(m.group(1))
            rev = m.group(2)
            console.rule(
                Text(f"diff {rel}  (#{rev} → working copy)", style=theme.DIFF_HEADER),
                style="dim",
            )
            current_file = rel
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


from p5.completion import complete_opened_files, complete_pending_cls  # noqa: E402


@click.command()
@click.argument("files", nargs=-1, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Diff files in a specific changelist",
              shell_complete=complete_pending_cls)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Diff all opened files across the entire depot")
def diff_cmd(files: tuple[str, ...], cl: str | None, show_all: bool) -> None:
    """Show colored diff of opened files."""
    import os
    args = ["diff", "-du"]
    if cl:
        args += ["-c", cl]
    if files:
        args += [os.path.abspath(f) for f in files]
    elif show_all:
        args.append("//...")
    else:
        # Default to current directory, consistent with status/sync/changes
        args.append(os.getcwd().rstrip("/") + "/...")

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
