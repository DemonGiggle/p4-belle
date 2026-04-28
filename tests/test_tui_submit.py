"""TUI tests for SubmitApp diff interactions."""
from __future__ import annotations

from unittest.mock import patch

import pytest


def _build_app():
    from p5.tui.submit_app import FileRecord, PendingCL, SubmitApp

    return SubmitApp(
        pending_cls=[
            PendingCL(
                "123456",
                "Test changelist",
                [
                    FileRecord(
                        "//depot/myproject/src/alpha.cpp",
                        "edit",
                        "src/alpha.cpp",
                        local_path="/tmp/src/alpha.cpp",
                    ),
                ],
            )
        ]
    )


@pytest.mark.asyncio
async def test_space_opens_submit_file_diff_and_escape_returns_to_list():
    """Space opens the highlighted file diff in CL detail; Escape returns to the file list."""
    from p5.tui.change_app import FileDiffView
    from textual.widgets import ListView

    app = _build_app()
    with patch(
        "p5.tui.submit_app._fetch_file_diff",
        return_value="diff src/alpha.cpp\n--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1,2 @@\n line\n+extra\n",
    ):
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("space")
            await pilot.pause()

            assert app._detail_open is True
            assert app.query_one("#main-list", ListView).display is False
            assert app.query_one("#detail-view", FileDiffView).display is True

            await pilot.press("escape")
            await pilot.pause()

            assert app._detail_open is False
            assert app.query_one("#main-list", ListView).display is True
            assert app.query_one("#detail-view", FileDiffView).display is False


@pytest.mark.asyncio
async def test_submit_detail_view_jk_scrolls_diff_panel():
    """When submit diff is open, j/k should scroll the diff panel instead of moving the list."""
    from p5.tui.change_app import FileDiffView
    from textual.widgets import ListView

    app = _build_app()
    with patch(
        "p5.tui.submit_app._fetch_file_diff",
        return_value="\n".join(
            ["diff src/alpha.cpp", "--- a/src/alpha.cpp", "+++ b/src/alpha.cpp", "@@ -1 +1,40 @@"]
            + [f"+line {i}" for i in range(40)]
        ),
    ):
        async with app.run_test(size=(120, 12)) as pilot:
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            lv = app.query_one("#main-list", ListView)
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
