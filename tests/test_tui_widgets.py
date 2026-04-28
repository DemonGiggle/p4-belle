"""Tests for shared responsive TUI widgets."""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListItem, Static

from p5.tui.widgets import FastListView, FastRichLog, FastScrollableContainer


class _FastListHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield FastListView(
            ListItem(Static("one")),
            ListItem(Static("two")),
            id="list-view",
        )


class _FastPagedListHarness(App[None]):
    def compose(self) -> ComposeResult:
        header = ListItem(Static("header"))
        header.disabled = True
        yield FastListView(
            header,
            *[ListItem(Static(f"item {i}")) for i in range(20)],
            id="list-view",
        )


class _FastScrollableHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield FastScrollableContainer(
            *[Static(f"line {i}") for i in range(20)],
            id="detail-view",
        )


class _FastRichLogHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield FastRichLog(id="log")


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
async def test_fast_widgets_page_scroll_immediately(monkeypatch):
    """Shared fast widgets should page-scroll without animation by default."""
    apps = (
        (_FastListHarness(), FastListView, "#list-view"),
        (_FastScrollableHarness(), FastScrollableContainer, "#detail-view"),
        (_FastRichLogHarness(), FastRichLog, "#log"),
    )

    for app, widget_type, selector in apps:
        async with app.run_test(size=(40, 10)) as pilot:
            await pilot.pause()
            widget = app.query_one(selector, widget_type)
            calls: list[dict[str, object]] = []

            def fake_scroll_to(*args, **kwargs):
                calls.append(kwargs)

            monkeypatch.setattr(widget, "scroll_to", fake_scroll_to)
            widget.scroll_page_down()
            widget.scroll_page_up()

            assert len(calls) == 2
            assert calls[0]["animate"] is False
            assert calls[0]["immediate"] is True
            assert calls[1]["animate"] is False
            assert calls[1]["immediate"] is True


@pytest.mark.asyncio
async def test_fast_list_view_page_down_moves_highlight_to_first_visible_entry():
    """Page Down should move the highlight to the first visible non-disabled row."""
    app = _FastPagedListHarness()

    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        lv = app.query_one(FastListView)

        lv.action_page_down()
        await pilot.pause()

        assert lv.index == 10


@pytest.mark.asyncio
async def test_fast_list_view_page_up_moves_highlight_to_first_visible_entry():
    """Page Up should move the highlight back to the first visible non-disabled row."""
    app = _FastPagedListHarness()

    async with app.run_test(size=(40, 10)) as pilot:
        await pilot.pause()
        lv = app.query_one(FastListView)

        lv.action_page_down()
        lv.action_page_up()
        await pilot.pause()

        assert lv.index == 1


@pytest.mark.asyncio
async def test_all_p5_tuis_use_fast_widgets():
    """Every interactive p5 view should use the shared responsive widgets."""
    from p5.commands.diff import DiffApp, FileEntry, GROUP_MODIFIED
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
    diff_app = DiffApp(
        groups={
            GROUP_MODIFIED: [
                FileEntry(
                    depot_path="//depot/myproject/src/alpha.cpp",
                    local_path="/tmp/src/alpha.cpp",
                    action="edit",
                    file_type="text",
                    display_path="src/alpha.cpp",
                )
            ]
        },
        initial_cache={
            "//depot/myproject/src/alpha.cpp": [("diff src/alpha.cpp", "dim")]
        },
    )

    async with workspace_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(workspace_app.query_one("#list-view"), FastListView)

    async with changes_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(changes_app.query_one("#list-view"), FastListView)
        assert isinstance(changes_app.query_one("#detail-view"), FastScrollableContainer)

    async with change_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(change_app.query_one("#file-list"), FastListView)
        assert isinstance(change_app.query_one("#detail-view"), FastScrollableContainer)

    async with submit_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(submit_app.query_one("#main-list"), FastListView)
        assert isinstance(submit_app.query_one("#detail-view"), FastScrollableContainer)

    async with diff_app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        assert isinstance(diff_app.query_one("#file-list"), FastRichLog)
        assert isinstance(diff_app.query_one("#diff-log"), FastRichLog)
