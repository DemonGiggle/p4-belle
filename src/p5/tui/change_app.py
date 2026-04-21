"""Interactive TUI for managing the default changelist."""
from __future__ import annotations

import re as _re
import subprocess
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from p5 import theme as T
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.workspace import any_to_rel


# ── Data ──────────────────────────────────────────────────────────────────────

class FileRecord:
    __slots__ = ("depot_file", "rel_path", "action")

    def __init__(self, depot_file: str, action: str, rel_path: str | None = None) -> None:
        self.depot_file = depot_file
        self.rel_path = rel_path or any_to_rel(depot_file)
        self.action = action


def _esc(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


# ── List items ────────────────────────────────────────────────────────────────

class FileItem(ListItem):
    def __init__(self, rec: FileRecord, selected: bool) -> None:
        letter = T.STATE_LETTER.get(rec.action, rec.action[0].upper())
        color = T.ACTION_COLOR.get(rec.action, "white")
        mark = "\u2713" if selected else " "
        super().__init__(
            Static(f"  [{color}]{mark}  {letter}[/{color}]  {_esc(rec.rel_path)}", markup=True)
        )


class SectionHeader(ListItem):
    def __init__(self, text: str) -> None:
        super().__init__(Static(f" [dim bold]{text}[/dim bold]", markup=True))
        self.disabled = True


class CLItem(ListItem):
    def __init__(self, cl: str, desc: str) -> None:
        self.cl = cl
        if cl == "default":
            label = f"  [{T.CL_NUM}]default[/{T.CL_NUM}]  [dim]Default changelist[/dim]"
        else:
            label = f"  [{T.CL_NUM}]CL {cl}[/{T.CL_NUM}]  [dim]{_esc(desc)}[/dim]"
        super().__init__(Static(label, markup=True))


# ── CL Selector Modal ────────────────────────────────────────────────────────

class CLSelectorScreen(ModalScreen[str | None]):
    """Pick a target changelist to move files into."""

    CSS = """
    CLSelectorScreen { align: center middle; }
    #cl-box {
        width: 70; max-height: 80%; height: auto;
        background: $surface; border: thick $primary; padding: 1 2;
    }
    #cl-list { height: auto; max-height: 20; margin: 1 0; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, files: list[FileRecord]) -> None:
        super().__init__()
        self._files = files

    def compose(self) -> ComposeResult:
        with Vertical(id="cl-box"):
            yield Static(
                f"[bold]Move {len(self._files)} file(s) to changelist[/bold]",
                markup=True,
            )
            yield ListView(id="cl-list")
            yield Static("[dim]Enter: confirm \u00b7 Esc: cancel[/dim]", markup=True)

    def on_mount(self) -> None:
        self._fetch_cls()

    @work(thread=True)
    def _fetch_cls(self) -> None:
        try:
            info = run_p4_tagged(["info"])
            user = info[0].get("userName", "") if info else ""
            args = ["changes", "-s", "pending", "-m", "30"]
            if user:
                args += ["-u", user]
            records = run_p4_tagged(args)
        except P4Error:
            records = []
        self.app.call_from_thread(self._populate, records)

    def _populate(self, records: list[dict]) -> None:
        lv = self.query_one("#cl-list", ListView)
        lv.clear()
        lv.append(CLItem("default", ""))
        for r in records:
            cl = r.get("change", "")
            desc = (r.get("desc") or "").strip().replace("\n", " ")[:50]
            if cl:
                lv.append(CLItem(cl, desc))

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, CLItem):
            self._do_move(event.item.cl)

    @work(thread=True)
    def _do_move(self, cl: str) -> None:
        try:
            depot_files = [f.depot_file for f in self._files]
            run_p4(["reopen", "-c", cl] + depot_files)
            self.app.call_from_thread(self.dismiss, cl)
        except P4Error as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── New CL Modal ─────────────────────────────────────────────────────────────

class NewCLScreen(ModalScreen[str | None]):
    """Create a new changelist and move selected files into it."""

    CSS = """
    NewCLScreen { align: center middle; }
    #new-cl-box {
        width: 70; max-height: 80%; height: auto;
        background: $surface; border: thick $primary; padding: 1 2;
    }
    #desc-input { margin: 1 0; }
    #file-preview { max-height: 15; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, files: list[FileRecord]) -> None:
        super().__init__()
        self._files = files

    def compose(self) -> ComposeResult:
        with Vertical(id="new-cl-box"):
            yield Static("[bold]Create new changelist[/bold]", markup=True)
            yield Static("")
            yield Static("Description:")
            yield Input(
                placeholder="Enter changelist description\u2026",
                id="desc-input",
            )
            yield Static("")
            yield Static("[bold]Files:[/bold]", markup=True)
            lines = []
            for f in self._files:
                letter = T.STATE_LETTER.get(f.action, f.action[0].upper())
                color = T.ACTION_COLOR.get(f.action, "white")
                lines.append(f"  [{color}]{letter}[/{color}]  {_esc(f.rel_path)}")
            yield Static("\n".join(lines), id="file-preview", markup=True)
            yield Static("")
            yield Static(
                "[dim]Enter: create \u00b7 Esc: cancel[/dim]", markup=True
            )

    def on_mount(self) -> None:
        self.query_one("#desc-input", Input).focus()

    @on(Input.Submitted)
    def on_submitted(self, event: Input.Submitted) -> None:
        desc = event.value.strip()
        if not desc:
            self.notify("Description cannot be empty", severity="warning")
            return
        self._create_cl(desc)

    @work(thread=True)
    def _create_cl(self, desc: str) -> None:
        try:
            indented = "\n\t".join(desc.splitlines())
            spec = f"Change: new\n\nDescription:\n\t{indented}\n"

            result = subprocess.run(
                ["p4", "change", "-i"],
                input=spec,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.notify, f"Error: {err}", severity="error")
                return

            m = _re.search(r"Change (\d+) created", result.stdout)
            if not m:
                self.app.call_from_thread(
                    self.notify,
                    f"Unexpected: {result.stdout.strip()}",
                    severity="error",
                )
                return

            new_cl = m.group(1)

            # Move files into the new CL
            depot_files = [f.depot_file for f in self._files]
            run_p4(["reopen", "-c", new_cl] + depot_files)

            self.app.call_from_thread(self.dismiss, new_cl)
        except (P4Error, FileNotFoundError) as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main App ─────────────────────────────────────────────────────────────────

