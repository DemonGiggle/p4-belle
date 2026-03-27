"""Depot root detection and path mapping between local, relative, and depot paths."""
from __future__ import annotations

import os
import re
from functools import cached_property
from pathlib import Path

from p5.p4 import P4Error, run_p4


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
    def depot_prefix(self) -> str:
        """The depot-side root path (e.g. '//depot/project') for this workspace."""
        raw = run_p4(["client", "-o"])
        # Parse the View section: first mapping line tells us the depot prefix
        in_view = False
        for line in raw.splitlines():
            if line.startswith("View:"):
                in_view = True
                continue
            if in_view:
                if not line.startswith("\t") and not line.startswith(" "):
                    break
                # Line like: \t//depot/project/... //client/...
                m = re.match(r"\s+(//[^\s]+)/\.\.\.", line)
                if m:
                    return m.group(1)
        # Fallback: use first two components of any depot path we can find
        return "//"

    def local_to_depot(self, path: str) -> str:
        """Convert a local or relative path to its depot path.

        Accepts:
        - Absolute local path: /home/gigo/workspace/project/src/foo.cpp
        - Relative path (from cwd): src/foo.cpp or ./src/foo.cpp
        - Depot path (pass-through): //depot/project/src/foo.cpp
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
        return self.depot_prefix + "/" + rel_str

    def depot_to_rel(self, depot_path: str) -> str:
        """Convert a depot path to a relative path from client root."""
        if not depot_path.startswith("//"):
            return depot_path
        prefix = self.depot_prefix.rstrip("/") + "/"
        if depot_path.startswith(prefix):
            return depot_path[len(prefix):]
        # Try stripping any //server/depot/ prefix using p4 client view
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
