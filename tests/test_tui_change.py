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
    """Pressing Enter should toggle file selection."""
    from p5.tui.change_app import ChangeApp

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert len(app._selected) == 0

            # Press Enter to select the current file
            await pilot.press("enter")
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
    from textual.widgets import Input, ListView, Static

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
            filter_input = app.query_one("#filter-input", Input)
            filter_bar = app.query_one("#filter-bar", Static)
            assert filter_input.has_class("visible")
            assert filter_bar.has_class("visible")
            assert filter_bar.has_class("active")

            # Escape should exit filter mode and return focus to ListView
            await pilot.press("escape")
            await pilot.pause()

            assert app._filtering is False
            focused = app.focused
            assert isinstance(focused, ListView), f"Expected ListView focused, got {type(focused)}"
            assert not filter_input.has_class("visible")
            assert not filter_bar.has_class("visible")
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_layout_shows_search_field_above_footer():
    """Filter mode should allocate a visible input row above the filter bar/footer."""
    from p5.tui.change_app import ChangeApp
    from textual.widgets import Input, Static

    patches = _make_patches()
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()

            filter_input = app.query_one("#filter-input", Input)
            filter_bar = app.query_one("#filter-bar", Static)
            footer_bar = app.query_one("#footer-bar", Static)

            assert filter_input.display is True
            assert filter_bar.display is True
            assert filter_input.region.height == 1
            assert filter_bar.region.height == 1
            assert filter_input.region.y + filter_input.region.height <= filter_bar.region.y
            assert filter_bar.region.y + filter_bar.region.height <= footer_bar.region.y
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
async def test_filter_updates_on_every_character():
    """Each typed character should immediately update the visible filtered list."""
    from p5.tui.change_app import ChangeApp, FileItem
    from textual.widgets import Input

    opened = [
        {"depotFile": f"{FAKE_PREFIX}/src/alpha.cpp", "action": "edit", "change": "default"},
        {"depotFile": f"{FAKE_PREFIX}/src/alpine.cpp", "action": "edit", "change": "default"},
        {"depotFile": f"{FAKE_PREFIX}/src/beta.cpp", "action": "add", "change": "default"},
    ]

    def fake_run_p4(args, *, cwd=None, check=True):
        joined = " ".join(args)
        if "info" in joined:
            return FAKE_P4_INFO_RAW
        if "client -o" in joined:
            return FAKE_P4_CLIENT_RAW
        return ""

    def fake_tagged(args, *, cwd=None):
        if "opened" in " ".join(args):
            return opened
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
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("slash")
            await pilot.pause()
            assert isinstance(app.focused, Input)

            await pilot.press("a")
            await pilot.pause()
            assert app._filter_text == "a"
            assert len(app.query(FileItem)) == 3
            assert isinstance(app.focused, Input)

            await pilot.press("l")
            await pilot.pause()
            assert app._filter_text == "al"
            assert len(app.query(FileItem)) == 2
            assert isinstance(app.focused, Input)

            await pilot.press("p")
            await pilot.pause()
            assert app._filter_text == "alp"
            assert len(app.query(FileItem)) == 2
            assert isinstance(app.focused, Input)

            await pilot.press("h")
            await pilot.pause()
            assert app._filter_text == "alph"
            assert len(app.query(FileItem)) == 1
            assert isinstance(app.focused, Input)
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

            # Press space — should type into filter, NOT open diff
            await pilot.press("space")
            await pilot.pause()
            assert len(app._selected) == 0, "diff action should NOT fire during filter"
            assert app._detail_open is False, "diff action should NOT fire during filter"
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
            assert app._filter_just_committed is False
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_filter_submit_restores_highlight_to_first_result():
    """Submitting a filter should leave the first visible file highlighted."""
    from p5.tui.change_app import ChangeApp, FileItem
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

            lv = app.query_one("#file-list", ListView)
            highlighted = lv.highlighted_child

            assert isinstance(app.focused, ListView)
            assert len(app.query(FileItem)) == 1
            assert lv.index is not None
            assert isinstance(highlighted, FileItem)
            assert highlighted.highlighted is True

            await pilot.press("enter")
            await pilot.pause()
            assert len(app._selected) == 1
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_space_opens_diff_and_escape_returns_to_list():
    """Space opens the highlighted file diff; Escape returns to the file list."""
    from p5.tui.change_app import ChangeApp, FileDiffView
    from textual.widgets import ListView

    patches = _make_patches()
    patches.append(
        patch(
            "p5.tui.change_app._fetch_file_diff",
            return_value="diff src/alpha.cpp\n--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1,2 @@\n line\n+extra\n",
        )
    )
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("space")
            await pilot.pause()

            assert app._detail_open is True
            assert app.query_one("#file-list", ListView).display is False
            assert app.query_one("#detail-view", FileDiffView).display is True

            await pilot.press("escape")
            await pilot.pause()

            assert app._detail_open is False
            assert app.query_one("#file-list", ListView).display is True
            assert app.query_one("#detail-view", FileDiffView).display is False
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_detail_view_jk_scrolls_diff_panel():
    """When diff is open, j/k should scroll the diff panel instead of moving the list."""
    from p5.tui.change_app import ChangeApp, FileDiffView
    from textual.widgets import ListView

    patches = _make_patches()
    patches.append(
        patch(
            "p5.tui.change_app._fetch_file_diff",
            return_value="\n".join(
                ["diff src/alpha.cpp", "--- a/src/alpha.cpp", "+++ b/src/alpha.cpp", "@@ -1 +1,40 @@"]
                + [f"+line {i}" for i in range(40)]
            ),
        )
    )
    for p in patches:
        p.start()
    try:
        app = ChangeApp()
        async with app.run_test(size=(120, 12)) as pilot:
            await pilot.pause()
            lv = app.query_one("#file-list", ListView)
            start_index = lv.index

            await pilot.press("space")
            await pilot.pause()

            detail = app.query_one("#detail-view", FileDiffView)
            start_y = detail.scroll_y

            await pilot.press("j")
            await pilot.pause()
            assert detail.scroll_y > start_y
            assert lv.index == start_index

            moved_y = detail.scroll_y
            await pilot.press("k")
            await pilot.pause()
            assert detail.scroll_y < moved_y
            assert lv.index == start_index
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
