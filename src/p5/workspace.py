"""Depot root detection and path mapping between local, relative, and depot paths."""
from __future__ import annotations

import os
import shlex
from functools import cached_property
from pathlib import Path

from p5.p4 import P4Error, run_p4


def _parse_view_mappings(raw: str) -> list[tuple[str, str]]:
    """Parse all View mappings from `p4 client -o` output.

    Returns an ordered list of (depot_base, client_rel) tuples where
    depot_base is e.g. '//depot/main' and client_rel is the client-side
    subpath relative to the client root (e.g. 'main', 'libs/foo', or ''
    for a root mapping like '//client/...').

    Exclusion ('-//...') lines are skipped. Overlay ('+//...') lines are
    treated as normal mappings after stripping the leading '+'.
    """
    mappings: list[tuple[str, str]] = []
    in_view = False
    for line in raw.splitlines():
        if line.startswith("View:"):
            in_view = True
            continue
        if not in_view:
            continue
        if not line.startswith("\t") and not line.startswith(" "):
            break
        stripped = line.strip()
        if not stripped:
            continue
        # Skip exclusion lines: "-//depot/... //client/..."
        if stripped.startswith("-"):
            continue
        # Overlay lines: "+//depot/... //client/..." -> treat as normal
        if stripped.startswith("+"):
            stripped = stripped[1:].lstrip()
            if not stripped:
                continue
        try:
            parts = shlex.split(stripped, posix=True)
        except ValueError:
            parts = stripped.split()
        if len(parts) < 2:
            continue
        depot_token, client_token = parts[0], parts[1]

        # Depot side: strip trailing "/..." (or bare "...").
        if depot_token.endswith("/..."):
            depot_base = depot_token[:-4]
        elif depot_token.endswith("..."):
            depot_base = depot_token[:-3].rstrip("/")
        else:
            depot_base = depot_token
            # Non-trivial wildcards (*, %%) can't be resolved by prefix
            # matching — skip them rather than mis-resolving.
            if "*" in depot_base or "%%" in depot_base:
                continue
        depot_base = depot_base.strip('"').strip("'").rstrip("/")
        if not depot_base.startswith("//"):
            continue

        # Client side: strip trailing "/..." then split off client name.
        if client_token.endswith("/..."):
            client_core = client_token[:-4]
        elif client_token.endswith("..."):
            client_core = client_token[:-3].rstrip("/")
        else:
            client_core = client_token
            if "*" in client_core or "%%" in client_core:
                continue
        client_core = client_core.strip('"').strip("'").rstrip("/")
        if not client_core.startswith("//"):
            continue
        without = client_core[2:]
        if "/" not in without:
            # e.g. "//myclient" -> root mapping
            client_rel = ""
        else:
            _, _, rel = without.partition("/")
            client_rel = rel.strip("/")
        mappings.append((depot_base, client_rel))
    return mappings


