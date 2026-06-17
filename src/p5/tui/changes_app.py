"""Interactive TUI for browsing p4 changelists using Textual."""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar

from rich.markup import escape as markup_escape
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, ListItem, ListView, Static

from p5 import theme as T
from p5.diff_utils import (
    DEFAULT_SIDE_BY_SIDE_COLUMN_WIDTH,
    build_side_by_side_lines,
    filter_unified_diff,
    make_unified_diff,
    side_by_side_column_width,
    _display_path,
)
from p5.p4 import P4Error, run_p4, run_p4_tagged
from p5.tui.widgets import FastListView, FastScrollableContainer
from p5.workspace import any_to_rel


# ─── Data ────────────────────────────────────────────────────────────────────

_ADD_ACTIONS = {"add", "branch", "move/add"}
_DELETE_ACTIONS = {"delete", "move/delete"}
_BINARY_TYPES = {"binary", "ubinary", "apple", "resource"}


class _CancelledFetch(Exception):
    """Raised when an in-flight detail fetch is cancelled."""


@dataclass
class ChangeFileRecord:
    action: str
    path: str
    depot_file: str = ""
    rev: str = ""
    file_type: str = "text"
    diff: str = ""
    diff_loaded: bool = False


@dataclass
class ChangeRecord:
    cl: str
    date: str
    user: str
    description: str
    status: str = "submitted"
    files: list[ChangeFileRecord | tuple[str, str]] = field(default_factory=list)
    diff: str = ""
    loaded: bool = False

    def __post_init__(self) -> None:
        normalized: list[ChangeFileRecord] = []
        for item in self.files:
            if isinstance(item, ChangeFileRecord):
                normalized.append(item)
            else:
                action, path = item
                normalized.append(ChangeFileRecord(action=action, path=path))
        self.files = normalized

        if self.diff:
            sections = _split_diff_by_path(self.diff)
            for file_rec in self.files:
                if not file_rec.diff and file_rec.path in sections:
                    file_rec.diff = sections[file_rec.path]
                    file_rec.diff_loaded = True


def _epoch_to_date(ts: str) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(ts)


def _fetch_changes(user: str | None, max_cls: int, cl_status: str,
                   p4_path: str = "//...") -> list[ChangeRecord]:
    args = ["changes", "-l", "-m", str(max_cls)]
    if cl_status != "all":
        args += ["-s", cl_status]
    if user:
        args += ["-u", user]
    args.append(p4_path)

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


