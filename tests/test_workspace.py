"""Tests for p5.workspace — path resolution without a real p4 server."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from p5.p4 import P4Error

# These tests construct a Workspace directly with controlled _info / depot_prefix.

FAKE_ROOT = "/home/testuser/workspace/myproject"
FAKE_PREFIX = "//depot/myproject"
FAKE_CLIENT = "testuser-myproject"

FAKE_P4_INFO = f"""\
User name: testuser
Client name: {FAKE_CLIENT}
Client host: devbox
Client root: {FAKE_ROOT}
"""

FAKE_P4_CLIENT_OUTPUT = f"""\
Client: {FAKE_CLIENT}
Root: {FAKE_ROOT}
View:
\t{FAKE_PREFIX}/... //{FAKE_CLIENT}/...
"""


@pytest.fixture(autouse=True)
def _reset_workspace():
    """Reset the module-level singleton before each test."""
    import p5.workspace as ws
    ws._workspace = None
    yield
    ws._workspace = None


@pytest.fixture()
def workspace():
    """Return a Workspace object backed by fake p4 output."""
    from p5.workspace import Workspace

    with patch("p5.p4.run_p4") as mock_run:
        def _side_effect(args, *, cwd=None, check=True):
            joined = " ".join(args)
            if "info" in joined:
                return FAKE_P4_INFO
            if "client -o" in joined:
                return FAKE_P4_CLIENT_OUTPUT
            return ""
        mock_run.side_effect = _side_effect

        ws = Workspace()
        # Force cache population
        _ = ws.client_root
        _ = ws.depot_prefix
    return ws


class TestWorkspaceProperties:
    def test_client_root(self, workspace):
        assert str(workspace.client_root) == FAKE_ROOT

    def test_client_name(self, workspace):
        assert workspace.client_name == FAKE_CLIENT

    def test_depot_prefix(self, workspace):
        assert workspace.depot_prefix == FAKE_PREFIX


class TestDepotToRel:
    def test_depot_path_under_prefix(self, workspace):
        assert workspace.depot_to_rel("//depot/myproject/src/main.cpp") == "src/main.cpp"

    def test_depot_path_not_under_prefix(self, workspace):
        # Falls through — returns the depot path unchanged
        assert workspace.depot_to_rel("//other/repo/foo.cpp") == "//other/repo/foo.cpp"

    def test_non_depot_path_passthrough(self, workspace):
        assert workspace.depot_to_rel("just/a/path") == "just/a/path"


class TestLocalToDepot:
    def test_absolute_under_root(self, workspace):
        result = workspace.local_to_depot(f"{FAKE_ROOT}/src/main.cpp")
        assert result == f"{FAKE_PREFIX}/src/main.cpp"

    def test_depot_path_passthrough(self, workspace):
        assert workspace.local_to_depot("//depot/myproject/a.cpp") == "//depot/myproject/a.cpp"

    def test_outside_root(self, workspace):
        # Path not under client root — returned as-is
        result = workspace.local_to_depot("/tmp/random/file.cpp")
        assert result == "/tmp/random/file.cpp"


class TestLocalToRel:
    def test_abs_path(self, workspace):
        assert workspace.local_to_rel(f"{FAKE_ROOT}/src/foo.cpp") == "src/foo.cpp"

    def test_outside_root_returns_as_is(self, workspace):
        result = workspace.local_to_rel("/tmp/elsewhere/bar.cpp")
        assert result == "/tmp/elsewhere/bar.cpp"


class TestAnyToRel:
    def test_depot_path(self, workspace):
        assert workspace.any_to_rel("//depot/myproject/src/foo.cpp") == "src/foo.cpp"

    def test_absolute_local_path(self, workspace):
        assert workspace.any_to_rel(f"{FAKE_ROOT}/src/foo.cpp") == "src/foo.cpp"


class TestCheckCwdInWorkspace:
    def test_inside_workspace(self, workspace):
        from p5.workspace import check_cwd_in_workspace

        with patch("p5.workspace.get_workspace", return_value=workspace):
            # Should not raise
            check_cwd_in_workspace(cwd=f"{FAKE_ROOT}/src")

    def test_outside_workspace(self, workspace):
        from p5.workspace import check_cwd_in_workspace

        with patch("p5.workspace.get_workspace", return_value=workspace):
            with pytest.raises(P4Error, match="not inside workspace"):
                check_cwd_in_workspace(cwd="/tmp/elsewhere")
