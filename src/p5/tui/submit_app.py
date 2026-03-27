"""Interactive TUI for submitting changelists."""
from __future__ import annotations

import re as _re
import subprocess
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static, TextArea

from p5 import theme as T
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.workspace import any_to_rel


# ── Data ──────────────────────────────────────────────────────────────────────

class FileRecord:
    __slots__ = ("depot_file", "rel_path", "action")

    def __init__(self, depot_file: str, action: str) -> None:
        self.depot_file = depot_file
        self.rel_path = any_to_rel(depot_file)
        self.action = action


class PendingCL:
    __slots__ = ("cl", "description", "files")

    def __init__(self, cl: str, description: str, files: list[FileRecord]) -> None:
        self.cl = cl
        self.description = description
        self.files = files


def _esc(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def _load_cl_files(cl: str) -> list[FileRecord]:
    """Fetch opened files for a changelist, including the default changelist."""
    try:
        opened = run_p4_tagged(["opened", "-c", cl])
    except P4Error:
        return []

    files: list[FileRecord] = []
    for record in opened:
        depot_file = record.get("depotFile", "")
        action = record.get("action", "edit")
        if depot_file:
            files.append(FileRecord(depot_file, action))
    return files


def _load_cl_description(cl: str) -> str:
    """Read a changelist description from `p4 change -o`."""
    try:
        spec = run_p4(["change", "-o", cl])
    except P4Error:
        return ""
    return _extract_description_from_spec(spec)


def _extract_description_from_spec(spec: str) -> str:
    """Extract the description body from a changelist spec."""
    lines = spec.splitlines()
    desc_lines: list[str] = []
    in_desc = False
    for line in lines:
        if not in_desc:
            if line.startswith("Description:"):
                in_desc = True
            continue
        if line.startswith("\t"):
            desc_lines.append(line[1:])
            continue
        if line == "":
            desc_lines.append("")
            continue
        break
    return "\n".join(desc_lines).strip()


def _replace_description_in_spec(spec: str, new_desc: str) -> str:
    """Replace the description block in a changelist spec."""
    lines = spec.splitlines()
    out_lines: list[str] = []
    in_desc = False
    wrote_desc = False
    desc_lines = [f"\t{line}" for line in new_desc.splitlines()] or ["\t"]

    for line in lines:
        if not in_desc and line.startswith("Description:"):
            out_lines.append(line)
            out_lines.extend(desc_lines)
            in_desc = True
            wrote_desc = True
            continue
        if in_desc:
            if line.startswith("\t") or line == "":
                continue
            in_desc = False
        out_lines.append(line)

    if not wrote_desc:
        if out_lines and out_lines[-1] != "":
            out_lines.append("")
        out_lines.append("Description:")
        out_lines.extend(desc_lines)

    return "\n".join(out_lines) + "\n"


def _fetch_pending_cls() -> list[PendingCL]:
    """Fetch all personal pending changelists with their files."""
    info = run_p4_tagged(["info"])
    user = info[0].get("userName", "") if info else ""
    pending_cls: list[PendingCL] = []

    default_files = _load_cl_files("default")
    if default_files:
        default_desc = _load_cl_description("default") or "Default changelist"
        pending_cls.append(PendingCL("default", default_desc, default_files))

    args = ["changes", "-s", "pending", "-l", "-m", "50"]
    if user:
        args += ["-u", user]
    records = run_p4_tagged(args)

    for r in records:
        cl = r.get("change", "")
        desc = (r.get("desc") or "").strip()
        if not cl:
            continue
        pending_cls.append(PendingCL(cl, desc, _load_cl_files(cl)))
    return pending_cls


# ── List items ────────────────────────────────────────────────────────────────

class CLListItem(ListItem):
    def __init__(self, pcl: PendingCL) -> None:
        self.pcl = pcl
        desc_short = pcl.description.replace("\n", " ")[:50]
        cl_label = "default" if pcl.cl == "default" else f"CL {pcl.cl}"
        label = (
            f"  [{T.CL_NUM}]{cl_label}[/{T.CL_NUM}]  "
            f"[dim]({len(pcl.files)} files)[/dim]  "
            f"{_esc(desc_short)}"
        )
        super().__init__(Static(label, markup=True))


class FileItem(ListItem):
    def __init__(self, rec: FileRecord) -> None:
        letter = T.STATE_LETTER.get(rec.action, rec.action[0].upper())
        color = T.ACTION_COLOR.get(rec.action, "white")
        super().__init__(
            Static(f"   [{color}]{letter}[/{color}]  {_esc(rec.rel_path)}", markup=True)
        )


class SectionHeader(ListItem):
    def __init__(self, text: str) -> None:
        super().__init__(Static(f" [dim bold]{text}[/dim bold]", markup=True))
        self.disabled = True


# ── Move Files Modal ──────────────────────────────────────────────────────────

class MoveFilesScreen(ModalScreen[str | None]):
    """Pick a target changelist to move files into."""

    CSS = """
    MoveFilesScreen { align: center middle; }
    #move-box {
        width: 70; max-height: 80%; height: auto;
        background: $surface; border: thick $primary; padding: 1 2;
    }
    #move-list { height: auto; max-height: 20; margin: 1 0; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, files: list[FileRecord], current_cl: str) -> None:
        super().__init__()
        self._files = files
        self._current_cl = current_cl

    def compose(self) -> ComposeResult:
        with Vertical(id="move-box"):
            yield Static(
                f"[bold]Move {len(self._files)} file(s) to changelist[/bold]",
                markup=True,
            )
            yield ListView(id="move-list")
            yield Static("[dim]Enter: confirm · Esc: cancel[/dim]", markup=True)

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
        lv = self.query_one("#move-list", ListView)
        lv.clear()
        # Add default changelist option
        item = ListItem(Static(f"  [{T.CL_NUM}]default[/{T.CL_NUM}]  [dim]Default changelist[/dim]", markup=True))
        item.cl = "default"  # type: ignore[attr-defined]
        lv.append(item)
        for r in records:
            cl = r.get("change", "")
            desc = (r.get("desc") or "").strip().replace("\n", " ")[:50]
            if cl and cl != self._current_cl:
                item = ListItem(Static(f"  [{T.CL_NUM}]CL {cl}[/{T.CL_NUM}]  [dim]{_esc(desc)}[/dim]", markup=True))
                item.cl = cl  # type: ignore[attr-defined]
                lv.append(item)

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        cl = getattr(event.item, "cl", None)
        if cl is not None:
            self._do_move(cl)

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


# ── Revert Confirm Modal ─────────────────────────────────────────────────────

class RevertConfirmScreen(ModalScreen[bool]):
    """Double-confirm revert. User must type 'revert' to confirm."""

    CSS = """
    RevertConfirmScreen { align: center middle; }
    #revert-box {
        width: 60; height: auto;
        background: $surface; border: thick $error; padding: 1 2;
    }
    #confirm-input { margin: 1 0; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, files: list[FileRecord], *, unchanged_only: bool = False) -> None:
        super().__init__()
        self._files = files
        self._unchanged_only = unchanged_only

    def compose(self) -> ComposeResult:
        with Vertical(id="revert-box"):
            if self._unchanged_only:
                yield Static(
                    f"[bold red]Revert unchanged files in this CL?[/bold red]",
                    markup=True,
                )
                yield Static(
                    f"[dim]Files that have no content changes will be reverted.[/dim]",
                    markup=True,
                )
            else:
                yield Static(
                    f"[bold red]Revert {len(self._files)} file(s)?[/bold red]",
                    markup=True,
                )
                for f in self._files[:10]:
                    letter = T.STATE_LETTER.get(f.action, "?")
                    color = T.ACTION_COLOR.get(f.action, "white")
                    yield Static(f"  [{color}]{letter}[/{color}]  {_esc(f.rel_path)}", markup=True)
                if len(self._files) > 10:
                    yield Static(f"  [dim]... and {len(self._files) - 10} more[/dim]", markup=True)
            yield Static("")
            yield Static("[bold]Type 'revert' to confirm:[/bold]", markup=True)
            yield Input(placeholder="revert", id="confirm-input")
            yield Static("[dim]Esc: cancel[/dim]", markup=True)

    def on_mount(self) -> None:
        self.query_one("#confirm-input", Input).focus()

    @on(Input.Submitted)
    def on_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip().lower() == "revert":
            self.dismiss(True)
        else:
            self.notify("Type 'revert' to confirm", severity="warning")

    def action_cancel(self) -> None:
        self.dismiss(False)


