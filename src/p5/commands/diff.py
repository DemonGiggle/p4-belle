"""p5 diff — interactive TUI diff viewer for opened files."""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, RichLog, Static, Tab, Tabs

from p5 import theme
from p5.completion import complete_opened_files, complete_pending_cls
from p5.diff_utils import join_rendered_diffs, make_unified_diff, render_side_by_side
from p5.dummy_data import build_diff_cache, build_diff_groups
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.tui.widgets import FastRichLog
from p5.workspace import any_to_rel, check_cwd_in_workspace, get_workspace

_debug = os.environ.get("P5_DEBUG", "").strip() not in ("", "0")


def _dbg(msg: str) -> None:
    if _debug:
        print(f"[p5 diff debug] {msg}", file=sys.stderr)


_HUNK_RE = re.compile(r"^(@@ .+? @@)(.*)")

GROUP_MODIFIED = "modified"
GROUP_ADDED = "added"
GROUP_DELETED = "deleted"
_GROUPS = [GROUP_MODIFIED, GROUP_ADDED, GROUP_DELETED]
_GROUP_LABELS = {
    GROUP_MODIFIED: "Modified",
    GROUP_ADDED: "Added",
    GROUP_DELETED: "Deleted",
}


@dataclass
class FileEntry:
    depot_path: str
    local_path: str  # absolute local path; may be empty for deleted files
    action: str      # p4 action: edit, add, delete, branch, move/add, move/delete
    file_type: str   # p4 type field, e.g. 'text', 'binary+x'
    display_path: str = ""

    @property
    def is_binary(self) -> bool:
        base = self.file_type.split("+")[0].lower()
        return base in ("binary", "ubinary", "apple", "resource")

    @property
    def group(self) -> str:
        if self.action in ("add", "branch", "move/add"):
            return GROUP_ADDED
        if self.action in ("delete", "move/delete"):
            return GROUP_DELETED
        return GROUP_MODIFIED

    @property
    def display_name(self) -> str:
        return self.display_path or any_to_rel(self.depot_path)


# ---------------------------------------------------------------------------
# Diff fetching
# ---------------------------------------------------------------------------

def _style_unified_diff(raw: str) -> list[tuple[str, str]]:
    """Apply rich styles to unified diff lines (from difflib or any standard source)."""
    result: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.rstrip("\n")
        if line.startswith("@@"):
            m = _HUNK_RE.match(line)
            styled = (m.group(1) + m.group(2)) if m else line
            result.append((styled, f"bold {theme.DIFF_HUNK}"))
        elif line.startswith(("--- ", "+++ ")):
            result.append((line, "dim"))
        elif line.startswith("+"):
            result.append((line, theme.DIFF_ADD))
        elif line.startswith("-"):
            result.append((line, theme.DIFF_DEL))
        else:
            result.append((line, ""))
    return result or [("(no differences)", "dim")]


def _fetch_diff(entry: FileEntry, *, ignore_whitespace: bool = False) -> str:
    """Return the entry's diff as unified text.

    For modified files, retrieves the depot base via 'p4 print' and computes
    the diff locally using difflib — avoiding 'p4 diff' which can hang when
    P4DIFF is set to an interactive tool.
    """
    if entry.is_binary:
        return "(binary file — diff not shown)"

    if entry.group == GROUP_MODIFIED:
        depot_spec = f"{entry.depot_path}#have"
        _dbg(f"running: p4 print -q {depot_spec}")
        try:
            depot_raw = run_p4(["print", "-q", depot_spec])
            _dbg(f"p4 print returned {len(depot_raw)} bytes")
        except P4Error as e:
            _dbg(f"p4 print failed: {e}")
            return f"(cannot get depot version: {e})"

        try:
            local_raw = Path(entry.local_path).read_text(errors="replace")
        except OSError as e:
            return f"(cannot read local file: {e})"

        return make_unified_diff(
            depot_raw,
            local_raw,
            fromfile=f"a/{entry.display_name}",
            tofile=f"b/{entry.display_name}",
            ignore_whitespace=ignore_whitespace,
        ) or "(no differences)"

    if entry.group == GROUP_ADDED:
        try:
            text = Path(entry.local_path).read_text(errors="replace")
        except OSError as e:
            return f"(cannot read: {e})"
        return make_unified_diff(
            "",
            text,
            fromfile="/dev/null",
            tofile=f"b/{entry.display_name}",
            ignore_whitespace=ignore_whitespace,
        ) or "(no differences)"

    # GROUP_DELETED — read last depot revision
    _dbg(f"running: p4 print -q {entry.depot_path}")
    try:
        raw = run_p4(["print", "-q", entry.depot_path])
        _dbg(f"p4 print returned {len(raw)} bytes")
    except P4Error as e:
        return f"(cannot retrieve depot content: {e})"
    return make_unified_diff(
        raw,
        "",
        fromfile=f"a/{entry.display_name}",
        tofile="/dev/null",
        ignore_whitespace=ignore_whitespace,
    ) or "(no differences)"


