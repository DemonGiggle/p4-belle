"""Tests for CLI commands — mock p4 output, verify p5 behaviour."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from p5.p4 import P4Error

# We need to patch both run_p4 and run_p4_tagged at the p5.p4 module level,
# AND where they're imported in each command module.

# ── Helpers ──────────────────────────────────────────────────────────────────

FAKE_ROOT = "/home/testuser/workspace/myproject"
FAKE_PREFIX = "//depot/myproject"
FAKE_CLIENT = "testuser-myproject"

FAKE_P4_INFO_TAGGED = [
    {
        "userName": "testuser",
        "clientName": FAKE_CLIENT,
        "clientRoot": FAKE_ROOT,
    }
]

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


def _make_p4_dispatcher(tagged_results=None, raw_results=None):
    """Build fake run_p4 / run_p4_tagged that return canned data.

    tagged_results: dict mapping command prefix → list[dict]
    raw_results:    dict mapping command prefix → str
    """
    tagged_results = tagged_results or {}
    raw_results = raw_results or {}

    def _fake_run_p4(args, *, cwd=None, check=True):
        joined = " ".join(args)
        # Workspace init calls
        if "info" in joined and "-ztag" not in joined:
            return FAKE_P4_INFO_RAW
        if "client -o" in joined:
            return FAKE_P4_CLIENT_RAW
        for prefix, value in raw_results.items():
            if prefix in joined:
                if isinstance(value, Exception):
                    raise value
                return value
        return ""

    def _fake_run_p4_tagged(args, *, cwd=None):
        joined = " ".join(args)
        for prefix, value in tagged_results.items():
            if prefix in joined:
                if isinstance(value, Exception):
                    raise value
                return value
        return []

    return _fake_run_p4, _fake_run_p4_tagged


# ── p5 status ────────────────────────────────────────────────────────────────

class TestStatusCmd:
    def _invoke(self, args=None, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.status.run_p4_tagged", fake_tagged),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.status import status_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(status_cmd, args or [])
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_clean_working_tree(self):
        result = self._invoke(
            tagged_results={
                "opened": P4Error("file(s) not opened on this client"),
                "reconcile": P4Error("no file(s) to reconcile"),
            }
        )
        assert result.exit_code == 0
        assert "nothing to commit" in result.output

    def test_opened_files_shown(self):
        result = self._invoke(
            tagged_results={
                "opened": [
                    {"depotFile": "//depot/myproject/src/main.cpp", "action": "edit", "change": "default"},
                    {"depotFile": "//depot/myproject/src/util.cpp", "action": "add", "change": "default"},
                ],
                "reconcile": [],
            }
        )
        assert result.exit_code == 0
        assert "main.cpp" in result.output
        assert "util.cpp" in result.output
        assert "M" in result.output  # edit → M
        assert "A" in result.output  # add → A

    def test_numbered_changelist(self):
        result = self._invoke(
            tagged_results={
                "opened": [
                    {"depotFile": "//depot/myproject/src/a.cpp", "action": "edit", "change": "12345"},
                ],
                "reconcile": [],
            }
        )
        assert result.exit_code == 0
        assert "12345" in result.output

    def test_reconcile_untracked(self):
        result = self._invoke(
            tagged_results={
                "opened": P4Error("file(s) not opened on this client"),
                "reconcile": [
                    {"depotFile": "//depot/myproject/src/new.cpp", "action": "add"},
                ],
            }
        )
        assert result.exit_code == 0
        assert "new.cpp" in result.output
        assert "Local changes not opened" in result.output


# ── p5 diff ──────────────────────────────────────────────────────────────────

class TestDiffCmd:
    def _invoke(self, args=None, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.diff.run_p4", fake_run),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.diff import diff_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(diff_cmd, args or [])
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_no_differences(self):
        result = self._invoke(
            raw_results={"diff": P4Error("file(s) not opened for edit")}
        )
        assert result.exit_code == 0
        assert "no differences" in result.output

    def test_diff_output_rendered(self):
        diff_text = """\
