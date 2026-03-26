"""Interactive TUI for listing and switching Perforce client workspaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, ListItem, ListView, Static

from p5 import theme as T
from p5.p4 import P4Error, run_p4, run_p4_tagged


# ─── Data ────────────────────────────────────────────────────────────────────

@dataclass
class ClientRecord:
    name: str
    root: str
    host: str
    description: str
    access: str       # last access date
    update: str       # last update date
    is_current: bool = False


def _fetch_clients(user: str | None) -> list[ClientRecord]:
    args = ["clients"]
    if user:
        args += ["-u", user]
    records = run_p4_tagged(args)

    # Get current client name
    try:
        info = run_p4_tagged(["info"])
        current = info[0].get("clientName", "") if info else ""
    except P4Error:
        current = ""

    result: list[ClientRecord] = []
    for r in records:
        name = r.get("client", "")
        root = r.get("Root", r.get("root", ""))
        host = r.get("Host", r.get("host", ""))
        desc = (r.get("Description", r.get("description", "")) or "").strip().replace("\n", " ")
        access = r.get("Access", r.get("access", ""))
        update = r.get("Update", r.get("update", ""))
        result.append(ClientRecord(
            name=name,
            root=root,
            host=host,
            description=desc,
            access=_epoch_to_date(access),
            update=_epoch_to_date(update),
            is_current=(name == current),
        ))

    # Sort: current first, then alphabetically
    result.sort(key=lambda c: (not c.is_current, c.name.lower()))
    return result


def _epoch_to_date(ts: str) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ts or ""


def _switch_client(name: str) -> None:
    run_p4(["set", f"P4CLIENT={name}"])


# ─── Widgets ─────────────────────────────────────────────────────────────────

class ClientItem(ListItem):
    DEFAULT_CSS = """
    ClientItem {
        height: 3;
        padding: 0 1;
        border-bottom: solid $panel-lighten-1;
    }
    ClientItem.--highlight {
        background: $accent 25%;
    }
    """

    def __init__(self, rec: ClientRecord) -> None:
        super().__init__()
        self.rec = rec

    def compose(self) -> ComposeResult:
        rec = self.rec
        marker   = "◆ " if rec.is_current else "  "
        m_style  = f"bold {T.ADDED}" if rec.is_current else "dim"
        name_style = f"bold {T.CL_NUM}" if rec.is_current else f"bold {T.DESC}"
        root_display = rec.root if rec.root else "(no root)"

        line1 = (
            f"[{m_style}]{marker}[/{m_style}]"
            f"[{name_style}]{rec.name}[/{name_style}]"
            + (f"  [dim](current)[/dim]" if rec.is_current else "")
        )
        line2 = f"  [dim]{root_display}[/dim]"
        line3 = (
            f"  [{T.DATE}]{rec.access}[/{T.DATE}]"
            + (f"  [{T.AUTHOR}]{rec.host}[/{T.AUTHOR}]" if rec.host else "")
            + (f"  [dim]{rec.description[:60]}[/dim]" if rec.description else "")
        )
        yield Static(line1, markup=True)
        yield Static(line2, markup=True)
        yield Static(line3, markup=True)


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $panel-darken-1;
        padding: 0 2;
        color: $text-muted;
    }
    """


# ─── App ─────────────────────────────────────────────────────────────────────