class ChangeApp(App):
    """Manage files in the default changelist — select, group, and move."""

    CSS = """
    #header-bar  { background: $surface; padding: 0 1; }
    #footer-bar  { background: $surface; padding: 0 1; dock: bottom; height: 2; }
    #filter-bar  { display: none; background: $primary; padding: 0 1;
                   dock: bottom; height: 1; }
    #filter-bar.visible { display: block; }
    #filter-bar.active { text-style: bold; }
    #filter-input {
        display: none;
        dock: bottom;
        height: 1;
        margin: 0;
        border: none;
        padding: 0 1;
        background: $boost;
        color: $text;
    }
    #filter-input.visible { display: block; }
    #file-list { height: 1fr; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j,down", "cursor_down",  "Down",       show=False),
        Binding("k,up",   "cursor_up",    "Up",         show=False),
        Binding("space",  "toggle",       "Toggle"),
        Binding("a",      "select_all",   "Select All"),
        Binding("d",      "deselect_all", "Deselect"),
        Binding("n",      "new_cl",       "New CL"),
        Binding("m",      "move_to_cl",   "Move"),
        Binding("slash",  "start_filter", "Filter"),
        Binding("q",      "quit",         "Quit"),
    ]

    def __init__(self, files: list[FileRecord] | None = None, *, demo_mode: bool = False) -> None:
        super().__init__()
        self._demo_files = files
        self._demo_mode = demo_mode
        self._demo_next_cl = 123480
        self._files: list[FileRecord] = []
        self._selected: set[str] = set()          # depot paths
        self._filtered: list[FileRecord] = []
        self._list_data: list[FileRecord | None] = []  # None = section header
        self._filtering: bool = False
        self._filter_buf: str = ""
        self._filter_text: str = ""
        self._filter_just_committed: bool = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]p5 change[/bold]  [dim]\u2014 manage default changelist[/dim]",
            id="header-bar",
            markup=True,
        )
        yield ListView(id="file-list")
        yield Input(placeholder="Filter files…", id="filter-input")
        yield Static("", id="filter-bar", markup=True)
        yield Static(
            "[dim] space[/dim] toggle  [dim]a[/dim] all  "
            "[dim]d[/dim] none  [dim]n[/dim] new CL  "
            "[dim]m[/dim] move  [dim]/[/dim] filter  [dim]q[/dim] quit",
            id="footer-bar",
            markup=True,
        )

    def on_mount(self) -> None:
        self._load_files()

    # ── data loading ──────────────────────────────────────────────────────

    @work(thread=True)
    def _load_files(self) -> None:
        if self._demo_files is not None:
            self._files = list(self._demo_files)
            self._run_filter()
            self.call_from_thread(self._rebuild_list)
            return
        try:
            records = run_p4_tagged(["opened", "-c", "default"])
        except P4Error:
            records = []
        files = []
        for r in records:
            dp = r.get("depotFile", "")
            action = r.get("action", "edit")
            if dp:
                files.append(FileRecord(dp, action))
        self._files = files
        self._run_filter()
        self.call_from_thread(self._rebuild_list)

    # ── filter ────────────────────────────────────────────────────────────

    def _run_filter(self) -> None:
        if self._filter_text:
            needle = self._filter_text.lower()
            self._filtered = [
                f for f in self._files if needle in f.rel_path.lower()
            ]
        else:
            self._filtered = list(self._files)

    def _rebuild_list(self) -> None:
        lv = self.query_one("#file-list", ListView)
        lv.clear()
        self._list_data = []

        sel = [f for f in self._filtered if f.depot_file in self._selected]
        unsel = [f for f in self._filtered if f.depot_file not in self._selected]

        if sel:
            lv.append(SectionHeader(f"\u2500\u2500 Selected ({len(sel)}) \u2500\u2500"))
            self._list_data.append(None)
            for f in sel:
                lv.append(FileItem(f, True))
                self._list_data.append(f)

        header = (
            f"\u2500\u2500 Default changelist ({len(unsel)}) \u2500\u2500"
            if unsel
            else "\u2500\u2500 Default changelist (empty) \u2500\u2500"
        )
        lv.append(SectionHeader(header))
        self._list_data.append(None)
        for f in unsel:
            lv.append(FileItem(f, False))
            self._list_data.append(f)

        if not self._files:
            lv.append(SectionHeader("  (no files in default changelist)"))
            self._list_data.append(None)

        # Cursor on first FileItem
        for i, d in enumerate(self._list_data):
            if d is not None:
                lv.index = i
                break

    # ── current item ──────────────────────────────────────────────────────

    def _current_file(self) -> FileRecord | None:
        lv = self.query_one("#file-list", ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._list_data):
            return self._list_data[idx]
        return None

    # ── selection actions ─────────────────────────────────────────────────

    def action_toggle(self) -> None:
        if self._filtering:
            return
        rec = self._current_file()
        if not rec:
            return
        lv = self.query_one("#file-list", ListView)
        old_idx = lv.index or 0

        if rec.depot_file in self._selected:
            self._selected.discard(rec.depot_file)
        else:
            self._selected.add(rec.depot_file)

        self._rebuild_list()

        # Advance cursor to next file after the toggled position
        target = min(old_idx, len(self._list_data) - 1)
        for i in range(target, len(self._list_data)):
            if self._list_data[i] is not None:
                lv.index = i
                return
        # Fallback: find any file item
        for i in range(len(self._list_data) - 1, -1, -1):
            if self._list_data[i] is not None:
                lv.index = i
                return

    def action_select_all(self) -> None:
        if self._filtering:
            return
        for f in self._filtered:
            self._selected.add(f.depot_file)
        self._rebuild_list()

    def action_deselect_all(self) -> None:
        if self._filtering:
            return
        for f in self._filtered:
            self._selected.discard(f.depot_file)
        self._rebuild_list()

    # ── changelist actions ────────────────────────────────────────────────

    def action_new_cl(self) -> None:
        if self._filtering:
            return
        if not self._selected:
            self.notify("No files selected", severity="warning")
            return
        if self._demo_mode:
            self._demo_next_cl += 1
            moved = [f for f in self._files if f.depot_file in self._selected]
            self._files = [f for f in self._files if f.depot_file not in self._selected]
            self._selected.clear()
            self._run_filter()
            self._rebuild_list()
            self.notify(
                f"Created demo CL {self._demo_next_cl} with {len(moved)} file(s)",
                severity="information",
            )
            return
        files = [f for f in self._files if f.depot_file in self._selected]
        self.push_screen(NewCLScreen(files), self._on_new_cl)

    def _on_new_cl(self, result: str | None) -> None:
        if result:
            self.notify(f"Created CL {result}", severity="information")
            self._selected.clear()
            self._load_files()

    def action_move_to_cl(self) -> None:
        if self._filtering:
            return
        if not self._selected:
            self.notify("No files selected", severity="warning")
            return
        if self._demo_mode:
            moved = [f for f in self._files if f.depot_file in self._selected]
            self._files = [f for f in self._files if f.depot_file not in self._selected]
            self._selected.clear()
            self._run_filter()
            self._rebuild_list()
            self.notify(
                f"Moved {len(moved)} file(s) to demo CL 123460",
                severity="information",
            )
            return
        files = [f for f in self._files if f.depot_file in self._selected]
        self.push_screen(CLSelectorScreen(files), self._on_move)

    def _on_move(self, result: str | None) -> None:
        if result:
            self.notify(f"Moved to CL {result}", severity="information")
            self._selected.clear()
            self._load_files()

    # ── cursor movement (skip section headers) ────────────────────────────

    def action_cursor_down(self) -> None:
        if self._filtering:
            return
        lv = self.query_one("#file-list", ListView)
        lv.action_cursor_down()
        idx = lv.index
        if idx is not None and self._list_data[idx] is None:
            if idx + 1 < len(self._list_data):
                lv.index = idx + 1

    def action_cursor_up(self) -> None:
        if self._filtering:
            return
        lv = self.query_one("#file-list", ListView)
        lv.action_cursor_up()
        idx = lv.index
        if idx is not None and self._list_data[idx] is None:
            if idx > 0:
                lv.index = idx - 1

    # ── ListView.Selected (Enter on an item) ──────────────────────────────

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        if self._filter_just_committed:
            self._filter_just_committed = False
            return
        if isinstance(event.item, FileItem):
            self.action_toggle()

    # ── filter mode ───────────────────────────────────────────────────────

    def action_start_filter(self) -> None:
        self._filtering = True
        self._filter_just_committed = False
        self._filter_buf = self._filter_text
        filter_input = self.query_one("#filter-input", Input)
        filter_input.value = self._filter_text
        filter_input.add_class("visible")
        filter_input.focus()
        self._update_filter_bar()

    def _update_filter_bar(self) -> None:
        fb = self.query_one("#filter-bar", Static)
        if self._filtering:
            text = self._filter_buf
            fb.update(f"[bold]filter:[/bold] {_esc(text)}▏")
            fb.add_class("visible")
            fb.add_class("active")
            return

        text = self._filter_text
        fb.remove_class("active")
        if text:
            fb.update(f"[bold]filter:[/bold] {_esc(text)}")
            fb.add_class("visible")
        else:
            fb.update("")
            fb.remove_class("visible")

    @on(Input.Changed, "#filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self._filter_buf = event.value
        self._filter_text = event.value
        self._update_filter_bar()
        self._run_filter()
        self._rebuild_list()
        # Keep typing routed to the filter input while the list updates.
        if self._filtering:
            event.input.focus()

    @on(Input.Submitted, "#filter-input")
    def on_filter_submitted(self, event: Input.Submitted) -> None:
        self._filtering = False
        self._filter_buf = event.value
        self._filter_text = event.value
        self._filter_just_committed = True
        self.query_one("#filter-input", Input).remove_class("visible")
        self.query_one("#file-list", ListView).focus()
        self._update_filter_bar()

    def on_key(self, event) -> None:
        if not self._filtering or event.key != "escape":
            return

        self._filtering = False
        self._filter_buf = ""
        self._filter_text = ""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.value = ""
        filter_input.remove_class("visible")
        self.query_one("#file-list", ListView).focus()
        self._update_filter_bar()
        self._run_filter()
        self._rebuild_list()
        event.stop()