def _diff_stats(diff_lines: list[tuple[str, str]]) -> tuple[int, int]:
    added = sum(1 for t, _ in diff_lines if t.startswith("+"))
    removed = sum(1 for t, _ in diff_lines if t.startswith("-"))
    return added, removed


# ---------------------------------------------------------------------------
# Textual TUI app
# ---------------------------------------------------------------------------

_CSS = """\
Tabs { dock: top; }
Footer { dock: bottom; height: 1; }
#main { height: 1fr; }
#file-list {
    width: 32;
    border: none;
    border-right: tall $panel;
    padding: 0 1;
}
#diff-panel { width: 1fr; }
#file-header {
    height: 1;
    background: $boost;
    padding: 0 1;
}
#diff-log { border: none; height: 1fr; }
"""


class DiffApp(App):
    CSS = _CSS

    BINDINGS = [
        Binding("n", "next_file", "Next file"),
        Binding("p", "prev_file", "Prev file"),
        Binding("[", "prev_tab", "Prev tab"),
        Binding("]", "next_tab", "Next tab"),
        Binding("j", "scroll_down", "Scroll ↓", show=False),
        Binding("k", "scroll_up", "Scroll ↑", show=False),
        Binding("b", "toggle_side_by_side", "View", show=False),
        Binding("w", "toggle_whitespace", "Whitespace", show=False),
        Binding("ctrl+f", "page_down", "Page ↓", show=False),
        Binding("ctrl+b", "page_up", "Page ↑", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        groups: dict[str, list[FileEntry]],
        initial_cache: dict[str, str] | None = None,
        *,
        ignore_whitespace: bool = False,
        side_by_side: bool = False,
    ) -> None:
        super().__init__()
        self.groups = groups
        self._indices: dict[str, int] = {g: 0 for g in _GROUPS}
        self._cache: dict[tuple[str, bool, bool], str] = {
            (path, False, False): raw for path, raw in (initial_cache or {}).items()
        }
        self._active_group: str = next(
            (g for g in _GROUPS if groups.get(g)), GROUP_MODIFIED
        )
        self._ignore_whitespace = ignore_whitespace
        self._side_by_side = side_by_side

    def compose(self) -> ComposeResult:
        yield Tabs(
            *[
                Tab(f"{_GROUP_LABELS[g]}  {len(self.groups.get(g, []))}", id=g)
                for g in _GROUPS
            ]
        )
        with Horizontal(id="main"):
            yield FastRichLog(id="file-list", highlight=False, markup=False, wrap=False, auto_scroll=False)
            with Vertical(id="diff-panel"):
                yield Static("", id="file-header")
                yield FastRichLog(id="diff-log", highlight=False, markup=False, wrap=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tabs).active = self._active_group
        self._refresh_view()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tab is not None:
            self._active_group = str(event.tab.id)
            self._refresh_view()

    def _current_files(self) -> list[FileEntry]:
        return self.groups.get(self._active_group, [])

    def _refresh_view(self) -> None:
        files = self._current_files()
        header = self.query_one("#file-header", Static)
        log = self.query_one("#diff-log", RichLog)

        self._update_file_list(files)

        if not files:
            header.update(Text("  (no files in this category)", style="dim"))
            log.clear()
            return

        idx = self._indices[self._active_group]
        entry = files[idx]
        cache_key = (entry.depot_path, self._ignore_whitespace, self._side_by_side)

        if cache_key not in self._cache:
            self._cache[cache_key] = _fetch_diff(entry, ignore_whitespace=self._ignore_whitespace)

        raw_diff = self._cache[cache_key]
        diff_lines = _style_unified_diff(raw_diff)
        added, removed = _diff_stats(diff_lines)

        t = Text()
        t.append(f"  {entry.display_name}  [{idx + 1} / {len(files)}]")
        if entry.group == GROUP_MODIFIED:
            t.append(f"  +{added}", style=f"bold {theme.DIFF_ADD}")
            t.append(f" -{removed}", style=f"bold {theme.DIFF_DEL}")
        whitespace = "ignored" if self._ignore_whitespace else "significant"
        t.append(f"  whitespace: {whitespace}", style="dim")
        t.append(
            f"  view: {'side-by-side' if self._side_by_side else 'unified'}",
            style="dim",
        )
        header.update(t)

        log.clear()
        if self._side_by_side:
            for line in render_side_by_side(raw_diff, ignore_whitespace=self._ignore_whitespace):
                log.write(line)
        else:
            for text, style in diff_lines:
                log.write(Text(text, style=style) if style else text)

    def _update_file_list(self, files: list[FileEntry]) -> None:
        idx = self._indices[self._active_group]
        log = self.query_one("#file-list", RichLog)
        log.clear()
        for i, entry in enumerate(files):
            t = Text(no_wrap=True, overflow="ellipsis")
            if i == idx:
                t.append("\u25b6 ", style=f"bold {theme.MODIFIED}")
                t.append(entry.display_name, style="bold")
            else:
                t.append("  " + entry.display_name, style="dim")
            log.write(t)
        # Scroll to keep the selected entry visible
        log.scroll_to(y=idx, animate=False)

    def action_next_file(self) -> None:
        files = self._current_files()
        if files:
            self._indices[self._active_group] = (self._indices[self._active_group] + 1) % len(files)
            self._refresh_view()

    def action_prev_file(self) -> None:
        files = self._current_files()
        if files:
            self._indices[self._active_group] = (self._indices[self._active_group] - 1) % len(files)
            self._refresh_view()

    def action_next_tab(self) -> None:
        idx = _GROUPS.index(self._active_group)
        self.query_one(Tabs).active = _GROUPS[(idx + 1) % len(_GROUPS)]

    def action_prev_tab(self) -> None:
        idx = _GROUPS.index(self._active_group)
        self.query_one(Tabs).active = _GROUPS[(idx - 1) % len(_GROUPS)]

    def action_scroll_down(self) -> None:
        self.query_one("#diff-log", RichLog).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#diff-log", RichLog).scroll_up()

    def action_page_down(self) -> None:
        self.query_one("#diff-log", RichLog).scroll_page_down()

    def action_page_up(self) -> None:
        self.query_one("#diff-log", RichLog).scroll_page_up()

    def action_toggle_whitespace(self) -> None:
        self._ignore_whitespace = not self._ignore_whitespace
        self._refresh_view()

    def action_toggle_side_by_side(self) -> None:
        self._side_by_side = not self._side_by_side
        self._refresh_view()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _build_entries(opened: list[dict]) -> list[FileEntry]:
    ws = get_workspace()
    entries: list[FileEntry] = []
    for rec in opened:
        depot = rec.get("depotFile", "")
        action = rec.get("action", "edit")
        file_type = rec.get("type", "")
        client_file = rec.get("clientFile", "")

        if client_file.startswith("//"):
            client_prefix = "//" + ws.client_name + "/"
            local = (
                str(Path(ws.client_root) / client_file[len(client_prefix):])
                if client_file.startswith(client_prefix)
                else ""
            )
        else:
            local = client_file

        entries.append(FileEntry(
            depot_path=depot,
            local_path=local,
            action=action,
            file_type=file_type,
        ))
    return entries


def _scope_args(p4_path: str | None, files: tuple[str, ...]) -> list[str]:
    if p4_path is not None:
        return [p4_path]
    return [os.path.abspath(f) for f in files]


def _print_no_differences() -> None:
    Console().print("[dim]no differences[/dim]")


def _load_opened_records(p4_path: str | None, files: tuple[str, ...], cl: str | None) -> list[dict]:
    try:
        if p4_path is not None:
            p4_opened_args = ["opened"]
            if cl:
                p4_opened_args += ["-c", cl]
            p4_opened_args.append(p4_path)
            _dbg(f"running: p4 {' '.join(p4_opened_args)}")
            return run_p4_tagged(p4_opened_args)

        opened: list[dict] = []
        for f in files:
            _dbg(f"running: p4 opened {f}")
            try:
                opened += run_p4_tagged(["opened", os.path.abspath(f)])
            except P4Error:
                pass
        return opened
    except P4Error as e:
        if "not opened" in str(e).lower():
            return []
        raise


def _run_cli_diff(
    p4_path: str | None,
    files: tuple[str, ...],
    cl: str | None,
    *,
    ignore_whitespace: bool,
    side_by_side: bool,
) -> None:
    if ignore_whitespace or side_by_side:
        opened = _load_opened_records(p4_path, files, cl)
        if not opened:
            Console().print("[dim]no files open[/dim]")
            return
        if side_by_side:
            rendered_parts: list[str] = []
            for entry in _build_entries(opened):
                raw = _fetch_diff(entry, ignore_whitespace=ignore_whitespace)
                if raw == "(no differences)":
                    continue
                rendered_parts.append(
                    "\n".join(render_side_by_side(raw, ignore_whitespace=ignore_whitespace))
                )
            rendered = "\n\n".join(rendered_parts)
            rendered = rendered + ("\n" if rendered else "")
        else:
            rendered = join_rendered_diffs(
                _fetch_diff(entry, ignore_whitespace=True)
                for entry in _build_entries(opened)
            )
        if not rendered:
            _print_no_differences()
            return
        click.echo(rendered, nl=False)
        return

    scope_args = _scope_args(p4_path, files)

    if cl:
        opened_args = ["opened", "-c", cl, *scope_args]
        _dbg(f"running: p4 {' '.join(opened_args)}")
        try:
            opened = run_p4_tagged(opened_args)
        except P4Error as e:
            if "not opened" in str(e).lower():
                opened = []
            else:
                raise
        if not opened:
            Console().print("[dim]no files open[/dim]")
            return
        diff_targets = [rec.get("depotFile") or rec.get("clientFile", "") for rec in opened]
    else:
        diff_targets = scope_args
        diff_sa_args = ["diff", "-sa", *scope_args]
        _dbg(f"running: p4 {' '.join(diff_sa_args)}")
        try:
            changed = run_p4_tagged(diff_sa_args)
        except P4Error:
            changed = None
        else:
            if not changed:
                _print_no_differences()
                return

    diff_du_args = ["diff", "-du", *diff_targets]
    _dbg(f"running: p4 {' '.join(diff_du_args)}")
    try:
        raw = run_p4(diff_du_args)
    except P4Error as e:
        if "not opened" in str(e).lower():
            _print_no_differences()
            return
        raise

    if not raw.strip():
        _print_no_differences()
        return

    click.echo(raw, nl=not raw.endswith("\n"))


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

@click.command()
@click.argument("files", nargs=-1, shell_complete=complete_opened_files)
@click.option("-c", "--cl", default=None, help="Diff files in a specific changelist",
              shell_complete=complete_pending_cls)
@click.option("-a", "--all", "show_all", is_flag=True,
              help="Diff all opened files across the entire depot")
@click.option("-w", "--ignore-whitespace", is_flag=True,
              help="Ignore whitespace-only changes when diffing")
@click.option("--side-by-side", is_flag=True,
              help="Render diffs in side-by-side view")
@click.option("--dummy-data", is_flag=True,
              help="Display sample output instead of querying Perforce")
def diff_cmd(
    files: tuple[str, ...],
    cl: str | None,
    show_all: bool,
    ignore_whitespace: bool,
    side_by_side: bool,
    dummy_data: bool,
) -> None:
    """Browse diffs of opened files in an interactive TUI."""
    _dbg(
        f"invoked: files={files!r} cl={cl!r} show_all={show_all!r} "
        f"ignore_whitespace={ignore_whitespace!r} side_by_side={side_by_side!r}"
    )

    if dummy_data:
        DiffApp(
            build_diff_groups(),
            initial_cache=build_diff_cache(),
            ignore_whitespace=ignore_whitespace,
            side_by_side=side_by_side,
        ).run()
        return

    if not show_all:
        check_cwd_in_workspace()

    # Resolve scope to a p4 path (or None for explicit file list)
    if show_all:
        p4_path: str | None = "//..."
    elif not files:
        p4_path = os.getcwd().rstrip("/") + "/..."
    else:
        p4_path = None

    _dbg(f"p4_path={p4_path!r}")

    if not sys.stdout.isatty():
        _run_cli_diff(
            p4_path,
            files,
            cl,
            ignore_whitespace=ignore_whitespace,
            side_by_side=side_by_side,
        )
        return

    opened = _load_opened_records(p4_path, files, cl)

    _dbg(f"total opened records: {len(opened)}")

    if not opened:
        Console().print("[dim]no files open[/dim]")
        return

    entries = _build_entries(opened)
    groups: dict[str, list[FileEntry]] = {g: [] for g in _GROUPS}
    for e in entries:
        groups[e.group].append(e)

    _dbg(
        f"groups: M={len(groups[GROUP_MODIFIED])} "
        f"A={len(groups[GROUP_ADDED])} "
        f"D={len(groups[GROUP_DELETED])}"
    )

    DiffApp(
        groups,
        ignore_whitespace=ignore_whitespace,
        side_by_side=side_by_side,
    ).run()
