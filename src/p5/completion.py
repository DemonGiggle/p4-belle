"""Shell completion helpers for p5 CLI arguments."""
from __future__ import annotations

from click.shell_completion import CompletionItem


def _safe(fn):
    """Wrap a completer so any p4/import error returns an empty list."""
    def wrapper(ctx, param, incomplete):
        try:
            return fn(ctx, param, incomplete)
        except Exception:
            return []
    return wrapper


@_safe
def complete_opened_files(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete relative paths of files currently opened in p4."""
    from p5.p4 import run_p4_tagged
    from p5.workspace import any_to_rel
    records = run_p4_tagged(["opened"])
    return [
        CompletionItem(any_to_rel(r["depotFile"]))
        for r in records
        if r.get("depotFile") and any_to_rel(r["depotFile"]).startswith(incomplete)
    ]


@_safe
def complete_pending_cls(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete pending changelist numbers."""
    from p5.p4 import run_p4_tagged
    records = run_p4_tagged(["changes", "-s", "pending", "-m", "30"])
    items = []
    for r in records:
        cl   = r.get("change", "")
        desc = (r.get("desc") or "").strip().replace("\n", " ")[:60]
        if cl.startswith(incomplete):
            items.append(CompletionItem(cl, help=desc))
    return items


@_safe
def complete_any_cl(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete CL numbers from recent submitted + pending changes."""
    from p5.p4 import run_p4_tagged
    items = []
    for status in ("pending", "submitted"):
        records = run_p4_tagged(["changes", "-s", status, "-m", "20"])
        for r in records:
            cl   = r.get("change", "")
            desc = (r.get("desc") or "").strip().replace("\n", " ")[:60]
            if cl.startswith(incomplete):
                items.append(CompletionItem(cl, help=f"[{status}] {desc}"))
    return items


@_safe
def complete_depot_path(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete a depot or local path using p4 dirs/files."""
    import os
    from p5.p4 import run_p4
    from p5.workspace import any_to_rel, local_to_depot

    if incomplete.startswith("//"):
        base = incomplete
    else:
        # Treat as local path — convert what we have so far to a depot prefix
        base = local_to_depot(incomplete or ".")

    # Complete directories first
    try:
        dirs_raw = run_p4(["dirs", base + "*"], check=False)
        dirs = [
            any_to_rel(line.strip()) + "/"
            for line in dirs_raw.splitlines()
            if line.strip()
        ]
    except Exception:
        dirs = []

    # Then files
    try:
        files_raw = run_p4(["files", base + "*"], check=False)
        files = []
        for line in files_raw.splitlines():
            # p4 files output: //depot/path/file#rev - action
            depot_path = line.split("#")[0].strip()
            if depot_path:
                files.append(any_to_rel(depot_path))
    except Exception:
        files = []

    candidates = dirs + files
    rel_incomplete = any_to_rel(incomplete) if incomplete else ""
    return [
        CompletionItem(c)
        for c in candidates
        if c.startswith(rel_incomplete)
    ]


def _filesystem_candidates(incomplete: str) -> list[CompletionItem]:
    """Return on-disk path completions matching incomplete (cwd-relative)."""
    import os
    from pathlib import Path

    if incomplete.startswith("//"):
        return []
    try:
        if incomplete == "" or incomplete.endswith(("/", os.sep)):
            base_dir = Path(incomplete or ".")
            prefix = ""
            dir_part = incomplete or ""
        elif "/" in incomplete or os.sep in incomplete:
            sep = "/" if "/" in incomplete else os.sep
            dir_part, _, prefix = incomplete.rpartition(sep)
            dir_part += sep
            base_dir = Path(dir_part or ".")
        else:
            base_dir = Path(".")
            prefix = incomplete
            dir_part = ""
        try:
            entries = list(base_dir.iterdir())
        except OSError:
            return []
        items = []
        for e in sorted(entries, key=lambda p: p.name):
            if not e.name.startswith(prefix):
                continue
            comp = f"{dir_part}{e.name}"
            if e.is_dir():
                comp += "/"
            items.append(CompletionItem(comp))
        return items
    except Exception:
        return []


@_safe
def complete_add_files(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete untracked files for `p5 add`.

    Primary source is `p4 reconcile -n -a` candidates; always also
    includes on-disk matches so TAB still suggests something when
    reconcile is empty or p4 is unavailable.
    """
    from p5.p4 import run_p4_tagged
    from p5.workspace import any_to_rel

    seen: dict[str, None] = {}
    try:
        records = run_p4_tagged(["reconcile", "-n", "-a"])
    except Exception:
        records = []
    for r in records:
        raw = (
            r.get("depotFile")
            or r.get("clientFile")
            or r.get("localFile")
            or r.get("path")
            or ""
        )
        if not raw:
            continue
        try:
            rel = any_to_rel(raw)
        except Exception:
            continue
        if rel.startswith(incomplete):
            seen[rel] = None
    for item in _filesystem_candidates(incomplete):
        if item.value not in seen:
            seen[item.value] = None
    return [CompletionItem(v) for v in seen]


@_safe
def complete_edit_files(ctx, param, incomplete: str) -> list[CompletionItem]:
    """Complete versioned files for `p5 edit`.

    Reuses depot-path logic (all tracked files), not just `p4 opened`.
    """
    return complete_depot_path(ctx, param, incomplete)