class WorkspaceApp(App):
    """Interactive workspace selector for p5."""

    CSS = """
    Screen { layout: vertical; }

    #header-bar {
        height: 3;
        background: $panel;
        border-bottom: solid $panel-lighten-2;
        padding: 0 2;
        content-align: left middle;
    }

    #list-view {
        height: 1fr;
        border: none;
    }

    #status-bar {
        height: 1;
        background: $panel-darken-1;
        padding: 0 2;
        color: $text-muted;
    }

    #filter-bar {
        height: 1;
        background: $panel;
        padding: 0 2;
        display: none;
    }

    #filter-bar.visible { display: block; }

    Footer { height: 1; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j,down",  "cursor_down",  "Down",  show=False),
        Binding("k,up",    "cursor_up",    "Up",    show=False),
        Binding("enter",   "select",       "Switch"),
        Binding("slash",   "start_filter", "Filter"),
        Binding("r",       "reload",       "Reload"),
        Binding("q",       "quit",         "Quit"),
    ]

    filter_text: reactive[str] = reactive("")

    def __init__(self, user: str | None = None) -> None:
        super().__init__()
        self._user = user
        self._records: list[ClientRecord] = []
        self._filtered: list[ClientRecord] = []
        self._switched_to: str | None = None

    # Result after quit — None means no switch was made
    @property
    def selected_client(self) -> str | None:
        return self._switched_to

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]p5 ws[/bold]  [dim]— Perforce workspace selector[/dim]",
            id="header-bar",
            markup=True,
        )
        yield ListView(id="list-view")
        yield Static("", id="filter-bar")
        yield Static("[dim]Loading workspaces...[/dim]", id="status-bar", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        try:
            records = _fetch_clients(self._user)
            self._records = records
            self.call_from_thread(self._apply_filter)
        except P4Error as e:
            self.call_from_thread(
                self._set_status, f"[red]error: {e}[/red]"
            )

    def _apply_filter(self) -> None:
        q = self.filter_text.lower()
        if q:
            self._filtered = [
                r for r in self._records
                if q in r.name.lower()
                or q in r.root.lower()
                or q in r.description.lower()
                or q in r.host.lower()
            ]
        else:
            self._filtered = list(self._records)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        lv = self.query_one("#list-view", ListView)
        lv.clear()
        for rec in self._filtered:
            lv.append(ClientItem(rec))
        n = len(self._filtered)
        total = len(self._records)
        suffix = f"  [dim](filtered: {n}/{total})[/dim]" if self.filter_text else ""
        self._set_status(
            f"[dim]{total} workspace{'s' if total != 1 else ''}[/dim]{suffix}  "
            f"  [dim][Enter] switch  [/] filter  [r] reload  [q] quit[/dim]"
        )

    def _set_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_cursor_down(self) -> None:
        self.query_one("#list-view", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#list-view", ListView).action_cursor_up()

    def action_select(self) -> None:
        lv = self.query_one("#list-view", ListView)
        idx = lv.index
        if idx is None or idx >= len(self._filtered):
            return
        rec = self._filtered[idx]
        self._do_switch(rec)

    def action_reload(self) -> None:
        self._records.clear()
        self.query_one("#list-view", ListView).clear()
        self._set_status("[dim]Reloading...[/dim]")
        self._load()

    def action_start_filter(self) -> None:
        fb = self.query_one("#filter-bar", Static)
        fb.add_class("visible")
        fb.update("Filter: _")
        self._filtering = True
        self._filter_buf = ""

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
                self.query_one("#filter-bar", Static).update(
                    f"Filter: {self._filter_buf}_"
                )
            elif event.character and event.character.isprintable():
                self._filter_buf += event.character
                self.query_one("#filter-bar", Static).update(
                    f"Filter: {self._filter_buf}_"
                )
            event.stop()

    @work(thread=True)
    def _do_switch(self, rec: ClientRecord) -> None:
        if rec.is_current:
            self.call_from_thread(
                self._set_status,
                f"[dim]{rec.name} is already the active workspace[/dim]",
            )
            return
        try:
            _switch_client(rec.name)
            self._switched_to = rec.name
            # Mark new current in data
            for r in self._records:
                r.is_current = (r.name == rec.name)
            self.call_from_thread(self._rebuild_list)
            self.call_from_thread(
                self._set_status,
                f"[{T.ADDED}]✓ switched to {rec.name}[/{T.ADDED}]",
            )
        except P4Error as e:
            self.call_from_thread(
                self._set_status,
                f"[red]error switching workspace: {e}[/red]",
            )
