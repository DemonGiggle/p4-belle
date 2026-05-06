"""Shared diff generation helpers."""
from __future__ import annotations

import difflib
import re
from typing import Iterable

_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_SKIP_METADATA_RE = re.compile(r"^(Change|Date|User|Client|Description|Files|Affected|Differences).*:")
_P4_HEADER_RE = re.compile(r"^====\s+(.+?)(?:#\d+)?(?:\s+\(.+\))?\s+====$")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", "", text)


def _format_unified_range(start: int, stop: int) -> str:
    beginning = start + 1
    length = stop - start
    if length == 1:
        return str(beginning)
    if length == 0:
        beginning -= 1
    return f"{beginning},{length}"


def _grouped_opcodes(
    before: list[str],
    after: list[str],
    *,
    ignore_whitespace: bool,
    context: int = 3,
) -> list[list[tuple[str, int, int, int, int]]]:
    if ignore_whitespace:
        before_cmp = [_normalize_whitespace(line.rstrip("\r\n")) for line in before]
        after_cmp = [_normalize_whitespace(line.rstrip("\r\n")) for line in after]
    else:
        before_cmp = before
        after_cmp = after

    matcher = difflib.SequenceMatcher(None, before_cmp, after_cmp, autojunk=False)
    return list(matcher.get_grouped_opcodes(context))


def _unified_hunks(
    before: list[str],
    after: list[str],
    *,
    ignore_whitespace: bool,
    context: int = 3,
) -> list[str]:
    hunks: list[str] = []
    for group in _grouped_opcodes(before, after, ignore_whitespace=ignore_whitespace, context=context):
        tag, old_start, _, new_start, _ = group[0]
        _, _, old_stop, _, new_stop = group[-1]
        hunks.append(
            f"@@ -{_format_unified_range(old_start, old_stop)} "
            f"+{_format_unified_range(new_start, new_stop)} @@\n"
        )
        for tag, i1, i2, j1, j2 in group:
            if tag in ("equal", "replace", "delete"):
                prefix = " " if tag == "equal" else "-"
                hunks.extend(prefix + line for line in before[i1:i2])
            if tag in ("replace", "insert"):
                hunks.extend("+" + line for line in after[j1:j2])
    return hunks


def make_unified_diff(
    before_text: str,
    after_text: str,
    *,
    fromfile: str,
    tofile: str,
    ignore_whitespace: bool = False,
    context: int = 3,
) -> str:
    before = before_text.splitlines(keepends=True)
    after = after_text.splitlines(keepends=True)
    if not ignore_whitespace:
        return "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=fromfile,
                tofile=tofile,
                n=context,
            )
        )

    hunks = _unified_hunks(before, after, ignore_whitespace=True, context=context)
    if not hunks:
        return ""
    return f"--- {fromfile}\n+++ {tofile}\n{''.join(hunks)}"


def filter_unified_diff(raw: str, *, ignore_whitespace: bool) -> str:
    if not ignore_whitespace or not raw:
        return raw

    lines = raw.splitlines(keepends=True)
    out: list[str] = []
    pending_headers: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if _SKIP_METADATA_RE.match(line.rstrip("\n")):
            idx += 1
            continue

        if line.startswith(("==== ", "diff ")):
            pending_headers = [line]
            idx += 1
            continue

        if line.startswith("--- "):
            file_headers = [*pending_headers, line]
            pending_headers = []
            idx += 1
            if idx < len(lines) and lines[idx].startswith("+++ "):
                file_headers.append(lines[idx])
                idx += 1

            hunks: list[str] = []
            while idx < len(lines) and not lines[idx].startswith(("==== ", "diff ", "--- ")):
                if not lines[idx].startswith("@@"):
                    idx += 1
                    continue

                idx += 1
                before: list[str] = []
                after: list[str] = []
                while idx < len(lines) and not lines[idx].startswith(("@@", "==== ", "diff ", "--- ")):
                    hunk_line = lines[idx]
                    if hunk_line.startswith(" "):
                        before.append(hunk_line[1:])
                        after.append(hunk_line[1:])
                    elif hunk_line.startswith("-"):
                        before.append(hunk_line[1:])
                    elif hunk_line.startswith("+"):
                        after.append(hunk_line[1:])
                    idx += 1

                hunks.extend(_unified_hunks(before, after, ignore_whitespace=True))

            if hunks:
                out.extend(file_headers)
                out.extend(hunks)
            continue

        if pending_headers:
            out.extend(pending_headers)
            pending_headers = []
        if not _HUNK_HEADER_RE.match(line):
            out.append(line)
        idx += 1

    if pending_headers:
        out.extend(pending_headers)
    return "".join(out)


