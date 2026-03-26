"""Interactive TUI for browsing p4 changelists using Textual."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, ListItem, ListView, Static

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
    files: list[tuple[str, str]] = field(default_factory=list)
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
        cl    = r.get("change", "?")
        ts    = r.get("time", "0")
        user_ = r.get("user", "")
        desc  = (r.get("desc") or "").strip().replace("\n", " ")
        status = r.get("status", "submitted")
        result.append(ChangeRecord(
            cl=cl, date=_epoch_to_date(ts), user=user_,
            description=desc, status=status,
        ))
    return result


def _fetch_detail(rec: ChangeRecord) -> None:
    """Load files + diff for a changelist (mutates rec in place)."""
    if rec.loaded:
        return

    try:
        file_records = run_p4_tagged(["describe", "-s", rec.cl])
        if file_records:
            fr          = file_records[0]
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
    DEFAULT_CSS = """
    ChangeItem { height: 1; padding: 0 1; }
    ChangeItem:focus-within { background: $accent 20%; }
    ChangeItem.--highlight  { background: $accent 30%; }
    """

    def __init__(self, rec: ChangeRecord) -> None:
        super().__init__()
        self.rec = rec

    def compose(self) -> ComposeResult:
        rec = self.rec
        cl_col   = f"[bold blue]{rec.cl:>8}[/bold blue]"
        date_col = f"[dim]{rec.date}[/dim]"
        user_col = f"[yellow]{rec.user:<12}[/yellow]"
        desc_col = rec.description[:60]
        yield Static(f"{cl_col}  {date_col}  {user_col}  {desc_col}", markup=True)


class DiffView(ScrollableContainer):
    DEFAULT_CSS = """
    DiffView {
        border: solid $panel-lighten-1;
        padding: 0 1;
        overflow-y: scroll;
    }
    """

    def update_content(self, rec: ChangeRecord) -> None:
        self.remove_children()

        widgets: list[Widget] = []
        widgets.append(Static(
            f"[bold white]CL {rec.cl}[/bold white]  "
            f"[dim]{rec.date}[/dim]  "
            f"[yellow]{rec.user}[/yellow]",
            markup=True,
        ))
        widgets.append(Static(f"  [white]{rec.description}[/white]", markup=True))
        widgets.append(Static(""))

        if rec.files:
            widgets.append(Static("[bold white]Files:[/bold white]", markup=True))
            for action, path in rec.files:
                letter = T.STATE_LETTER.get(action, "M")
                color  = T.ACTION_COLOR.get(action, "white")
                widgets.append(Static(f"  [{color}]{letter}[/{color}]  {path}", markup=True))
            widgets.append(Static(""))

        if rec.diff:
            widgets.append(Static("[bold white]Diff:[/bold white]", markup=True))
            widgets.append(Static("─" * 60))
            for line in _colorize_diff(rec.diff):
                widgets.append(Static(line, markup=True))

        for w in widgets:
            self.mount(w)

    def show_loading(self) -> None:
        self.remove_children()
        self.mount(Static("[dim]Loading...[/dim]", markup=True))

    def show_placeholder(self) -> None:
        self.remove_children()
        self.mount(Static(
            "[dim]Press [bold]Enter[/bold] on a changelist to view its diff[/dim]",
            markup=True,
        ))


_HUNK_RE   = re.compile(r"^(@@ .+? @@)(.*)")
_HEADER_RE = re.compile(r"^==== (.+?)#(\d+)")


def _colorize_diff(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        if re.match(r"^(Change|Date|User|Client|Description|Files|Affected|Differences).*:", line):
            continue
        if m := _HEADER_RE.match(line):
            rel = any_to_rel(m.group(1))
            out.append(f"[bold white]diff {_esc(rel)}[/bold white]")
        elif line.startswith("--- "):
            out.append(f"[{T.DIFF_DEL}]{_esc(line)}[/{T.DIFF_DEL}]")
        elif line.startswith("+++ "):
            out.append(f"[{T.DIFF_ADD}]{_esc(line)}[/{T.DIFF_ADD}]")
        elif line.startswith("@@"):
            if hm := _HUNK_RE.match(line):
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
    return s.replace("[", "\\[").replace("]", "\\]")


# ─── Main App ────────────────────────────────────────────────────────────────

class ChangesApp(App):
    CSS = """
    Screen { layout: vertical; }

    #header-bar {
        height: 1;
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

    #list-view  { height: 1fr; border: none; }
    #detail-view { height: 1fr; display: none; }

    #filter-bar {
        height: 1;
        background: $panel;
        padding: 0 2;
        display: none;
        color: $accent;
    }
    #filter-bar.active { display: block; }

    Footer { height: 1; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j",      "cursor_down",  "Down",   show=False),
        Binding("down",   "cursor_down",  "Down",   show=False),
        Binding("k",      "cursor_up",    "Up",     show=False),
        Binding("up",     "cursor_up",    "Up",     show=False),
        Binding("escape", "collapse",     "Back",   show=True),
        Binding("slash",  "start_filter", "Filter", show=True),
        Binding("r",      "reload",       "Reload", show=True),
        Binding("q",      "quit",         "Quit",   show=True),
    ]

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
        self._records:  list[ChangeRecord] = []
        self._filtered: list[ChangeRecord] = []
        self._filter_buf: str = ""
        self._filtering: bool = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]p5 changes[/bold]  [dim]— Perforce changelist browser[/dim]",
            id="header-bar", markup=True,
        )
        yield Static(
            f"[dim]{'CL':>8}  {'Date':<10}  {'Author':<12}  Description[/dim]",
            id="col-headers", markup=True,
        )
        yield ListView(id="list-view")
        yield DiffView(id="detail-view")
        yield Static("", id="filter-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_changes()

    # ── Loading ───────────────────────────────────────────────────────────────

    @work(thread=True)
    def _load_changes(self) -> None:
        try:
            records = _fetch_changes(self._user, self._max_cls, self._cl_status)
            self._records = records
            self._run_filter()
            self.call_from_thread(self._rebuild_list)
        except P4Error as e:
            self.call_from_thread(self._show_error, str(e))

    def _show_error(self, msg: str) -> None:
        from textual.widgets import ListItem
        lv = self.query_one("#list-view", ListView)
        lv.append(ListItem(Static(f"[red]error: {msg}[/red]", markup=True)))

    # ── Filter (pure data, no DOM) ────────────────────────────────────────────

    def _run_filter(self) -> None:
        """Recompute self._filtered from self._records + current filter text.
        Safe to call from any thread — touches no DOM."""
        q = self._filter_buf.lower()
        if q:
            self._filtered = [
                r for r in self._records
                if q in r.cl
                or q in r.user.lower()
                or q in r.description.lower()
            ]
        else:
            self._filtered = list(self._records)

    # ── DOM rebuild (main thread only) ────────────────────────────────────────

    def _rebuild_list(self) -> None:
        lv = self.query_one("#list-view", ListView)
        lv.clear()
        for rec in self._filtered:
            lv.append(ChangeItem(rec))
        if self._filtered:
            lv.index = 0

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_cursor_down(self) -> None:
        if self._filtering:
            return
        if self.detail_open:
            self.query_one("#detail-view", DiffView).scroll_down(3)
        else:
            self.query_one("#list-view", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        if self._filtering:
            return
        if self.detail_open:
            self.query_one("#detail-view", DiffView).scroll_up(3)
        else:
            self.query_one("#list-view", ListView).action_cursor_up()

    def action_collapse(self) -> None:
        if self._filtering:
            self._cancel_filter()
        elif self.detail_open:
            self._close_detail()

    def action_start_filter(self) -> None:
        if self.detail_open:
            return
        self._filtering = True
        self._filter_buf = ""
        fb = self.query_one("#filter-bar", Static)
        fb.add_class("active")
        fb.update("[bold cyan]Filter:[/bold cyan] _")

    def action_reload(self) -> None:
        self._records.clear()
        self._filtered.clear()
        self.query_one("#list-view", ListView).clear()
        self._load_changes()

    # ── Key handling for filter input ─────────────────────────────────────────

    def on_key(self, event) -> None:
        if not self._filtering:
            return

        key = event.key
        if key == "enter":
            self._commit_filter()
        elif key == "escape":
            self._cancel_filter()
        elif key == "backspace":
            self._filter_buf = self._filter_buf[:-1]
            self._update_filter_bar()
        elif event.character and event.character.isprintable():
            self._filter_buf += event.character
            self._update_filter_bar()
        else:
            return  # let other keys pass through
        event.stop()

    def _update_filter_bar(self) -> None:
        self.query_one("#filter-bar", Static).update(
            f"[bold cyan]Filter:[/bold cyan] {_esc(self._filter_buf)}_"
        )

    def _commit_filter(self) -> None:
        self._filtering = False
        fb = self.query_one("#filter-bar", Static)
        fb.remove_class("active")
        if self._filter_buf:
            fb.update(f"[bold cyan]Filter:[/bold cyan] {_esc(self._filter_buf)}")
            fb.add_class("active")  # keep showing what we filtered by
        self._run_filter()
        self._rebuild_list()

    def _cancel_filter(self) -> None:
        self._filtering = False
        self._filter_buf = ""
        fb = self.query_one("#filter-bar", Static)
        fb.remove_class("active")
        self._run_filter()
        self._rebuild_list()

    # ── Expand on Enter (via ListView.Selected) ───────────────────────────────

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        """ListView fires this when Enter is pressed on a highlighted item."""
        if isinstance(event.item, ChangeItem):
            self._open_detail(event.item.rec)

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _open_detail(self, rec: ChangeRecord) -> None:
        lv = self.query_one("#list-view", ListView)
        dv = self.query_one("#detail-view", DiffView)
        lv.display = False
        dv.display = True
        self.detail_open = True

        if rec.loaded:
            dv.update_content(rec)
        else:
            dv.show_loading()
            self._load_detail(rec)

    def _close_detail(self) -> None:
        lv = self.query_one("#list-view", ListView)
        dv = self.query_one("#detail-view", DiffView)
        dv.display = False
        lv.display = True
        self.detail_open = False

    @work(thread=True)
    def _load_detail(self, rec: ChangeRecord) -> None:
        _fetch_detail(rec)
        dv = self.query_one("#detail-view", DiffView)
        self.call_from_thread(dv.update_content, rec)
