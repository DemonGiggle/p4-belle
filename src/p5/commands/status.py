"""p5 status — git-like pending changes overview."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from p5 import theme
from p5.completion import complete_depot_path
from p5.p4 import P4Error, run_p4_tagged
from p5.workspace import Workspace, check_cwd_in_workspace, get_workspace

console = Console()

_debug = os.environ.get("P5_DEBUG", "").strip() not in ("", "0")
_INDEXED_KEY_RE = re.compile(r"^(.+?)\d+$")


def _dbg(msg: str) -> None:
    if _debug:
        print(f"[p5 status debug] {msg}", file=sys.stderr)


def _dbg_elapsed(label: str, t0: float) -> None:
    if _debug:
        elapsed = time.monotonic() - t0
        print(f"[p5 status debug] {label} ({elapsed:.2f}s)", file=sys.stderr)


def _letter(action: str) -> str:
    return theme.STATE_LETTER.get(action, action[0].upper())


def _color(action: str) -> str:
    return theme.ACTION_COLOR.get(action, "white")


def _render_file_line(action: str, rel_path: str) -> Text:
    letter = _letter(action)
    color  = _color(action)
    t = Text()
    t.append(f"  {letter}  ", style=f"bold {color}")
    t.append(rel_path)
    return t


def _to_cwd_rel(rec: dict) -> str:
    """Get a cwd-relative display path from a p4 record."""
    ws = get_workspace()
    cwd = os.getcwd()

    client_file = rec.get("clientFile", "")
    if client_file:
        if client_file.startswith("//"):
            client_prefix = "//" + ws.client_name + "/"
            if client_file.startswith(client_prefix):
                ws_rel = client_file[len(client_prefix):]
                abs_path = str(Path(ws.client_root) / ws_rel)
                return os.path.relpath(abs_path, cwd)
        else:
            return os.path.relpath(client_file, cwd)

    depot_file = rec.get("depotFile", "")
    prefix = ws.depot_prefix.rstrip("/") + "/"
    if depot_file.startswith(prefix):
        ws_rel = depot_file[len(prefix):]
        abs_path = str(Path(ws.client_root) / ws_rel)
        return os.path.relpath(abs_path, cwd)

    return depot_file


def _is_excluded(rel_path: str, excludes: tuple[str, ...]) -> bool:
    for ex in excludes:
        ex_clean = ex.rstrip("/")
        if ex_clean == ".":
            return True
        if rel_path == ex_clean or rel_path.startswith(ex_clean + "/"):
            return True
    return False


def _local_abs(rec: dict, ws: Workspace) -> str:
    """Return the absolute local path for a record, or ''."""
    client_file = rec.get("clientFile", "")
    if client_file:
        if client_file.startswith("//"):
            client_prefix = "//" + ws.client_name + "/"
            if client_file.startswith(client_prefix):
                return str(Path(ws.client_root) / client_file[len(client_prefix):])
        else:
            return client_file
    depot_file = rec.get("depotFile", "")
    prefix = ws.depot_prefix.rstrip("/") + "/"
    if depot_file.startswith(prefix):
        return str(Path(ws.client_root) / depot_file[len(prefix):])
    return ""


def _under(abs_path: str, root: str) -> bool:
    """True if abs_path is root itself or anywhere under root."""
    return abs_path == root or abs_path.startswith(root + os.sep)


def _run_reconcile_with_progress(reconcile_path: str) -> list[dict]:
    """Run p4 reconcile -n, streaming output and showing the current file
    in-place on a single stderr line so the user can see progress."""
    ws = get_workspace()
    client_prefix = "//" + ws.client_name + "/"
    cwd = os.getcwd()

    is_tty = sys.stderr.isatty()
    try:
        term_width = os.get_terminal_size().columns if is_tty else 80
    except OSError:
        term_width = 80

    cmd = ["p4", "-ztag", "reconcile", "-n", "-e", "-a", "-d", reconcile_path]
    _dbg(f"running (streaming): {' '.join(cmd)}")
    t0 = time.monotonic()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.DEVNULL,
    )

    records: list[dict] = []
    current: dict[str, str] = {}

    for raw_line in proc.stdout:  # type: ignore[union-attr]
        line = raw_line.rstrip("\n")
        if line.startswith("... "):
            parts = line[4:].split(" ", 1)
            key = parts[0]
            val = parts[1] if len(parts) > 1 else ""
            # Normalise indexed keys (depotFile0 → depotFile)
            m = _INDEXED_KEY_RE.match(key)
            if m:
                key = m.group(1)
            current[key] = val

            if key == "clientFile" and is_tty:
                # Convert to cwd-relative for display
                if val.startswith(client_prefix):
                    abs_local = str(Path(ws.client_root) / val[len(client_prefix):])
                    rel = os.path.relpath(abs_local, cwd)
                else:
                    rel = val
                label = f"  reconciling: {rel}"
                # Truncate from the left so the filename tail stays visible
                max_label = term_width - 1
                if len(label) > max_label:
                    label = "  reconciling: \u2026" + rel[-(max_label - 18):]
                print(f"\r{label:<{term_width}}", end="", flush=True, file=sys.stderr)
        else:
            if current:
                records.append(current)
                current = {}

    if current:
        records.append(current)

    proc.wait()

    if is_tty:
        # Erase the progress line
        print(f"\r{' ' * term_width}\r", end="", flush=True, file=sys.stderr)

    _dbg_elapsed(f"p4 reconcile (streaming) → {len(records)} record(s)", t0)
    return records


@click.command()
@click.argument("path", default=None, required=False,
                shell_complete=complete_depot_path)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Show entire depot, not just current directory")
@click.option("-r", "--reconcile", "do_reconcile", is_flag=True,
              help="Also check for untracked edits/adds/deletes (slow — scans disk)")
@click.option("-x", "--exclude", "excludes", multiple=True,
              help="Exclude paths matching this prefix (repeatable)")
def status_cmd(
    path: str | None,
    show_all: bool,
    do_reconcile: bool,
    excludes: tuple[str, ...],
) -> None:
    """Show pending changes in the current directory (like git status).

    By default only shows files explicitly opened in p4 (fast).
    Use -r to also scan for untracked local changes.
    """
    _dbg(f"invoked: path={path!r} show_all={show_all!r} do_reconcile={do_reconcile!r} excludes={excludes!r}")

    t0 = time.monotonic()
    if not show_all:
        check_cwd_in_workspace()
    _dbg_elapsed("check_cwd_in_workspace", t0)

    t0 = time.monotonic()
    ws = get_workspace()
    _dbg_elapsed("get_workspace (p4 info / client -o)", t0)

    # Determine the local directory root to scope results (None = whole client).
    if show_all:
        filter_root: str | None = None
    elif path is not None:
        filter_root = os.path.abspath(path)
    else:
        filter_root = os.getcwd()
    _dbg(f"filter_root={filter_root!r}")

    # p4 opened with no path is a pure server metadata lookup — no local path
    # resolution, instant regardless of workspace size.
    t0 = time.monotonic()
    _dbg("running: p4 opened")
    try:
        opened = run_p4_tagged(["opened"])
    except P4Error as e:
        if "not opened" in str(e).lower():
            opened = []
        else:
            raise
    _dbg_elapsed(f"p4 opened → {len(opened)} record(s)", t0)

    # Filter to the requested subtree locally — O(F) string ops, no server call.
    if filter_root is not None:
        before = len(opened)
        opened = [r for r in opened if _under(_local_abs(r, ws), filter_root)]
        _dbg(f"local filter: {before} → {len(opened)} record(s) under {filter_root!r}")

    # Reconcile is opt-in: it walks the entire local tree (slow).
    reconcile: list[dict] = []
    if do_reconcile:
        reconcile_path = (
            "//..."
            if filter_root is None
            else filter_root.rstrip(os.sep) + "/..."
        )
        reconcile = _run_reconcile_with_progress(reconcile_path)

    # --- Render -----------------------------------------------------------------

    # Group opened files by changelist, applying excludes
    cl_files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rec in opened:
        cl     = rec.get("change", "default")
        rel    = _to_cwd_rel(rec)
        action = rec.get("action", "edit")
        if excludes and _is_excluded(rel, excludes):
            continue
        cl_files[cl].append((action, rel))

    # Print default CL first
    if "default" in cl_files:
        console.print(Text("Changes to be submitted (default changelist):", style=theme.SECTION))
        for action, p in cl_files["default"]:
            console.print(_render_file_line(action, p))
        console.print()

    # Other named CLs
    other_cls = [cl for cl in cl_files if cl != "default"]
    if other_cls:
        console.print(Text("Other pending changelists:", style=theme.SECTION))
        for cl in other_cls:
            console.print(f"  [bold blue]CL {cl}[/bold blue]")
            for action, p in cl_files[cl]:
                t = Text("    ")
                t.append(_letter(action), style=f"bold {_color(action)}")
                t.append(f"  {p}")
                console.print(t)
        console.print()

    # Reconcile / untracked results
    filtered_reconcile: list[tuple[str, str]] = []
    for rec in reconcile:
        rel = _to_cwd_rel(rec)
        if excludes and _is_excluded(rel, excludes):
            continue
        filtered_reconcile.append((rel, rec.get("action", "?")))

    if not cl_files and not filtered_reconcile:
        console.print("[dim]nothing to commit, working tree clean[/dim]")
        return

    if filtered_reconcile:
        console.print(Text("Local changes not opened in p4:", style=theme.SECTION))
        for p, action in filtered_reconcile:
            if action not in theme.STATE_LETTER:
                letter = "?"
                color  = theme.UNTRACKED
            else:
                letter = _letter(action)
                color  = _color(action)
            t = Text()
            t.append(f"  {letter}  ", style=f"bold {color}")
            t.append(p)
            console.print(t)

    console.print()
    hint = "  [dim]use [/dim][bold]p4 edit <file>[/bold][dim] to open for edit, "
    hint += "[/dim][bold]p4 add <file>[/bold][dim] to mark new files, "
    hint += "[/dim][bold]p5 delete <file>[/bold][dim] to mark for delete"
    if not do_reconcile:
        hint += "  ([/dim][bold]p5 status -r[/bold][dim] to scan for untracked changes)"
    hint += "[/dim]"
    console.print(hint)