==== //depot/myproject/src/main.cpp#5 (text) ====
--- a/src/main.cpp
+++ b/src/main.cpp
@@ -10,3 +10,4 @@ void main() {
     existing line
+    new line added
-    old line removed
"""
        result = self._invoke(raw_results={"diff": diff_text})
        assert result.exit_code == 0
        assert "main.cpp" in result.output
        assert "new line added" in result.output
        assert "old line removed" in result.output

    def test_empty_diff(self):
        result = self._invoke(raw_results={"diff": ""})
        assert result.exit_code == 0
        assert "no differences" in result.output


# ── p5 sync ──────────────────────────────────────────────────────────────────

class TestSyncCmd:
    def _invoke(self, args=None, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.sync.run_p4", fake_run),
            patch("p5.commands.sync.run_p4_tagged", fake_tagged),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.sync import sync_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(sync_cmd, args or [])
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_already_up_to_date(self):
        result = self._invoke(
            raw_results={
                "sync": "//depot/myproject/... - file(s) up-to-date.\n",
            },
            tagged_results={"changes": []},
        )
        assert result.exit_code == 0
        assert "up-to-date" in result.output

    def test_sync_with_updates(self):
        sync_output = (
            "//depot/myproject/src/a.cpp#3 - updating /home/testuser/workspace/myproject/src/a.cpp\n"
            "//depot/myproject/src/b.cpp#1 - added as /home/testuser/workspace/myproject/src/b.cpp\n"
            "//depot/myproject/src/c.cpp#2 - deleted as /home/testuser/workspace/myproject/src/c.cpp\n"
        )
        result = self._invoke(
            raw_results={"sync": sync_output},
            tagged_results={"changes": []},
        )
        assert result.exit_code == 0
        assert "updated" in result.output
        assert "added" in result.output
        assert "deleted" in result.output
        # File names should be relative
        assert "a.cpp" in result.output
        assert "b.cpp" in result.output


# ── p5 filelog ───────────────────────────────────────────────────────────────

class TestFilelogCmd:
    def _invoke(self, args, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.filelog.run_p4_tagged", fake_tagged),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.filelog import filelog_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(filelog_cmd, args)
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_no_history(self):
        result = self._invoke(
            ["main.cpp"],
            tagged_results={"filelog": []},
        )
        assert result.exit_code == 0
        assert "no history" in result.output

    def test_filelog_output(self):
        result = self._invoke(
            ["main.cpp"],
            tagged_results={
                "filelog": [
                    {
                        "depotFile": "//depot/myproject/src/main.cpp",
                        "rev": ["3", "2", "1"],
                        "change": ["300", "200", "100"],
                        "time": ["1700000000", "1699000000", "1698000000"],
                        "user": ["alice", "bob", "alice"],
                        "desc": ["Fix bug", "Add feature", "Initial"],
                        "action": ["edit", "edit", "add"],
                    }
                ],
            },
        )
        assert result.exit_code == 0
        assert "main.cpp" in result.output
        assert "300" in result.output  # CL number
        assert "alice" in result.output
        assert "Fix bug" in result.output


# ── p5 delete ────────────────────────────────────────────────────────────────

class TestDeleteCmd:
    def _invoke(self, args, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.delete.run_p4", fake_run),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.delete import delete_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(delete_cmd, args)
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_delete_with_yes_flag(self):
        result = self._invoke(
            ["-y", f"{FAKE_ROOT}/src/old.cpp"],
            raw_results={
                "delete": "//depot/myproject/src/old.cpp#4 - opened for delete\n"
            },
        )
        assert result.exit_code == 0
        assert "deleted" in result.output
        assert "old.cpp" in result.output

    def test_delete_p4_error(self):
        result = self._invoke(
            ["-y", f"{FAKE_ROOT}/src/missing.cpp"],
            raw_results={
                "delete": P4Error("file(s) not on client")
            },
        )
        assert result.exit_code == 0  # error is caught and printed
        assert "error" in result.output


# ── p5 submit (direct mode) ─────────────────────────────────────────────────

class TestSubmitCmd:
    def _invoke(self, args, **dispatcher_kwargs):
        fake_run, fake_tagged = _make_p4_dispatcher(**dispatcher_kwargs)
        patches = [
            patch("p5.p4.run_p4", fake_run),
            patch("p5.commands.submit.run_p4", fake_run),
            patch("p5.commands.submit.run_p4_tagged", fake_tagged),
            patch("p5.workspace.run_p4", fake_run),
            patch("os.getcwd", return_value=f"{FAKE_ROOT}/src"),
        ]
        for p in patches:
            p.start()
        try:
            from p5.commands.submit import submit_cmd
            import p5.workspace as ws
            ws._workspace = None
            runner = CliRunner()
            return runner.invoke(submit_cmd, args)
        finally:
            for p in patches:
                p.stop()
            import p5.workspace as ws
            ws._workspace = None

    def test_nothing_to_submit(self):
        result = self._invoke(
            ["-c", "99999", "-y"],
            tagged_results={"opened": []},
        )
        assert result.exit_code == 0
        assert "nothing to submit" in result.output

    def test_submit_with_description(self):
        result = self._invoke(
            ["-c", "12345", "-d", "Fix the bug", "-y"],
            tagged_results={
                "opened": [
                    {"depotFile": "//depot/myproject/src/a.cpp", "action": "edit"},
                ],
            },
            raw_results={
                "submit": "Change 12345 submitted.\n",
            },
        )
        assert result.exit_code == 0
        assert "submitted" in result.output
        assert "12345" in result.output