# ── Submit Confirm Modal ──────────────────────────────────────────────────────

class SubmitConfirmScreen(ModalScreen[bool]):
    """Final confirmation before submit."""

    CSS = """
    SubmitConfirmScreen { align: center middle; }
    #submit-box {
        width: 70; max-height: 80%; height: auto;
        background: $surface; border: thick $success; padding: 1 2;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Confirm"),
    ]

    def __init__(self, pcl: PendingCL) -> None:
        super().__init__()
        self._pcl = pcl

    def compose(self) -> ComposeResult:
        with Vertical(id="submit-box"):
            yield Static(
                f"[bold]Submit CL {self._pcl.cl}?[/bold]",
                markup=True,
            )
            yield Static("")
            desc_short = self._pcl.description.replace("\n", " ")[:80]
            yield Static(f"  [white]{_esc(desc_short)}[/white]", markup=True)
            yield Static("")
            yield Static(f"  [dim]{len(self._pcl.files)} file(s)[/dim]", markup=True)
            for f in self._pcl.files[:15]:
                letter = T.STATE_LETTER.get(f.action, "?")
                color = T.ACTION_COLOR.get(f.action, "white")
                yield Static(f"    [{color}]{letter}[/{color}]  {_esc(f.rel_path)}", markup=True)
            if len(self._pcl.files) > 15:
                yield Static(f"    [dim]... and {len(self._pcl.files) - 15} more[/dim]", markup=True)
            yield Static("")
            yield Static("[bold green]y[/bold green] submit  [dim]Esc[/dim] cancel", markup=True)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ── Description Editor Modal ─────────────────────────────────────────────────

class DescriptionScreen(ModalScreen[str | None]):
    """Edit changelist description."""

    CSS = """
    DescriptionScreen { align: center middle; }
    #desc-box {
        width: 80; height: 20;
        background: $surface; border: thick $primary; padding: 1 2;
    }
    #desc-editor { height: 1fr; margin: 1 0; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_desc: str) -> None:
        super().__init__()
        self._current_desc = current_desc

    def compose(self) -> ComposeResult:
        with Vertical(id="desc-box"):
            yield Static("[bold]Edit description[/bold]  [dim](Ctrl+S to save)[/dim]", markup=True)
            yield TextArea(self._current_desc, id="desc-editor")
            yield Static("[dim]Ctrl+S: save · Esc: cancel[/dim]", markup=True)

    def on_mount(self) -> None:
        self.query_one("#desc-editor", TextArea).focus()

    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            text = self.query_one("#desc-editor", TextArea).text.strip()
            if not text:
                self.notify("Description cannot be empty", severity="warning")
                return
            self.dismiss(text)
            event.stop()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main App ─────────────────────────────────────────────────────────────────

