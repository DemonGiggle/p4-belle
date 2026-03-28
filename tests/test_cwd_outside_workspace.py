"""Tests that commands report errors when cwd is outside the workspace."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

FAKE_ROOT = "/home/testuser/workspace/myproject"
FAKE_CLIENT = "testuser-myproject"
FAKE_PREFIX = "//depot/myproject"

FAKE_P4_INFO_RAW = f"""\
User name: testuser
Client name: {FAKE_CLIENT}
Client host: devbox
Client root: {FAKE_ROOT}
"""

FAKE_P4_CLIENT_RAW = f"""\
Client: {FAKE_CLIENT}
Root: {FAKE_ROOT}
View:
\t{FAKE_PREFIX}/... //{FAKE_CLIENT}/...
"""


def _fake_run_p4(args, *, cwd=None, check=True):
    joined = " ".join(args)
    if "info" in joined:
        return FAKE_P4_INFO_RAW
    if "client -o" in joined:
        return FAKE_P4_CLIENT_RAW
    return ""


@pytest.fixture(autouse=True)
def _reset_and_patch():
    """Set cwd to somewhere OUTSIDE the workspace, patch p4 calls."""
    import p5.workspace as ws
    ws._workspace = None
    with patch("p5.p4.run_p4", _fake_run_p4), \
         patch("p5.workspace.run_p4", _fake_run_p4), \
         patch("os.getcwd", return_value="/tmp/somewhere_else"):
        yield
    ws._workspace = None


class TestCwdOutsideWorkspace:
    """Commands that use local paths should error when cwd is outside the workspace."""

    def test_status_outside_workspace(self):
        from p5.commands.status import status_cmd
        runner = CliRunner()
        result = runner.invoke(status_cmd, [])
        assert result.exit_code != 0 or "not inside workspace" in result.output

    def test_diff_outside_workspace(self):
        from p5.commands.diff import diff_cmd
        runner = CliRunner()
        result = runner.invoke(diff_cmd, [])
        assert result.exit_code != 0 or "not inside workspace" in result.output

    def test_sync_outside_workspace(self):
        from p5.commands.sync import sync_cmd
        runner = CliRunner()
        result = runner.invoke(sync_cmd, [])
        assert result.exit_code != 0 or "not inside workspace" in result.output

    def test_filelog_outside_workspace(self):
        from p5.commands.filelog import filelog_cmd
        runner = CliRunner()
        result = runner.invoke(filelog_cmd, ["somefile.cpp"])
        assert result.exit_code != 0 or "not inside workspace" in result.output

    def test_delete_outside_workspace(self):
        from p5.commands.delete import delete_cmd
        runner = CliRunner()
        result = runner.invoke(delete_cmd, ["-y", "somefile.cpp"])
        assert result.exit_code != 0 or "not inside workspace" in result.output

    def test_status_all_flag_bypasses_check(self):
        """p5 status -a should work even outside the workspace."""
        from p5.commands.status import status_cmd

        with patch("p5.commands.status.run_p4_tagged") as mock_tagged:
            mock_tagged.return_value = []
            runner = CliRunner()
            result = runner.invoke(status_cmd, ["--all"])
            # Should NOT error about workspace
            assert "not inside workspace" not in (result.output or "")

    def test_sync_all_flag_bypasses_check(self):
        """p5 sync -a should work even outside the workspace."""
        from p5.commands.sync import sync_cmd

        with patch("p5.commands.sync.run_p4", return_value="up-to-date\n"), \
             patch("p5.commands.sync.run_p4_tagged", return_value=[]):
            runner = CliRunner()
            result = runner.invoke(sync_cmd, ["--all"])
            assert "not inside workspace" not in (result.output or "")
