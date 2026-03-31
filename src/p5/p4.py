"""Low-level p4 subprocess wrapper."""
from __future__ import annotations

import re
import subprocess
from typing import Any


_INDEXED_KEY_RE = re.compile(r"^(.+?)(\d+)$")


class P4Error(Exception):
    """Raised when p4 exits with a non-zero status or reports an error."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


def run_p4(args: list[str], *, cwd: str | None = None, check: bool = True) -> str:
    """Run a p4 command and return stdout as a string."""
    cmd = ["p4"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise P4Error("p4 command not found — is Perforce installed and on PATH?")
    if check and result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise P4Error(msg, result.returncode)
    return result.stdout


def run_p4_tagged(args: list[str], *, cwd: str | None = None) -> list[dict[str, Any]]:
    """Run a p4 command with -ztag and return a list of record dicts."""
    raw = run_p4(["-ztag"] + args, cwd=cwd)
    return _parse_ztag(raw)


def _parse_ztag(raw: str) -> list[dict[str, Any]]:
    """Parse p4 -ztag output into a list of dicts."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line.startswith("... "):
            if current:
                records.append(current)
                current = {}
            continue
        parts = line[4:].split(" ", 1)
        key = parts[0]
        value = parts[1] if len(parts) > 1 else ""
        # Handle repeated keys (e.g. depotFile0, depotFile1 → list under 'depotFile')
        # p4 -ztag uses indexed keys like depotFile0, depotFile1
        m = _INDEXED_KEY_RE.match(key)
        if m:
            base, idx = m.group(1), int(m.group(2))
            if base not in current:
                current[base] = []
            lst = current[base]
            if not isinstance(lst, list):
                lst = [lst]
                current[base] = lst
            while len(lst) <= idx:
                lst.append(None)
            lst[idx] = value
        else:
            current[key] = value
    if current:
        records.append(current)
    return records