class SubmitApp(App):
    """Browse pending changelists, manage files, edit description, and submit."""

    CSS = """
    #header-bar  { background: $surface; padding: 0 1; }
    #footer-bar  { background: $surface; padding: 0 1; dock: bottom; height: 2; }
    #filter-bar  { display: none; background: $primary; padding: 0 1;
                   dock: bottom; height: 1; }
    #filter-bar.visible { display: block; }
    #main-list { height: 1fr; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j,down", "cursor_down", "Down",        show=False),
        Binding("k,up",   "cursor_up",   "Up",          show=False),
        Binding("enter",  "select_item", "Select",      show=False),
        Binding("escape", "go_back",     "Back"),
        Binding("m",      "move_file",   "Move"),
        Binding("r",      "revert_file", "Revert"),
        Binding("u",      "revert_unchanged", "Revert unchanged"),
        Binding("e",      "edit_desc",   "Edit desc"),
        Binding("s",      "do_submit",   "Submit"),
        Binding("slash",  "start_filter", "Filter"),
        Binding("q",      "quit",        "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._cls: list[PendingCL] = []
        self._current_cl: PendingCL | None = None   # None = CL list view
        self._list_data: list[PendingCL | FileRecord | None] = []  # None = header
        self._filtering: bool = False
        self._filter_buf: str = ""
        self._filter_text: str = ""
        self._filter_just_committed: bool = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]p5 submit[/bold]  [dim]— submit pending changelists[/dim]",
            id="header-bar",
            markup=True,
        )
        yield ListView(id="main-list")
        yield Static("", id="filter-bar", markup=True)
        yield Static("", id="footer-bar", markup=True)

    def on_mount(self) -> None:
        self._update_footer()
        self._load_cls()

    # ── footer ────────────────────────────────────────────────────────────

    def _update_footer(self) -> None:
        fb = self.query_one("#footer-bar", Static)
        if self._current_cl:
            fb.update(
                "[dim]m[/dim] move  [dim]r[/dim] revert  "
                "[dim]u[/dim] revert unchanged  [dim]e[/dim] edit desc  "
                "[dim]s[/dim] submit  [dim]Esc[/dim] back  [dim]q[/dim] quit"
            )
        else:
            fb.update(
                "[dim]Enter[/dim] select CL  "
                "[dim]/[/dim] filter  [dim]q[/dim] quit"
            )

    # ── data loading ──────────────────────────────────────────────────────

    @work(thread=True)
    def _load_cls(self) -> None:
        try:
            cls = _fetch_pending_cls()
        except P4Error:
            cls = []
        self._cls = cls
        self.call_from_thread(self._show_cl_list)

    def _show_cl_list(self) -> None:
        self._current_cl = None
        self._update_footer()
        lv = self.query_one("#main-list", ListView)
        lv.clear()
        self._list_data = []

        if not self._cls:
            lv.append(SectionHeader("  (no pending changelists)"))
            self._list_data.append(None)
            return

        needle = self._filter_text.lower() if self._filter_text else ""
        for pcl in self._cls:
            if needle and needle not in pcl.cl and needle not in pcl.description.lower():
                continue
            lv.append(CLListItem(pcl))
            self._list_data.append(pcl)

        if self._list_data:
            lv.index = 0

    def _show_cl_detail(self, pcl: PendingCL) -> None:
        self._current_cl = pcl
        self._update_footer()
        lv = self.query_one("#main-list", ListView)
        lv.clear()
        self._list_data = []

        # Header
        desc_short = pcl.description.replace("\n", " ")[:60]
        cl_label = "default" if pcl.cl == "default" else f"CL {pcl.cl}"
        lv.append(SectionHeader(
            f"{cl_label}  —  {_esc(desc_short)}"
        ))
        self._list_data.append(None)

        if not pcl.files:
            lv.append(SectionHeader("  (no files)"))
            self._list_data.append(None)
        else:
            for f in pcl.files:
                lv.append(FileItem(f))
                self._list_data.append(f)

        # Position cursor on first file
        for i, d in enumerate(self._list_data):
            if d is not None:
                lv.index = i
                break

    # ── reload a single CL's files ────────────────────────────────────────

    @work(thread=True)
    def _reload_current_cl(self) -> None:
        pcl = self._current_cl
        if not pcl:
            return
        pcl.files = _load_cl_files(pcl.cl)
        if pcl.cl == "default":
            pcl.description = _load_cl_description("default") or "Default changelist"
        self.call_from_thread(self._show_cl_detail, pcl)

    # ── current item ──────────────────────────────────────────────────────

    def _current_item(self):
        lv = self.query_one("#main-list", ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._list_data):
            return self._list_data[idx]
        return None

    # ── cursor movement ───────────────────────────────────────────────────

    def action_cursor_down(self) -> None:
        if self._filtering:
            return
        lv = self.query_one("#main-list", ListView)
        lv.action_cursor_down()
        idx = lv.index
        if idx is not None and idx < len(self._list_data) and self._list_data[idx] is None:
            if idx + 1 < len(self._list_data):
                lv.index = idx + 1

    def action_cursor_up(self) -> None:
        if self._filtering:
            return
        lv = self.query_one("#main-list", ListView)
        lv.action_cursor_up()
        idx = lv.index
        if idx is not None and idx < len(self._list_data) and self._list_data[idx] is None:
            if idx > 0:
                lv.index = idx - 1

    # ── select (Enter) ────────────────────────────────────────────────────

    def action_select_item(self) -> None:
        pass  # handled by ListView.Selected

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        if self._filtering:
            return
        if self._filter_just_committed:
            self._filter_just_committed = False
            return
        item = self._current_item()
        if isinstance(item, PendingCL):
            self._show_cl_detail(item)

    # ── go back ───────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        if self._filtering:
            self._cancel_filter()
        elif self._current_cl:
            self._filter_text = ""
            self._show_cl_list()

    # ── move file to another CL ──────────────────────────────────────────

    def action_move_file(self) -> None:
        if self._filtering or not self._current_cl:
            return
        item = self._current_item()
        if not isinstance(item, FileRecord):
            return
        self.push_screen(
            MoveFilesScreen([item], self._current_cl.cl),
            self._on_move_done,
        )

    def _on_move_done(self, result: str | None) -> None:
        if result:
            target = "default changelist" if result == "default" else f"CL {result}"
            self.notify(f"Moved to {target}", severity="information")
            self._reload_current_cl()

    # ── revert file (double confirm) ─────────────────────────────────────

    def action_revert_file(self) -> None:
        if self._filtering or not self._current_cl:
            return
        item = self._current_item()
        if not isinstance(item, FileRecord):
            return
        self.push_screen(
            RevertConfirmScreen([item]),
            self._on_revert_done,
        )

    def _on_revert_done(self, confirmed: bool) -> None:
        if not confirmed or not self._current_cl:
            return
        item = self._current_item()
        if isinstance(item, FileRecord):
            self._do_revert([item])

    @work(thread=True)
    def _do_revert(self, files: list[FileRecord]) -> None:
        try:
            depot_files = [f.depot_file for f in files]
            run_p4(["revert"] + depot_files)
            self.call_from_thread(
                self.notify, f"Reverted {len(files)} file(s)", severity="information"
            )
            self.call_from_thread(self._trigger_reload)
        except P4Error as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def _trigger_reload(self) -> None:
        self._reload_current_cl()

    # ── revert unchanged ─────────────────────────────────────────────────

    def action_revert_unchanged(self) -> None:
        if self._filtering or not self._current_cl:
            return
        if not self._current_cl.files:
            self.notify("No files in this changelist", severity="warning")
            return
        self.push_screen(
            RevertConfirmScreen(self._current_cl.files, unchanged_only=True),
            self._on_revert_unchanged_done,
        )

    def _on_revert_unchanged_done(self, confirmed: bool) -> None:
        if not confirmed or not self._current_cl:
            return
        self._do_revert_unchanged()

    @work(thread=True)
    def _do_revert_unchanged(self) -> None:
        pcl = self._current_cl
        if not pcl:
            return
        try:
            run_p4(["revert", "-a", "-c", pcl.cl, "//..."])
            self.call_from_thread(
                self.notify, "Reverted unchanged files", severity="information"
            )
            self.call_from_thread(self._trigger_reload)
        except P4Error as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    # ── edit description ──────────────────────────────────────────────────

    def action_edit_desc(self) -> None:
        if self._filtering or not self._current_cl:
            return
        self.push_screen(
            DescriptionScreen(self._current_cl.description),
            self._on_desc_done,
        )

    def _on_desc_done(self, new_desc: str | None) -> None:
        if not new_desc or not self._current_cl:
            return
        self._save_desc(new_desc)

    @work(thread=True)
    def _save_desc(self, new_desc: str) -> None:
        pcl = self._current_cl
        if not pcl:
            return
        try:
            # Fetch current spec, update description, write back
            raw = run_p4(["change", "-o", pcl.cl])
            spec = _replace_description_in_spec(raw, new_desc)
            result = subprocess.run(
                ["p4", "change", "-i"],
                input=spec,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                self.call_from_thread(self.notify, f"Error: {err}", severity="error")
                return

            pcl.description = new_desc
            self.call_from_thread(
                self.notify, "Description updated", severity="information"
            )
            self.call_from_thread(self._show_cl_detail, pcl)
        except (P4Error, FileNotFoundError) as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    # ── submit ────────────────────────────────────────────────────────────

    def action_do_submit(self) -> None:
        if self._filtering or not self._current_cl:
            return
        if not self._current_cl.files:
            self.notify("No files to submit", severity="warning")
            return
        self.push_screen(
            SubmitConfirmScreen(self._current_cl),
            self._on_submit_done,
        )

    def _on_submit_done(self, confirmed: bool) -> None:
        if not confirmed or not self._current_cl:
            return
        self._run_submit()

    @work(thread=True)
    def _run_submit(self) -> None:
        pcl = self._current_cl
        if not pcl:
            return
        try:
            submit_args = ["submit"] if pcl.cl == "default" else ["submit", "-c", pcl.cl]
            raw = run_p4(submit_args)
            m = _re.search(r"Change (\d+) submitted", raw)
            if m:
                submitted_cl = m.group(1)
                msg = (
                    f"Submitted default changelist as CL {submitted_cl}"
                    if pcl.cl == "default"
                    else f"Submitted CL {submitted_cl}"
                )
            else:
                msg = raw.strip()[:80]
            self.call_from_thread(self.notify, msg, severity="information")
            # Reload — the submitted CL will no longer appear
            try:
                cls = _fetch_pending_cls()
            except P4Error:
                cls = []
            self._cls = cls
            self._current_cl = None
            self.call_from_thread(self._show_cl_list)
        except P4Error as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    # ── filter mode ───────────────────────────────────────────────────────

    def action_start_filter(self) -> None:
        if self._current_cl:
            return  # filter only in CL list view
        self._filtering = True
        self._filter_buf = self._filter_text
        self._update_filter_bar()
        self.query_one("#filter-bar", Static).add_class("visible")

    def _update_filter_bar(self) -> None:
        fb = self.query_one("#filter-bar", Static)
        fb.update(f"[bold]filter:[/bold] {_esc(self._filter_buf)}▏")

    def _cancel_filter(self) -> None:
        self._filtering = False
        self._filter_buf = ""
        self._filter_text = ""
        self.query_one("#filter-bar", Static).remove_class("visible")
        self._show_cl_list()

    def on_key(self, event) -> None:
        if not self._filtering:
            return

        key = event.key
        if key == "enter":
            self._filtering = False
            self._filter_just_committed = True
            self._filter_text = self._filter_buf
            self.query_one("#filter-bar", Static).remove_class("visible")
            self._show_cl_list()
            event.stop()
        elif key == "escape":
            self._cancel_filter()
            event.stop()
        elif key == "backspace":
            self._filter_buf = self._filter_buf[:-1]
            self._filter_text = self._filter_buf
            self._update_filter_bar()
            self._show_cl_list()
            event.stop()
        elif len(event.character or "") == 1 and event.character.isprintable():
            self._filter_buf += event.character
            self._filter_text = self._filter_buf
            self._update_filter_bar()
            self._show_cl_list()
            event.stop()
        else:
            event.stop()