def diff_has_changes(raw: str) -> bool:
    return any(line[:1] in "+-" and not line.startswith(("+++ ", "--- ")) for line in raw.splitlines())


def join_rendered_diffs(parts: Iterable[str]) -> str:
    kept = [part.rstrip("\n") for part in parts if part and diff_has_changes(part)]
    if not kept:
        return ""
    return "\n\n".join(kept) + "\n"


def _display_path(fromfile: str, tofile: str) -> str:
    for candidate in (tofile, fromfile):
        if candidate and candidate != "/dev/null":
            if candidate.startswith(("a/", "b/")):
                return candidate[2:]
            return candidate
    return "(unknown)"


def _fit_side(text: str, width: int) -> str:
    text = text.expandtabs(4)
    if len(text) > width:
        return text[: max(1, width - 1)] + "…"
    return text.ljust(width)


def _format_side_by_side_row(left_prefix: str, left: str, right_prefix: str, right: str, width: int) -> str:
    return f"{left_prefix} {_fit_side(left, width)} │ {right_prefix} {_fit_side(right, width)}"


def render_side_by_side(
    raw: str,
    *,
    ignore_whitespace: bool = False,
    column_width: int = 56,
) -> list[str]:
    raw = filter_unified_diff(raw, ignore_whitespace=ignore_whitespace)
    if not raw.strip():
        return ["(no differences)"]

    lines = raw.splitlines()
    out: list[str] = []
    idx = 0
    pending_p4_header: str | None = None

    while idx < len(lines):
        line = lines[idx]
        if _SKIP_METADATA_RE.match(line):
            idx += 1
            continue

        if match := _P4_HEADER_RE.match(line):
            pending_p4_header = match.group(1)
            idx += 1
            continue

        if line.startswith("diff "):
            out.append(line)
            idx += 1
            continue

        if line.startswith("--- "):
            fromfile = line[4:]
            idx += 1
            tofile = ""
            if idx < len(lines) and lines[idx].startswith("+++ "):
                tofile = lines[idx][4:]
                idx += 1
            out.append(f"diff {pending_p4_header or _display_path(fromfile, tofile)}")
            pending_p4_header = None
            continue

        if line.startswith("@@"):
            out.append(line)
            idx += 1
            hunk_lines: list[str] = []
            while idx < len(lines) and not lines[idx].startswith(("@@", "==== ", "diff ", "--- ")):
                hunk_lines.append(lines[idx])
                idx += 1

            cursor = 0
            while cursor < len(hunk_lines):
                current = hunk_lines[cursor]
                if current.startswith(" "):
                    text = current[1:]
                    out.append(_format_side_by_side_row(" ", text, " ", text, column_width))
                    cursor += 1
                    continue

                if current.startswith("-"):
                    removed: list[str] = []
                    added: list[str] = []
                    while cursor < len(hunk_lines) and hunk_lines[cursor].startswith("-"):
                        removed.append(hunk_lines[cursor][1:])
                        cursor += 1
                    while cursor < len(hunk_lines) and hunk_lines[cursor].startswith("+"):
                        added.append(hunk_lines[cursor][1:])
                        cursor += 1
                    for row in range(max(len(removed), len(added))):
                        left = removed[row] if row < len(removed) else ""
                        right = added[row] if row < len(added) else ""
                        left_prefix = "-" if row < len(removed) else " "
                        right_prefix = "+" if row < len(added) else " "
                        out.append(_format_side_by_side_row(left_prefix, left, right_prefix, right, column_width))
                    continue

                if current.startswith("+"):
                    added: list[str] = []
                    while cursor < len(hunk_lines) and hunk_lines[cursor].startswith("+"):
                        added.append(hunk_lines[cursor][1:])
                        cursor += 1
                    for text in added:
                        out.append(_format_side_by_side_row(" ", "", "+", text, column_width))
                    continue

                cursor += 1
            continue

        pending_p4_header = None
        out.append(line)
        idx += 1

    return out