class Workspace:
    """Represents the current Perforce workspace with path resolution helpers."""

    @cached_property
    def _info(self) -> dict[str, str]:
        raw = run_p4(["info"])
        result: dict[str, str] = {}
        for line in raw.splitlines():
            if ": " in line:
                k, _, v = line.partition(": ")
                result[k.strip()] = v.strip()
        return result

    @cached_property
    def client_root(self) -> Path:
        """Local filesystem root of the workspace (from p4 info)."""
        root = self._info.get("Client root")
        if not root:
            raise P4Error("Could not determine client root from 'p4 info'")
        return Path(root).resolve()

    @cached_property
    def client_name(self) -> str:
        name = self._info.get("Client name")
        if not name:
            raise P4Error("Could not determine client name from 'p4 info'")
        return name

    @cached_property
    def view_mappings(self) -> list[tuple[str, str]]:
        """All parsed View mappings as (depot_base, client_rel) in file order."""
        raw = run_p4(["client", "-o"])
        return _parse_view_mappings(raw)

    @cached_property
    def depot_prefix(self) -> str:
        """The depot-side root path (e.g. '//depot/project') for this workspace.

        For single-mapping workspaces this is the mapping's depot side.
        For multi-mapping workspaces it is the first mapping's depot side,
        preserved for backward compatibility; use view_mappings plus
        local_to_depot/depot_to_rel for accurate multi-map resolution.
        """
        if self.view_mappings:
            return self.view_mappings[0][0]
        return "//"

    def local_to_depot(self, path: str) -> str:
        """Convert a local or relative path to its depot path.

        Accepts:
        - Absolute local path: /home/gigo/workspace/project/src/foo.cpp
        - Relative path (from cwd): src/foo.cpp or ./src/foo.cpp
        - Depot path (pass-through): //depot/project/src/foo.cpp

        With multiple View mappings, the mapping with the longest
        client-side match wins. Files under the client root but outside
        every mapping fall back to depot_prefix + rel (single-map
        behaviour).
        """
        if path.startswith("//"):
            return path
        abs_path = Path(path).resolve()
        try:
            rel = abs_path.relative_to(self.client_root)
        except ValueError:
            # Not under client root — return as-is and let p4 complain
            return path
        rel_str = str(rel).replace(os.sep, "/")
        if rel_str == ".":
            return self.depot_prefix
        best_depot: str | None = None
        best_remainder = ""
        best_len = -1
        for depot_base, client_rel in self.view_mappings:
            if client_rel == "":
                remainder = rel_str
                mlen = 0
            elif rel_str == client_rel:
                remainder = ""
                mlen = len(client_rel)
            elif rel_str.startswith(client_rel + "/"):
                remainder = rel_str[len(client_rel) + 1 :]
                mlen = len(client_rel)
            else:
                continue
            if mlen > best_len:
                best_len = mlen
                best_depot = depot_base
                best_remainder = remainder
        if best_depot is not None:
            if best_remainder:
                return best_depot.rstrip("/") + "/" + best_remainder
            return best_depot
        if rel_str == ".":
            return self.depot_prefix
        return self.depot_prefix + "/" + rel_str

    def depot_to_rel(self, depot_path: str) -> str:
        """Convert a depot path to a relative path from client root.

        With multiple View mappings, the mapping with the longest
        depot-side match wins. Paths outside every mapping are returned
        unchanged.
        """
        if not depot_path.startswith("//"):
            return depot_path
        best_rel: str | None = None
        best_len = -1
        for depot_base, client_rel in self.view_mappings:
            base = depot_base.rstrip("/")
            if depot_path == base:
                # Exact directory match: e.g. //depot/main -> "main".
                # Root mappings (client_rel == "") keep the old
                # pass-through behaviour for a bare prefix.
                candidate = client_rel if client_rel else depot_path
                mlen = len(base)
            elif depot_path.startswith(base + "/"):
                remainder = depot_path[len(base) + 1 :]
                candidate = (client_rel + "/" + remainder) if client_rel else remainder
                mlen = len(base)
            else:
                continue
            if mlen > best_len:
                best_len = mlen
                best_rel = candidate
        if best_rel is not None:
            return best_rel
        # Fallback: return the depot path unchanged
        return depot_path

    def local_to_rel(self, local_path: str) -> str:
        """Convert an absolute local path to a relative path from client root."""
        abs_path = Path(local_path).resolve()
        try:
            return str(abs_path.relative_to(self.client_root)).replace(os.sep, "/")
        except ValueError:
            return local_path

    def any_to_rel(self, path: str) -> str:
        """Accept depot path, absolute local, or relative — return relative display path."""
        if path.startswith("//"):
            return self.depot_to_rel(path)
        return self.local_to_rel(path)


# Module-level singleton — lazy, one per process
_workspace: Workspace | None = None


def get_workspace() -> Workspace:
    global _workspace
    if _workspace is None:
        _workspace = Workspace()
    return _workspace


def check_cwd_in_workspace(cwd: str | None = None) -> None:
    """Raise P4Error if cwd is not under the current client root.

    Call this early in any command that uses local paths to detect when
    the user is outside their active workspace.
    """
    ws = get_workspace()
    target = Path(cwd or os.getcwd()).resolve()
    try:
        target.relative_to(ws.client_root)
    except ValueError:
        raise P4Error(
            f"Current directory is not inside workspace '{ws.client_name}'\n"
            f"  cwd:         {target}\n"
            f"  client root: {ws.client_root}\n\n"
            f"  Use 'p5 ws' to switch to the correct workspace."
        )


def local_to_depot(path: str) -> str:
    return get_workspace().local_to_depot(path)


def depot_to_rel(path: str) -> str:
    return get_workspace().depot_to_rel(path)


def local_to_rel(path: str) -> str:
    return get_workspace().local_to_rel(path)


def any_to_rel(path: str) -> str:
    return get_workspace().any_to_rel(path)
