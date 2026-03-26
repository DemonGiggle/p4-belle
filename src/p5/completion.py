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
