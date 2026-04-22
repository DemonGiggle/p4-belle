"""Tests that expose actual bugs in the TUI apps.

These tests FAIL against the current code — they demonstrate real bugs.
Mark them with xfail so the test suite passes but the bugs are documented.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from p5.p4 import P4Error

FAKE_ROOT = "/home/testuser/workspace/myproject"
FAKE_PREFIX = "//depot/myproject"
FAKE_CLIENT = "testuser-myproject"

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


def _make_change_app_patches(opened_files):
    def fake_run_p4(args, *, cwd=None, check=True):
        joined = " ".join(args)
        if "info" in joined:
            return FAKE_P4_INFO_RAW
        if "client -o" in joined:
            return FAKE_P4_CLIENT_RAW
        return ""

    def fake_run_p4_tagged(args, *, cwd=None):
        joined = " ".join(args)
        if "opened" in joined:
            return list(opened_files)
        if "info" in joined:
            return [{"userName": "testuser"}]
        return []

    return [
        patch("p5.p4.run_p4", fake_run_p4),
        patch("p5.tui.change_app.run_p4", fake_run_p4),
        patch("p5.tui.change_app.run_p4_tagged", fake_run_p4_tagged),
        patch("p5.workspace.run_p4", fake_run_p4),
    ]


@pytest.fixture(autouse=True)
def _reset_workspace():
    import p5.workspace as ws
    ws._workspace = None
    yield
    ws._workspace = None


# ─────────────────────────────────────────────────────────────────────────────
# BUG 1: _filter_just_committed flag gets stuck in ChangeApp
#
# When the user commits a filter (Enter) that matches zero files,
# ListView.Selected never fires, so _filter_just_committed stays True.
# The next legitimate Enter on a list item is silently swallowed.
#
# Same bug pattern exists in ChangesApp and SubmitApp.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_just_committed_flag_gets_stuck():
    """After committing a zero-result filter, the next Enter on a list item
    should still work (toggle selection). Currently it's silently swallowed."""
    from p5.tui.change_app import ChangeApp, FileItem

    opened = [
        {"depotFile": f"{FAKE_PREFIX}/src/alpha.cpp", "action": "edit", "change": "default"},
        {"depotFile": f"{FAKE_PREFIX}/src/beta.cpp", "action": "add", "change": "default"},
    ]
    patches = _make_change_app_patches(opened)
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert len(app._selected) == 0

            # Filter to something that matches nothing
            await pilot.press("slash")
            for ch in "zzzzz_no_match":
                await pilot.press(ch)
            await pilot.pause()
            assert len(app.query(FileItem)) == 0

            # Commit the filter — flag is set but never consumed
            await pilot.press("enter")
            await pilot.pause()
            assert app._filter_just_committed is True, \
                "Flag should be stuck — no ListView.Selected to consume it"

            # Clear filter — files come back
            await pilot.press("slash")
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.query(FileItem)) == 2

            # Enter should toggle, but the stale flag swallows it
            await pilot.press("enter")
            await pilot.pause()
            assert len(app._selected) == 1, \
                "Enter should toggle the item, but stale _filter_just_committed blocks it"
    finally:
        for p in patches:
            p.stop()


# ─────────────────────────────────────────────────────────────────────────────
# BUG 2: SubmitApp on_key blocks ALL keys during filter (inconsistent)
#
# SubmitApp.on_key has `else: event.stop()` which blocks every key not
# explicitly handled (Enter, Escape, Backspace, printable chars).
# This means Ctrl+C, resize events, etc. are all stopped during filter.
#
# ChangesApp correctly uses `else: return` to let unhandled keys through.
# ─────────────────────────────────────────────────────────────────────────────

def test_submit_app_filter_does_not_block_system_keys():
    """SubmitApp.on_key should let unhandled keys pass through during filter,
    like ChangesApp does. Currently it stops everything."""
    import inspect
    from p5.tui.submit_app import SubmitApp

    source = inspect.getsource(SubmitApp.on_key)

    # The final else branch should use `return` (let keys through),
    # not `event.stop()` (block everything)
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "else:":
            # Check the line(s) after `else:`
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "event.stop()", \
                "SubmitApp.on_key should use `return` in the else branch, not `event.stop()`"


def test_change_dummy_data_imports_on_python39():
    """Dummy-data change TUI should import cleanly on Python 3.9."""
    from p5.commands.change import change_cmd

    runner = CliRunner()
    with patch("p5.tui.change_app.ChangeApp.run", autospec=True, return_value=None):
        result = runner.invoke(change_cmd, ["--dummy-data"])

    assert result.exit_code == 0


def test_submit_dummy_data_imports_on_python39():
    """Dummy-data submit TUI should import cleanly on Python 3.9."""
    from p5.commands.submit import submit_cmd

    runner = CliRunner()
    with patch("p5.tui.submit_app.SubmitApp.run", autospec=True, return_value=None):
        result = runner.invoke(submit_cmd, ["--dummy-data"])

    assert result.exit_code == 0
