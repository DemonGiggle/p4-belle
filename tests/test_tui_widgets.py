"""Tests for shared responsive TUI widgets."""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListItem, Static

from p5.tui.widgets import FastListView


class _FastListHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield FastListView(
            ListItem(Static("one")),
            ListItem(Static("two")),
            id="list-view",
        )


@pytest.mark.asyncio
async def test_fast_list_view_scrolls_immediately_on_index_change(monkeypatch):
    """Highlighted rows should be scrolled into view without deferred lag."""
    app = _FastListHarness()

    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        lv = app.query_one(FastListView)
        calls: list[tuple[object, dict[str, object]]] = []

        def fake_scroll_to_widget(widget, **kwargs):
            calls.append((widget, kwargs))
            return False

        monkeypatch.setattr(lv, "scroll_to_widget", fake_scroll_to_widget)
        lv.index = 1

        assert calls
        assert calls[-1][1]["animate"] is False
        assert calls[-1][1]["immediate"] is True


@pytest.mark.asyncio
async def test_fast_list_view_ignores_invalid_index():
    """Invalid indices should be ignored without touching the backing node list."""
    app = _FastListHarness()

    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        lv = app.query_one(FastListView)
        original_index = lv.index
        lv.watch_index(None, 99)
        assert lv.index == original_index


@pytest.mark.asyncio
async def test_all_p5_tuis_use_fast_list_view():
    """Every interactive p5 list should use the shared responsive list widget."""
    from p5.tui.change_app import ChangeApp, FileRecord as ChangeFileRecord
    from p5.tui.changes_app import ChangeRecord, ChangesApp
    from p5.tui.submit_app import FileRecord as SubmitFileRecord
    from p5.tui.submit_app import PendingCL, SubmitApp
    from p5.tui.ws_app import ClientRecord, WorkspaceApp

    workspace_app = WorkspaceApp(
        demo_records=[
            ClientRecord(
                name="ws-main",
                root="/tmp/ws-main",
                host="host1",
                description="Main workspace",
                access="2026-04-28",
                update="2026-04-28",
                is_current=True,
            )
        ]
    )
    changes_app = ChangesApp(
        demo_records=[
            ChangeRecord(
                cl="123456",
                date="2026-04-28",
                user="alice",
                description="Fix scrolling responsiveness",
            )
        ]
    )
    change_app = ChangeApp(
        files=[
            ChangeFileRecord(
                "//depot/myproject/src/alpha.cpp",
                "edit",
                rel_path="src/alpha.cpp",
                local_path="/tmp/src/alpha.cpp",
            )
        ],
        demo_mode=True,
    )
    submit_app = SubmitApp(
        pending_cls=[
            PendingCL(
                "123456",
                "Test changelist",
                [
                    SubmitFileRecord(
                        "//depot/myproject/src/alpha.cpp",
                        "edit",
                        "src/alpha.cpp",
                        local_path="/tmp/src/alpha.cpp",
                    )
                ],
            )
        ]
    )

    async with workspace_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(workspace_app.query_one("#list-view"), FastListView)

    async with changes_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(changes_app.query_one("#list-view"), FastListView)

    async with change_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(change_app.query_one("#file-list"), FastListView)

    async with submit_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(submit_app.query_one("#main-list"), FastListView)
