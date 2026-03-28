"""Tests for p5.p4 — the low-level p4 subprocess wrapper."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from p5.p4 import P4Error, _parse_ztag, run_p4, run_p4_tagged


# ── _parse_ztag ──────────────────────────────────────────────────────────────

class TestParseZtag:
    def test_empty_input(self):
        assert _parse_ztag("") == []

    def test_single_record(self):
        raw = """\
... depotFile //depot/myproject/src/main.cpp
... action edit
... change default
"""
        result = _parse_ztag(raw)
        assert len(result) == 1
        assert result[0]["depotFile"] == "//depot/myproject/src/main.cpp"
        assert result[0]["action"] == "edit"
        assert result[0]["change"] == "default"

    def test_multiple_records(self):
        raw = """\
... depotFile //depot/myproject/src/a.cpp
... action edit

... depotFile //depot/myproject/src/b.cpp
... action add
"""
        result = _parse_ztag(raw)
        assert len(result) == 2
        assert result[0]["depotFile"] == "//depot/myproject/src/a.cpp"
        assert result[1]["action"] == "add"

    def test_indexed_keys_become_lists(self):
        """p4 filelog returns keys like rev0, rev1, change0, change1."""
        raw = """\
... depotFile //depot/myproject/src/main.cpp
... rev0 5
... rev1 4
... rev2 3
... change0 100
... change1 99
... change2 98
... action0 edit
... action1 add
... action2 branch
"""
        result = _parse_ztag(raw)
        assert len(result) == 1
        rec = result[0]
        assert rec["rev"] == ["5", "4", "3"]
        assert rec["change"] == ["100", "99", "98"]
        assert rec["action"] == ["edit", "add", "branch"]

    def test_value_with_spaces(self):
        raw = "... desc This is a long description with spaces\n"
        result = _parse_ztag(raw)
        assert result[0]["desc"] == "This is a long description with spaces"

    def test_empty_value(self):
        raw = "... desc \n"
        result = _parse_ztag(raw)
        assert result[0]["desc"] == ""

    def test_key_without_value(self):
        """Some p4 fields have no value after the key."""
        raw = "... isMapped\n"
        result = _parse_ztag(raw)
        assert result[0]["isMapped"] == ""

    def test_non_ztag_lines_separate_records(self):
        raw = """\
... depotFile //depot/a
other line here
... depotFile //depot/b
"""
        result = _parse_ztag(raw)
        assert len(result) == 2


# ── run_p4 ───────────────────────────────────────────────────────────────────

class TestRunP4:
    def test_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["p4", "info"], returncode=0,
                stdout="User name: testuser\n", stderr="",
            )
            result = run_p4(["info"])
            assert "testuser" in result
            mock_run.assert_called_once()

    def test_nonzero_exit_raises_p4error(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["p4", "bad"], returncode=1,
                stdout="", stderr="Unknown command.\n",
            )
            with pytest.raises(P4Error, match="Unknown command"):
                run_p4(["bad"])

    def test_check_false_no_raise(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["p4", "bad"], returncode=1,
                stdout="error output", stderr="",
            )
            result = run_p4(["bad"], check=False)
            assert result == "error output"

    def test_p4_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(P4Error, match="not found"):
                run_p4(["info"])

    def test_run_p4_tagged(self):
        with patch("p5.p4.run_p4") as mock:
            mock.return_value = "... user testuser\n... clientName ws\n"
            result = run_p4_tagged(["info"])
            assert result == [{"user": "testuser", "clientName": "ws"}]
            # Verify -ztag was prepended
            mock.assert_called_once_with(["-ztag", "info"], cwd=None)
