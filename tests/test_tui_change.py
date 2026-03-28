"""TUI tests for ChangeApp using Textual's Pilot.

These tests exercise:
- File list rendering with mocked p4 data
- Selection (space, a, d)
- Filter mode (/, typing, Escape, Enter) and focus correctness
- Key passthrough prevention while filtering
- Cursor navigation (j/k) skipping section headers
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

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

FAKE_OPENED_DEFAULT = [
    {"depotFile": f"{FAKE_PREFIX}/src/alpha.cpp", "action": "edit", "change": "default"},
    {"depotFile": f"{FAKE_PREFIX}/src/beta.cpp", "action": "add", "change": "default"},
    {"depotFile": f"{FAKE_PREFIX}/src/gamma.py", "action": "delete", "change": "default"},
]


def _make_patches():
    """Return context managers that mock p4 calls for the TUI."""

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
            return list(FAKE_OPENED_DEFAULT)
        if "changes" in joined:
            return [
                {"change": "100", "desc": "existing CL"},
            ]
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


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_loads_files():
    """ChangeApp should display file items from mocked p4 opened output."""
    from p5.tui.change_app import ChangeApp, FileItem

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            # There should be FileItem widgets for each opened file
            file_items = app.query(FileItem)
            assert len(file_items) == 3
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_toggle_selection():
    """Pressing space should toggle file selection."""
    from p5.tui.change_app import ChangeApp, FileItem

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert len(app._selected) == 0

            # Press space to select the current file
            await pilot.press("space")
            await pilot.pause()
            assert len(app._selected) == 1
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_select_all_deselect_all():
    """'a' selects all files, 'd' deselects all."""
    from p5.tui.change_app import ChangeApp

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("a")
            await pilot.pause()
            assert len(app._selected) == 3

            await pilot.press("d")
            await pilot.pause()
            assert len(app._selected) == 0
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_mode_focus():
    """Pressing '/' should focus the filter input; Escape returns focus to the list."""
    from p5.tui.change_app import ChangeApp
    from textual.widgets import Input, ListView

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            # Enter filter mode
            await pilot.press("slash")
            await pilot.pause()

            # The Input widget should have focus
            focused = app.focused
            assert isinstance(focused, Input), f"Expected Input focused, got {type(focused)}"
            assert app._filtering is True

            # Escape should exit filter mode and return focus to ListView
            await pilot.press("escape")
            await pilot.pause()

            assert app._filtering is False
            focused = app.focused
            assert isinstance(focused, ListView), f"Expected ListView focused, got {type(focused)}"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_narrows_list():
    """Typing in filter mode should narrow the displayed files."""
    from p5.tui.change_app import ChangeApp, FileItem

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert len(app.query(FileItem)) == 3

            # Enter filter and type "alpha"
            await pilot.press("slash")
            await pilot.pause()
            # Type into the input
            for ch in "alpha":
                await pilot.press(ch)
            await pilot.pause()

            # Should show only alpha.cpp
            assert len(app.query(FileItem)) == 1
            assert app._filter_text == "alpha"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_escape_clears():
    """Pressing Escape during filter should clear the filter and show all files again."""
    from p5.tui.change_app import ChangeApp, FileItem

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            # Filter down
            await pilot.press("slash")
            for ch in "gamma":
                await pilot.press(ch)
            await pilot.pause()
            assert len(app.query(FileItem)) == 1

            # Escape clears filter
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.query(FileItem)) == 3
            assert app._filter_text == ""
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_keys_blocked_during_filter():
    """While filtering, action keys like 'a', 'd', space should NOT trigger actions."""
    from p5.tui.change_app import ChangeApp

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            # Enter filter mode
            await pilot.press("slash")
            await pilot.pause()

            # Press 'a' — should type into filter, NOT select-all
            await pilot.press("a")
            await pilot.pause()
            assert len(app._selected) == 0, "select_all should NOT fire during filter"

            # Press space — should type into filter, NOT toggle
            await pilot.press("space")
            await pilot.pause()
            assert len(app._selected) == 0, "toggle should NOT fire during filter"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_submit_returns_focus():
    """Pressing Enter in filter mode should commit the filter and return focus to ListView."""
    from p5.tui.change_app import ChangeApp
    from textual.widgets import ListView

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for ch in "beta":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()

            assert app._filtering is False
            assert app._filter_text == "beta"
            focused = app.focused
            assert isinstance(focused, ListView), f"Expected ListView, got {type(focused)}"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_cursor_skips_section_headers():
    """j/k navigation should skip disabled section header items."""
    from p5.tui.change_app import ChangeApp
    from textual.widgets import ListView

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            lv = app.query_one("#file-list", ListView)
            # Cursor should start on a file item (not a section header)
            idx = lv.index
            assert idx is not None
            assert app._list_data[idx] is not None, "Cursor should not be on a section header"

            # Navigate down through all items — cursor should never land on None (header)
            for _ in range(5):
                await pilot.press("j")
                await pilot.pause()
                idx = lv.index
                if idx is not None and idx < len(app._list_data):
                    assert app._list_data[idx] is not None, \
                        f"Cursor landed on section header at index {idx}"
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_quit():
    """Pressing 'q' should exit the app."""
    from p5.tui.change_app import ChangeApp

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            # App should have exited (run_test context completes)
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_empty_default_changelist():
    """App should handle empty default changelist gracefully."""
    from p5.tui.change_app import ChangeApp, FileItem

    def fake_run_p4(args, *, cwd=None, check=True):
        joined = " ".join(args)
        if "info" in joined:
            return FAKE_P4_INFO_RAW
        if "client -o" in joined:
            return FAKE_P4_CLIENT_RAW
        return ""

    def fake_tagged(args, *, cwd=None):
        joined = " ".join(args)
        if "opened" in joined:
            return []
        return []

    patches = [
        patch("p5.p4.run_p4", fake_run_p4),
        patch("p5.tui.change_app.run_p4", fake_run_p4),
        patch("p5.tui.change_app.run_p4_tagged", fake_tagged),
        patch("p5.workspace.run_p4", fake_run_p4),
    ]
    for p in patches:
        p.start()
    try:
        import p5.workspace as ws
        ws._workspace = None
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert len(app.query(FileItem)) == 0
            assert len(app._files) == 0
    finally:
        for p in patches:
            p.stop()
