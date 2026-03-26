"""Interactive TUI for browsing p4 changelists using Textual."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from p5 import theme as T
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.workspace import any_to_rel


# ─── Data ────────────────────────────────────────────────────────────────────

@dataclass
class ChangeRecord:
    cl: str
    date: str
    user: str
    description: str
    status: str = "submitted"
    files: list[tuple[str, str]] = field(default_factory=list)  # (action, rel_path)
    diff: str = ""
    loaded: bool = False


def _epoch_to_date(ts: str) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(ts)


def _fetch_changes(user: str | None, max_cls: int, cl_status: str) -> list[ChangeRecord]:
    args = ["changes", "-l", "-m", str(max_cls)]
    if cl_status != "all":
        args += ["-s", cl_status]
    if user:
        args += ["-u", user]
    args.append("//...")

    records = run_p4_tagged(args)
    result: list[ChangeRecord] = []
    for r in records:
        cl   = r.get("change", "?")
        ts   = r.get("time", "0")
        user_ = r.get("user", "")
        desc = (r.get("desc") or "").strip().replace("\n", " ")
        status = r.get("status", "submitted")
        result.append(ChangeRecord(
            cl=cl,
            date=_epoch_to_date(ts),
            user=user_,
            description=desc,
            status=status,
        ))
    return result


def _fetch_detail(rec: ChangeRecord) -> None:
    """Load files + diff for a changelist (mutates rec in place)."""
    if rec.loaded:
        return

    # Files
    try:
        file_records = run_p4_tagged(["describe", "-s", rec.cl])
        if file_records:
            fr = file_records[0]
            depot_files = fr.get("depotFile") or []
            actions     = fr.get("action")    or []
            if isinstance(depot_files, str):
                depot_files = [depot_files]
            if isinstance(actions, str):
                actions = [actions]
            rec.files = [
                (act, any_to_rel(dep))
                for dep, act in zip(depot_files, actions)
            ]
    except P4Error:
        pass

    # Diff
    try:
        if rec.status == "submitted":
            raw = run_p4(["describe", "-du", rec.cl])
        else:
            raw = run_p4(["describe", "-du", "-S", rec.cl])
        rec.diff = raw
    except P4Error:
        rec.diff = "(diff unavailable)"

    rec.loaded = True


# ─── Widgets ─────────────────────────────────────────────────────────────────

class ChangeItem(ListItem):
    """A single row in the changelist list view."""

    DEFAULT_CSS = """
    ChangeItem {
        height: 1;
        padding: 0 1;
    }
    ChangeItem:focus-within {
        background: $accent 20%;
    }
    ChangeItem.--highlight {
        background: $accent 30%;
    }
    """

    def __init__(self, rec: ChangeRecord) -> None:
        super().__init__()
        self.rec = rec

    def compose(self) -> ComposeResult:
        rec = self.rec
        # Fixed-width columns
        cl_col   = f"[bold blue]{rec.cl:>8}[/bold blue]"
        date_col = f"[dim]{rec.date}[/dim]"
        user_col = f"[yellow]{rec.user:<12}[/yellow]"
        desc_col = rec.description[:60]
        yield Static(f"{cl_col}  {date_col}  {user_col}  {desc_col}", markup=True)


class DiffView(ScrollableContainer):
    """Scrollable colored diff panel."""

    DEFAULT_CSS = """
    DiffView {
        border: solid $panel-lighten-1;
        padding: 0 1;
        overflow-y: scroll;
    }
    """

    def update_content(self, rec: ChangeRecord) -> None:
        self.remove_children()
        if not rec.loaded:
            self.mount(Static("[dim]Loading...[/dim]", markup=True))
            return

        lines: list[Widget] = []

        # Header
        lines.append(Static(
            f"[bold white]CL {rec.cl}[/bold white]  "
            f"[dim]{rec.date}[/dim]  "
            f"[yellow]{rec.user}[/yellow]",
            markup=True,
        ))
        lines.append(Static(f"  [white]{rec.description}[/white]", markup=True))
        lines.append(Static(""))

        # Files
        if rec.files:
            lines.append(Static(f"[bold white]Files:[/bold white]", markup=True))
            for action, path in rec.files:
                letter = T.STATE_LETTER.get(action, "M")
                color  = T.ACTION_COLOR.get(action, "white")
                lines.append(Static(
                    f"  [{color}]{letter}[/{color}]  {path}",
                    markup=True,
                ))
            lines.append(Static(""))

        # Diff
        if rec.diff:
            lines.append(Static(f"[bold white]Diff:[/bold white]", markup=True))
            lines.append(Static("─" * 60))
            for line in _colorize_diff(rec.diff):
                lines.append(Static(line, markup=True))

        for w in lines:
            self.mount(w)

    def clear(self) -> None:
        self.remove_children()
        self.mount(Static("[dim]Select a changelist to view details[/dim]", markup=True))


_HUNK_RE   = re.compile(r"^(@@ .+? @@)(.*)")
_HEADER_RE = re.compile(r"^==== (.+?)#(\d+)")


def _colorize_diff(raw: str) -> list[str]:
    """Convert raw p4 diff to Rich markup lines."""
    out: list[str] = []
    for line in raw.splitlines():
        # Skip the p4 describe header lines (Change/Date/User/etc.)
        if re.match(r"^(Change|Date|User|Client|Description|Files|Affected|Differences).*:", line):
            continue
        if _HEADER_RE.match(line):
            m = _HEADER_RE.match(line)
            rel = any_to_rel(m.group(1))
            out.append(f"[bold white]diff {rel}[/bold white]")
        elif line.startswith("--- "):
            out.append(f"[{T.DIFF_DEL}]{_esc(line)}[/{T.DIFF_DEL}]")
        elif line.startswith("+++ "):
            out.append(f"[{T.DIFF_ADD}]{_esc(line)}[/{T.DIFF_ADD}]")
        elif line.startswith("@@"):
            hm = _HUNK_RE.match(line)
            if hm:
                out.append(
                    f"[bold {T.DIFF_HUNK}]{_esc(hm.group(1))}[/bold {T.DIFF_HUNK}]"
                    f"[dim]{_esc(hm.group(2))}[/dim]"
                )
            else:
                out.append(f"[bold {T.DIFF_HUNK}]{_esc(line)}[/bold {T.DIFF_HUNK}]")
        elif line.startswith("+"):
            out.append(f"[{T.DIFF_ADD}]{_esc(line)}[/{T.DIFF_ADD}]")
        elif line.startswith("-"):
            out.append(f"[{T.DIFF_DEL}]{_esc(line)}[/{T.DIFF_DEL}]")
        else:
            out.append(_esc(line))
    return out


def _esc(s: str) -> str:
    """Escape Rich markup special chars in diff text."""
    return s.replace("[", "\\[").replace("]", "\\]")


# ─── Main App ────────────────────────────────────────────────────────────────

class ChangesApp(App):
    """Interactive Textual app for browsing p4 changes."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header-bar {
        height: 3;
        background: $panel;
        border-bottom: solid $panel-lighten-2;
        padding: 0 2;
        content-align: left middle;
    }

    #col-headers {
        height: 1;
        background: $panel-darken-1;
        padding: 0 1;
        color: $text-muted;
    }

    #list-view {
        height: 1fr;
        border: none;
    }

    #detail-view {
        height: 1fr;
        display: none;
    }

    #filter-bar {
        height: 3;
        background: $panel;
        border: solid $accent;
        padding: 0 2;
        display: none;
    }

    #filter-bar.visible {
        display: block;
    }

    Footer {
        height: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j,down",  "cursor_down",  "Down",   show=False),
        Binding("k,up",    "cursor_up",    "Up",     show=False),
        Binding("enter",   "expand",       "Expand"),
        Binding("escape",  "collapse",     "Back",   show=False),
        Binding("slash",   "start_filter", "Filter"),
        Binding("r",       "reload",       "Reload"),
        Binding("q",       "quit",         "Quit"),
    ]

    filter_text: reactive[str] = reactive("")
    detail_open: reactive[bool] = reactive(False)

    def __init__(
        self,
        user: str | None = None,
        max_cls: int = 50,
        cl_status: str = "submitted",
    ) -> None:
        super().__init__()
        self._user      = user
        self._max_cls   = max_cls
        self._cl_status = cl_status
        self._records: list[ChangeRecord] = []
        self._filtered: list[ChangeRecord] = []
        self._cursor: int = 0

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]p5 changes[/bold]  [dim]— Perforce changelist browser[/dim]",
            id="header-bar",
            markup=True,
        )
        yield Static(
            f"[dim]{'CL':>8}  {'Date':<10}  {'Author':<12}  Description[/dim]",
            id="col-headers",
            markup=True,
        )
        yield ListView(id="list-view")
        yield DiffView(id="detail-view")
        yield Static("", id="filter-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_changes()

    @work(thread=True)
    def _load_changes(self) -> None:
        try:
            records = _fetch_changes(self._user, self._max_cls, self._cl_status)
            self._records = records
            self._apply_filter()
        except P4Error as e:
            self.call_from_thread(
                self.query_one("#list-view", ListView).mount,
                ListItem(Static(f"[red]error: {e}[/red]", markup=True)),
            )

    def _apply_filter(self) -> None:
        q = self.filter_text.lower()
        if q:
            self._filtered = [
                r for r in self._records
                if q in r.cl or q in r.user.lower() or q in r.description.lower()
            ]
        else:
            self._filtered = list(self._records)

        self.call_from_thread(self._rebuild_list)

    def _rebuild_list(self) -> None:
        lv = self.query_one("#list-view", ListView)
        lv.clear()
        for rec in self._filtered:
            lv.append(ChangeItem(rec))
        if self._filtered:
            lv.index = 0

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_cursor_down(self) -> None:
        lv = self.query_one("#list-view", ListView)
        if self.detail_open:
            # Scroll diff
            dv = self.query_one("#detail-view", DiffView)
            dv.scroll_down(3)
        else:
            lv.action_cursor_down()

    def action_cursor_up(self) -> None:
        lv = self.query_one("#list-view", ListView)
        if self.detail_open:
            dv = self.query_one("#detail-view", DiffView)
            dv.scroll_up(3)
        else:
            lv.action_cursor_up()

    def action_expand(self) -> None:
        lv = self.query_one("#list-view", ListView)
        idx = lv.index
        if idx is None or idx >= len(self._filtered):
            return
        rec = self._filtered[idx]
        self._open_detail(rec)

    def action_collapse(self) -> None:
        if self.detail_open:
            self._close_detail()

    def action_start_filter(self) -> None:
        fb = self.query_one("#filter-bar", Static)
        fb.add_class("visible")
        fb.update("Filter: ")
        # Simple inline input via on_key below
        self._filtering = True
        self._filter_buf = ""

    def action_reload(self) -> None:
        lv = self.query_one("#list-view", ListView)
        lv.clear()
        self._records.clear()
        self._load_changes()

    def on_key(self, event) -> None:
        if getattr(self, "_filtering", False):
            if event.key == "enter":
                self._filtering = False
                self.filter_text = self._filter_buf
                fb = self.query_one("#filter-bar", Static)
                fb.remove_class("visible")
                self._apply_filter()
            elif event.key == "escape":
                self._filtering = False
                self._filter_buf = ""
                self.filter_text = ""
                fb = self.query_one("#filter-bar", Static)
                fb.remove_class("visible")
                self._apply_filter()
            elif event.key == "backspace":
                self._filter_buf = self._filter_buf[:-1]
                self.query_one("#filter-bar", Static).update(f"Filter: {self._filter_buf}_")
            elif event.character and event.character.isprintable():
                self._filter_buf += event.character
                self.query_one("#filter-bar", Static).update(f"Filter: {self._filter_buf}_")
            event.stop()

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        pass  # Enter key is handled by action_expand

    # ── Detail panel ─────────────────────────────────────────────────────────

    def _open_detail(self, rec: ChangeRecord) -> None:
        lv = self.query_one("#list-view", ListView)
        dv = self.query_one("#detail-view", DiffView)

        lv.display = False
        dv.display = True
        self.detail_open = True

        dv.clear()

        if not rec.loaded:
            self._load_detail(rec)
        else:
            dv.update_content(rec)

    def _close_detail(self) -> None:
        lv = self.query_one("#list-view", ListView)
        dv = self.query_one("#detail-view", DiffView)
        lv.display = True
        dv.display = False
        self.detail_open = False

    @work(thread=True)
    def _load_detail(self, rec: ChangeRecord) -> None:
        _fetch_detail(rec)
        dv = self.query_one("#detail-view", DiffView)
        self.call_from_thread(dv.update_content, rec)