def _split_diff_by_path(raw: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_path: str | None = None
    current_lines: list[str] = []
    pending_path: str | None = None
    lines = raw.splitlines()

    def flush() -> None:
        nonlocal current_path, current_lines
        if current_path and current_lines:
            sections[current_path] = list(current_lines)
        current_path = None
        current_lines = []

    for idx, line in enumerate(lines):
        if match := _HEADER_RE.match(line):
            flush()
            current_path = any_to_rel(match.group(1))
            current_lines = [line]
            pending_path = current_path
            continue

        if line.startswith('--- '):
            flush()
            fromfile = line[4:]
            tofile = ''
            if idx + 1 < len(lines) and lines[idx + 1].startswith('+++ '):
                tofile = lines[idx + 1][4:]
            display = pending_path or _display_path(fromfile, tofile)
            if display.startswith(('a/', 'b/')):
                display = display[2:]
            current_path = display
            current_lines = [line]
            pending_path = None
            continue

        if current_path is not None:
            current_lines.append(line)

    flush()
    return {path: '\n'.join(chunk) + '\n' for path, chunk in sections.items()}


def _run_p4_cancellable(args: list[str], should_cancel) -> str:
    cmd = ['p4'] + args
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise P4Error('p4 command not found — is Perforce installed and on PATH?')

    while proc.poll() is None:
        if should_cancel():
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise _CancelledFetch()
        time.sleep(0.05)

    out, err = proc.communicate()
    if should_cancel():
        raise _CancelledFetch()
    if proc.returncode != 0:
        raise P4Error((err or out).strip() or 'p4 command failed', proc.returncode)
    return out


def _fetch_detail_summary(rec: ChangeRecord) -> None:
    if rec.loaded:
        return

    file_records = run_p4_tagged(['describe', '-s', rec.cl])
    depot_files: list[str] = []
    actions: list[str] = []
    revs: list[str] = []
    types: list[str] = []

    for record in file_records:
        record_depot_files = record.get('depotFile') or []
        record_actions = record.get('action') or []
        record_revs = record.get('rev') or []
        record_types = record.get('type') or []

        if isinstance(record_depot_files, str):
            record_depot_files = [record_depot_files]
        if isinstance(record_actions, str):
            record_actions = [record_actions]
        if isinstance(record_revs, str):
            record_revs = [record_revs]
        if isinstance(record_types, str):
            record_types = [record_types]

        depot_files.extend([item for item in record_depot_files if item])
        actions.extend(record_actions)
        revs.extend(record_revs)
        types.extend(record_types)

    rec.files = []
    for idx, depot_file in enumerate(depot_files):
        rec.files.append(
            ChangeFileRecord(
                action=actions[idx] if idx < len(actions) and actions[idx] else 'edit',
                path=any_to_rel(depot_file),
                depot_file=depot_file,
                rev=revs[idx] if idx < len(revs) and revs[idx] else '',
                file_type=types[idx] if idx < len(types) and types[idx] else 'text',
            )
        )

    if rec.diff and rec.files:
        sections = _split_diff_by_path(rec.diff)
        for file_rec in rec.files:
            if file_rec.path in sections:
                file_rec.diff = sections[file_rec.path]
                file_rec.diff_loaded = True
    rec.loaded = True


def _print_revision(revision: str, should_cancel) -> str:
    return _run_p4_cancellable(['print', '-q', revision], should_cancel)


def _fetch_pending_file_diff(rec: ChangeRecord, file_rec: ChangeFileRecord, should_cancel) -> str:
    raw = _run_p4_cancellable(['describe', '-du', '-S', rec.cl], should_cancel)
    sections = _split_diff_by_path(raw)
    return sections.get(file_rec.path, '(diff unavailable)')


def _fetch_submitted_file_diff(depot: str, before_rev: int, after_rev: int, should_cancel) -> str:
    return _run_p4_cancellable(
        ['diff2', '-du', f'{depot}#{before_rev}', f'{depot}#{after_rev}'],
        should_cancel,
    )


def _fetch_file_diff_for_change(rec: ChangeRecord, file_rec: ChangeFileRecord, should_cancel) -> str:
    if file_rec.diff_loaded:
        return file_rec.diff

    if rec.status != 'submitted':
        diff = _fetch_pending_file_diff(rec, file_rec, should_cancel)
        file_rec.diff = diff
        file_rec.diff_loaded = True
        return diff

    base_type = file_rec.file_type.split('+')[0].lower()
    if base_type in _BINARY_TYPES:
        file_rec.diff = '(binary file — diff not shown)'
        file_rec.diff_loaded = True
        return file_rec.diff

    rev_num = int(file_rec.rev) if file_rec.rev.isdigit() else None
    if rev_num is None:
        file_rec.diff = '(diff unavailable)'
        file_rec.diff_loaded = True
        return file_rec.diff

    rel = file_rec.path
    depot = file_rec.depot_file

    try:
        if file_rec.action in _ADD_ACTIONS:
            after = _print_revision(f'{depot}#{rev_num}', should_cancel)
            diff = make_unified_diff('', after, fromfile='/dev/null', tofile=f'b/{rel}') or '(no differences)'
        elif file_rec.action in _DELETE_ACTIONS:
            before = _print_revision(f'{depot}#{max(rev_num - 1, 1)}', should_cancel)
            diff = make_unified_diff(before, '', fromfile=f'a/{rel}', tofile='/dev/null') or '(no differences)'
        else:
            diff = _fetch_submitted_file_diff(depot, max(rev_num - 1, 1), rev_num, should_cancel) or '(no differences)'
    except P4Error as exc:
        diff = f'(diff unavailable: {exc})'

    file_rec.diff = diff
    file_rec.diff_loaded = True
    return diff


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


class DiffView(FastScrollableContainer):
    DEFAULT_CSS = """
    DiffView {
        border: solid $panel-lighten-1;
        padding: 0 1;
        overflow-y: scroll;
    }
    """

    _LOADING_FRAMES = ['[    ]', '[=   ]', '[==  ]', '[=== ]', '[ ===]', '[  ==]', '[   =]']

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._loading_timer: Any = None
        self._loading_index = 0
        self._loading_message = ''

    def _stop_loading_animation(self) -> None:
        if self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer = None
        self._loading_index = 0
        self._loading_message = ''

    def _start_loading_animation(self, message: str) -> None:
        self._stop_loading_animation()
        self._loading_message = message
        self._loading_index = 0
        self._update_loading_status()
        self._loading_timer = self.set_interval(0.1, self._advance_loading_animation)

    def _advance_loading_animation(self) -> None:
        self._loading_index = (self._loading_index + 1) % len(self._LOADING_FRAMES)
        self._update_loading_status()

    def _update_loading_status(self) -> None:
        status = self.query_one('#loading-status', Static)
        frame = self._LOADING_FRAMES[self._loading_index]
        status.update(Text.from_markup(f'[dim]{frame} {self._loading_message}[/dim]'))
        status.refresh()

    def _mount_widgets(self, widgets: list[Widget]) -> None:
        self._stop_loading_animation()
        self.remove_children()
        for widget in widgets:
            self.mount(widget)
        self.scroll_home(animate=False)

    def show_change_loading(self) -> None:
        self._mount_widgets([Static('', id='loading-status', markup=True)])
        self._start_loading_animation('Loading changelist details...')

    def show_file_loading(self, rec: ChangeRecord, file_rec: ChangeFileRecord) -> None:
        self._mount_widgets([
            Static(f'[bold white]CL {rec.cl}[/bold white]  [dim]{rec.date}[/dim]  [yellow]{rec.user}[/yellow]', markup=True),
            Static(f'  [white]{rec.description}[/white]', markup=True),
            Static(''),
            Static('', id='loading-status', markup=True),
            Static('[dim]Esc: cancel and return to files[/dim]', markup=True),
        ])
        self._start_loading_animation(f'Loading diff for [cyan]{_esc(file_rec.path)}[/cyan]')

    def show_change_summary(self, rec: ChangeRecord, selected_index: int) -> None:
        widgets: list[Widget] = [
            Static(f'[bold white]CL {rec.cl}[/bold white]  [dim]{rec.date}[/dim]  [yellow]{rec.user}[/yellow]', markup=True),
            Static(f'  [white]{rec.description}[/white]', markup=True),
            Static(''),
        ]
        if rec.files:
            widgets.append(Static('[bold white]Files:[/bold white]', markup=True))
            for idx, file_rec in enumerate(rec.files):
                letter = T.STATE_LETTER.get(file_rec.action, 'M')
                color = T.ACTION_COLOR.get(file_rec.action, 'white')
                prefix = '›' if idx == selected_index else ' '
                style = 'reverse' if idx == selected_index else 'dim'
                widgets.append(Static(
                    f'[{style}]{prefix}[/{style}] [{color}]{letter}[/{color}]  {_esc(file_rec.path)}',
                    markup=True,
                ))
            widgets.append(Static(''))
            widgets.append(Static('[dim]j/k: select file  Enter: open diff  Esc: back[/dim]', markup=True))
        else:
            widgets.append(Static('[dim](no files in this changelist)[/dim]', markup=True))
        self._mount_widgets(widgets)

    def show_file_diff(
        self,
        rec: ChangeRecord,
        file_rec: ChangeFileRecord,
        *,
        ignore_whitespace: bool,
        side_by_side: bool,
    ) -> None:
        whitespace = 'ignored' if ignore_whitespace else 'significant'
        view_mode = 'side-by-side' if side_by_side else 'unified'
        column_width = (
            side_by_side_column_width(self.scrollable_content_region.width or self.size.width)
            if side_by_side
            else DEFAULT_SIDE_BY_SIDE_COLUMN_WIDTH
        )
        widgets: list[Widget] = [
            Static(f'[bold white]CL {rec.cl}[/bold white]  [dim]{rec.date}[/dim]  [yellow]{rec.user}[/yellow]', markup=True),
            Static(f'  [white]{rec.description}[/white]', markup=True),
            Static(f'[bold white]File:[/bold white] [cyan]{_esc(file_rec.path)}[/cyan]  [dim]{file_rec.action}[/dim]', markup=True),
            Static(f'[dim]Whitespace: {whitespace}  View: {view_mode}[/dim]', markup=True),
            Static(''),
        ]
        for line in _render_diff_lines(
            file_rec.diff,
            ignore_whitespace=ignore_whitespace,
            side_by_side=side_by_side,
            column_width=column_width,
        ):
            widgets.append(Static(line))
        self._mount_widgets(widgets)

    def show_placeholder(self) -> None:
        self._mount_widgets([
            Static(
                '[dim]Press [bold]Enter[/bold] on a changelist to view its description and files[/dim]',
                markup=True,
            )
        ])


_HUNK_RE   = re.compile(r"^(@@ .+? @@)(.*)")
_HEADER_RE = re.compile(r"^==== (.+?)#(\d+)")

# ── Syntax highlighting ───────────────────────────────────────────────────────

# VS Code Dark+ inspired token → Rich style mapping (most-specific first)
from pygments.token import Token  # noqa: E402

_TOKEN_STYLES: list[tuple] = [
    (Token.Comment,                    "italic #6A9955"),
    (Token.Keyword.Type,               "#4EC9B0"),
    (Token.Keyword,                    "bold #569CD6"),
    (Token.Name.Function.Magic,        "#DCDCAA"),
    (Token.Name.Function,              "#DCDCAA"),
    (Token.Name.Class,                 "#4EC9B0"),
    (Token.Name.Builtin.Pseudo,        "#569CD6"),
    (Token.Name.Builtin,               "#4EC9B0"),
    (Token.Name.Decorator,             "#C586C0"),
    (Token.Name.Namespace,             "#4EC9B0"),
    (Token.Name.Attribute,             "#9CDCFE"),
    (Token.Name.Tag,                   "#569CD6"),
    (Token.Literal.String.Interpol,    "#569CD6"),
    (Token.Literal.String,             "#CE9178"),
    (Token.Literal.Number,             "#B5CEA8"),
    (Token.Operator.Word,              "bold #569CD6"),
    (Token.Operator,                   "#D4D4D4"),
    (Token.Punctuation,                "#D4D4D4"),
    (Token.Generic.Heading,            "bold"),
    (Token.Name,                       "#9CDCFE"),
]


def _get_lexer(depot_path: str):
    """Return a Pygments lexer for the given file path, or None."""
    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound
    try:
        return get_lexer_for_filename(depot_path, stripall=True)
    except ClassNotFound:
        return None


def _token_style(ttype) -> str | None:
    for token_type, style in _TOKEN_STYLES:
        if ttype in token_type:
            return style
    return None


def _highlight(code: str, lexer) -> str:
    """Tokenize `code` and return Rich markup string with syntax colors."""
    if lexer is None:
        return _esc(code)
    result = ""
    for ttype, value in lexer.get_tokens(code):
        if value in ("\n", ""):
            continue
        style   = _token_style(ttype)
        escaped = _esc(value)
        result += f"[{style}]{escaped}[/{style}]" if style else escaped
    return result


# ── Diff renderer ─────────────────────────────────────────────────────────────

def _colorize_diff(raw: str, *, ignore_whitespace: bool = False) -> list[str]:
    raw = filter_unified_diff(raw, ignore_whitespace=ignore_whitespace)
    if not raw.strip():
        return ["[dim](no differences)[/dim]"]
    out: list[str] = []
    lexer = None   # updated each time we see a new file header

    for line in raw.splitlines():
        if re.match(r"^(Change|Date|User|Client|Description|Files|Affected|Differences).*:", line):
            continue

        if m := _HEADER_RE.match(line):
            rel   = any_to_rel(m.group(1))
            lexer = _get_lexer(m.group(1))
            out.append(f"[bold white]diff {_esc(rel)}[/bold white]")

        elif line.startswith("--- ") or line.startswith("+++ "):
            # Unified diff file markers — show dimly, no syntax
            out.append(f"[dim]{_esc(line)}[/dim]")

        elif line.startswith("@@"):
            if hm := _HUNK_RE.match(line):
                out.append(
                    f"[bold {T.DIFF_HUNK}]{_esc(hm.group(1))}[/bold {T.DIFF_HUNK}]"
                    f"[dim]{_esc(hm.group(2))}[/dim]"
                )
            else:
                out.append(f"[bold {T.DIFF_HUNK}]{_esc(line)}[/bold {T.DIFF_HUNK}]")

        elif line.startswith("+"):
            highlighted = _highlight(line[1:], lexer)
            out.append(
                f"[bold {T.DIFF_ADD} {T.DIFF_ADD_BG}]+[/bold {T.DIFF_ADD} {T.DIFF_ADD_BG}]"
                f"[{T.DIFF_ADD_BG}]{highlighted}[/{T.DIFF_ADD_BG}]"
            )

        elif line.startswith("-"):
            highlighted = _highlight(line[1:], lexer)
            out.append(
                f"[bold {T.DIFF_DEL} {T.DIFF_DEL_BG}]-[/bold {T.DIFF_DEL} {T.DIFF_DEL_BG}]"
                f"[{T.DIFF_DEL_BG}]{highlighted}[/{T.DIFF_DEL_BG}]"
            )

        else:
            # Context line — syntax-highlight but no diff color
            out.append(f"[dim] [/dim]{_highlight(line[1:] if line.startswith(' ') else line, lexer)}")

    return out


def _esc(s: str) -> str:
    return markup_escape(s)


def _render_diff_lines(
    raw: str,
    *,
    ignore_whitespace: bool = False,
    side_by_side: bool = False,
    column_width: int = DEFAULT_SIDE_BY_SIDE_COLUMN_WIDTH,
) -> list[Text]:
    if side_by_side:
        rendered: list[Text] = []
        for line in build_side_by_side_lines(
            raw,
            ignore_whitespace=ignore_whitespace,
            column_width=column_width,
        ):
            if line.kind == "file":
                rendered.append(Text(line.text, style="bold white"))
                continue
            if line.kind == "hunk":
                text_line = Text()
                if hm := _HUNK_RE.match(line.text):
                    text_line.append(hm.group(1), style=f"bold {T.DIFF_HUNK}")
                    text_line.append(hm.group(2), style="dim")
                else:
                    text_line.append(line.text, style=f"bold {T.DIFF_HUNK}")
                rendered.append(text_line)
                continue
            if line.kind == "message":
                rendered.append(Text(line.text, style="dim"))
                continue

            text_line = Text()
            left = line.left_cell_text()
            right = line.right_cell_text()
            if line.left_kind == "remove":
                text_line.append(left, style=f"{T.DIFF_DEL} {T.DIFF_DEL_BG}")
            elif line.left_kind == "context":
                text_line.append(left, style="dim")
            else:
                text_line.append(left)

            text_line.append(" │ ", style="dim")

            if line.right_kind == "add":
                text_line.append(right, style=f"{T.DIFF_ADD} {T.DIFF_ADD_BG}")
            elif line.right_kind == "context":
                text_line.append(right, style="dim")
            else:
                text_line.append(right)

            rendered.append(text_line)
        return rendered
    return [Text.from_markup(line) for line in _colorize_diff(raw, ignore_whitespace=ignore_whitespace)]


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
        Binding("enter",  "activate",     "Open",   show=False),
        Binding("j",      "cursor_down",  "Down",   show=False),
        Binding("down",   "cursor_down",  "Down",   show=False),
        Binding("k",      "cursor_up",    "Up",     show=False),
        Binding("up",     "cursor_up",    "Up",     show=False),
        Binding("b",      "toggle_side_by_side", "View", show=False),
        Binding("w",      "toggle_whitespace", "Whitespace", show=False),
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
        p4_path: str = "//...",
        demo_records: list[ChangeRecord] | None = None,
    ) -> None:
        super().__init__()
        self._user = user
        self._max_cls = max_cls
        self._cl_status = cl_status
        self._p4_path = p4_path
        self._demo_records = demo_records
        self._records: list[ChangeRecord] = []
        self._filtered: list[ChangeRecord] = []
        self._filter_buf = ""
        self._filtering = False
        self._filter_just_committed = False
        self._ignore_whitespace = False
        self._side_by_side = False
        self._detail_rec: ChangeRecord | None = None
        self._detail_file_index = 0
        self._detail_diff_file: ChangeFileRecord | None = None
        self._detail_diff_loading = False
        self._detail_diff_request_id = 0

    def compose(self) -> ComposeResult:
        path_hint = "" if self._p4_path == "//..." else f"  [dim cyan]{any_to_rel(self._p4_path.removesuffix('/...'))}[/dim cyan]"
        yield Static(
            f"[bold]p5 changes[/bold]  [dim]— Perforce changelist browser[/dim]{path_hint}",
            id="header-bar", markup=True,
        )
        yield Static(
            f"[dim]{'CL':>8}  {'Date':<10}  {'Author':<12}  Description[/dim]",
            id="col-headers", markup=True,
        )
        yield FastListView(id="list-view")
        yield DiffView(id="detail-view")
        yield Static("", id="filter-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_changes()

    @work(thread=True)
    def _load_changes(self) -> None:
        if self._demo_records is not None:
            self._records = list(self._demo_records)
            self._run_filter()
            self.call_from_thread(self._rebuild_list)
            return
        try:
            self._records = _fetch_changes(self._user, self._max_cls, self._cl_status, self._p4_path)
            self._run_filter()
            self.call_from_thread(self._rebuild_list)
        except P4Error as e:
            self.call_from_thread(self._show_error, str(e))

    def _show_error(self, msg: str) -> None:
        lv = self.query_one('#list-view', ListView)
        lv.append(ListItem(Static(f"[red]error: {msg}[/red]", markup=True)))

    def _run_filter(self) -> None:
        q = self._filter_buf.lower()
        if q:
            self._filtered = [
                r for r in self._records
                if q in r.cl or q in r.user.lower() or q in r.description.lower()
            ]
        else:
            self._filtered = list(self._records)

    def _rebuild_list(self) -> None:
        lv = self.query_one('#list-view', ListView)
        lv.clear()
        for rec in self._filtered:
            lv.append(ChangeItem(rec))
        if self._filtered:
            lv.index = 0

    def _current_change(self) -> ChangeRecord | None:
        lv = self.query_one('#list-view', ListView)
        child = lv.highlighted_child
        if isinstance(child, ChangeItem):
            return child.rec
        return None

    def _current_file(self) -> ChangeFileRecord | None:
        if self._detail_rec is None or not self._detail_rec.files:
            return None
        index = max(0, min(self._detail_file_index, len(self._detail_rec.files) - 1))
        self._detail_file_index = index
        return self._detail_rec.files[index]

    def action_activate(self) -> None:
        if self._filtering:
            return
        if not self.detail_open:
            rec = self._current_change()
            if rec is not None:
                self._open_detail(rec)
            return
        if self._detail_diff_file is None and not self._detail_diff_loading:
            self._open_selected_file_diff()

    def action_cursor_down(self) -> None:
        if self._filtering:
            return
        if not self.detail_open:
            self.query_one('#list-view', ListView).action_cursor_down()
            return
        if self._detail_diff_file is None and self._detail_rec is not None and self._detail_rec.files:
            self._detail_file_index = min(self._detail_file_index + 1, len(self._detail_rec.files) - 1)
            self._render_detail_summary()
            return
        self.query_one('#detail-view', DiffView).scroll_relative(y=3)

    def action_cursor_up(self) -> None:
        if self._filtering:
            return
        if not self.detail_open:
            self.query_one('#list-view', ListView).action_cursor_up()
            return
        if self._detail_diff_file is None and self._detail_rec is not None and self._detail_rec.files:
            self._detail_file_index = max(self._detail_file_index - 1, 0)
            self._render_detail_summary()
            return
        self.query_one('#detail-view', DiffView).scroll_relative(y=-3)

    def action_collapse(self) -> None:
        if self._filtering:
            self._cancel_filter()
            return
        if not self.detail_open:
            return
        if self._detail_diff_loading or self._detail_diff_file is not None:
            self._cancel_diff_request()
            self._detail_diff_loading = False
            self._detail_diff_file = None
            self._render_detail_summary()
            return
        self._close_detail()

    def action_start_filter(self) -> None:
        if self.detail_open:
            return
        self._filtering = True
        self._filter_just_committed = False
        self._filter_buf = ''
        fb = self.query_one('#filter-bar', Static)
        fb.add_class('active')
        fb.update('[bold cyan]Filter:[/bold cyan] _')

    def action_reload(self) -> None:
        self._cancel_diff_request()
        self._close_detail()
        self._records.clear()
        self._filtered.clear()
        self.query_one('#list-view', ListView).clear()
        self._load_changes()

    def action_toggle_whitespace(self) -> None:
        self._ignore_whitespace = not self._ignore_whitespace
        if self.detail_open and self._detail_diff_file is not None and self._detail_rec is not None:
            self.query_one('#detail-view', DiffView).show_file_diff(
                self._detail_rec,
                self._detail_diff_file,
                ignore_whitespace=self._ignore_whitespace,
                side_by_side=self._side_by_side,
            )

    def action_toggle_side_by_side(self) -> None:
        self._side_by_side = not self._side_by_side
        if self.detail_open and self._detail_diff_file is not None and self._detail_rec is not None:
            self.query_one('#detail-view', DiffView).show_file_diff(
                self._detail_rec,
                self._detail_diff_file,
                ignore_whitespace=self._ignore_whitespace,
                side_by_side=self._side_by_side,
            )

    def on_resize(self) -> None:
        if self.detail_open and self._detail_rec is not None and self._detail_diff_file is not None:
            self.query_one('#detail-view', DiffView).show_file_diff(
                self._detail_rec,
                self._detail_diff_file,
                ignore_whitespace=self._ignore_whitespace,
                side_by_side=self._side_by_side,
            )

    def on_key(self, event) -> None:
        if self.detail_open and not self._filtering and event.key == 'enter':
            self.action_activate()
            event.stop()
            return
        if not self._filtering:
            return
        key = event.key
        if key == 'enter':
            self._commit_filter()
        elif key == 'escape':
            self._cancel_filter()
        elif key == 'backspace':
            self._filter_buf = self._filter_buf[:-1]
            self._update_filter_bar()
        elif event.character and event.character.isprintable():
            self._filter_buf += event.character
            self._update_filter_bar()
        else:
            return
        event.stop()

    def _update_filter_bar(self) -> None:
        self.query_one('#filter-bar', Static).update(f"[bold cyan]Filter:[/bold cyan] {_esc(self._filter_buf)}_")

    def _commit_filter(self) -> None:
        self._filtering = False
        self._filter_just_committed = True
        fb = self.query_one('#filter-bar', Static)
        fb.remove_class('active')
        if self._filter_buf:
            fb.update(f"[bold cyan]Filter:[/bold cyan] {_esc(self._filter_buf)}")
            fb.add_class('active')
        self._run_filter()
        self._rebuild_list()

    def _cancel_filter(self) -> None:
        self._filtering = False
        self._filter_buf = ''
        fb = self.query_one('#filter-bar', Static)
        fb.remove_class('active')
        self._run_filter()
        self._rebuild_list()

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        if self.detail_open or self._filtering:
            return
        if self._filter_just_committed:
            self._filter_just_committed = False
            return
        if isinstance(event.item, ChangeItem):
            self._open_detail(event.item.rec)

    def _open_detail(self, rec: ChangeRecord) -> None:
        self._cancel_diff_request()
        self._detail_file_index = 0
        self._detail_diff_file = None
        self._detail_diff_loading = False
        self._detail_rec = rec
        self.query_one('#list-view', ListView).display = False
        dv = self.query_one('#detail-view', DiffView)
        dv.display = True
        dv.focus()
        self.detail_open = True
        if rec.loaded:
            self._render_detail_summary()
        else:
            dv.show_change_loading()
            self._load_detail_summary(rec)

    def _close_detail(self) -> None:
        self._cancel_diff_request()
        self.query_one('#detail-view', DiffView).display = False
        lv = self.query_one('#list-view', ListView)
        lv.display = True
        lv.focus()
        self.detail_open = False
        self._detail_rec = None
        self._detail_diff_file = None
        self._detail_diff_loading = False

    def _render_detail_summary(self) -> None:
        if self._detail_rec is None:
            return
        self.query_one('#detail-view', DiffView).show_change_summary(self._detail_rec, self._detail_file_index)

    def _open_selected_file_diff(self) -> None:
        if self._detail_rec is None:
            return
        file_rec = self._current_file()
        if file_rec is None:
            return
        if file_rec.diff_loaded:
            self._detail_diff_loading = False
            self._detail_diff_file = file_rec
            self.query_one('#detail-view', DiffView).show_file_diff(
                self._detail_rec,
                file_rec,
                ignore_whitespace=self._ignore_whitespace,
                side_by_side=self._side_by_side,
            )
            return
        self._detail_diff_loading = True
        self._detail_diff_file = None
        request_id = self._next_diff_request_id()
        self.query_one('#detail-view', DiffView).show_file_loading(self._detail_rec, file_rec)
        self._load_file_diff(self._detail_rec, file_rec, request_id)

    def _next_diff_request_id(self) -> int:
        self._detail_diff_request_id += 1
        return self._detail_diff_request_id

    def _cancel_diff_request(self) -> None:
        self._detail_diff_request_id += 1

    @work(thread=True)
    def _load_detail_summary(self, rec: ChangeRecord) -> None:
        if self._demo_records is None:
            try:
                _fetch_detail_summary(rec)
            except P4Error as exc:
                if self._detail_rec is rec and self.detail_open:
                    self.call_from_thread(self._show_error, str(exc))
                return
        if self._detail_rec is rec and self.detail_open:
            self.call_from_thread(self._render_detail_summary)

    @work(thread=True)
    def _load_file_diff(self, rec: ChangeRecord, file_rec: ChangeFileRecord, request_id: int) -> None:
        def should_cancel() -> bool:
            return request_id != self._detail_diff_request_id or self._detail_rec is not rec or not self.detail_open

        try:
            _fetch_file_diff_for_change(rec, file_rec, should_cancel)
        except _CancelledFetch:
            return

        if should_cancel():
            return

        def finish() -> None:
            if should_cancel():
                return
            self._detail_diff_loading = False
            self._detail_diff_file = file_rec
            self.query_one('#detail-view', DiffView).show_file_diff(
                rec,
                file_rec,
                ignore_whitespace=self._ignore_whitespace,
                side_by_side=self._side_by_side,
            )

        self.call_from_thread(finish)
