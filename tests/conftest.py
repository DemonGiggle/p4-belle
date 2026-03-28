"""Shared fixtures for p5 tests — mock p4 subprocess calls."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# ── Fake workspace info returned by `p4 info` and `p4 client -o` ────────────

FAKE_CLIENT_ROOT = "/home/testuser/workspace/myproject"
FAKE_CLIENT_NAME = "testuser-myproject"
FAKE_DEPOT_PREFIX = "//depot/myproject"

FAKE_P4_INFO = f"""\
User name: testuser
Client name: {FAKE_CLIENT_NAME}
Client host: devbox
Client root: {FAKE_CLIENT_ROOT}
Current directory: {FAKE_CLIENT_ROOT}/src
"""

FAKE_P4_CLIENT = f"""\
Client: {FAKE_CLIENT_NAME}
Root: {FAKE_CLIENT_ROOT}
View:
\t{FAKE_DEPOT_PREFIX}/... //{FAKE_CLIENT_NAME}/...
"""


@pytest.fixture()
def fake_workspace(monkeypatch):
    """Patch run_p4 so Workspace can initialize without a real p4 server.

    Returns a helper with the fake constants for assertions.
    """
    import p5.workspace as ws_mod

    # Reset the cached singleton so each test gets a fresh Workspace
    ws_mod._workspace = None

    def _fake_run_p4(args, *, cwd=None, check=True):
        cmd = " ".join(args)
        if cmd == "info" or cmd == "-ztag info":
            return FAKE_P4_INFO
        if cmd.startswith("client -o"):
            return FAKE_P4_CLIENT
        return ""

    monkeypatch.setattr("p5.p4.run_p4", _fake_run_p4)

    # Also patch cwd to be inside the fake workspace
    monkeypatch.setattr("os.getcwd", lambda: f"{FAKE_CLIENT_ROOT}/src")
    monkeypatch.setattr(
        Path, "resolve",
        lambda self: Path(str(self)) if str(self).startswith("/") else Path(f"{FAKE_CLIENT_ROOT}/src/{self}"),
    )

    class Info:
        root = FAKE_CLIENT_ROOT
        name = FAKE_CLIENT_NAME
        prefix = FAKE_DEPOT_PREFIX

    yield Info()

    # Clean up singleton
    ws_mod._workspace = None
