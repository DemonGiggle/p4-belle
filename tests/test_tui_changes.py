"""TUI tests for ChangesApp diff interactions."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest


def _demo_record(*, diff: str, loaded: bool = True, file_count: int = 1):
    from p5.tui.changes_app import ChangeFileRecord, ChangeRecord

    files = []
    for i in range(file_count):
        file_rec = ChangeFileRecord(
            action="edit",
            path=f"src/file_{i}.cpp",
            depot_file=f"//depot/project/src/file_{i}.cpp",
            rev="2",
            file_type="text",
        )
        if i == 0 and diff:
            file_rec.diff = diff
            file_rec.diff_loaded = True
        files.append(file_rec)
    return ChangeRecord(
        cl="123456",
        date="2026-05-06",
        user="gigo",
        description="Demo change",
        diff=diff,
        files=files,
        loaded=loaded,
    )


@pytest.mark.asyncio
async def test_enter_opens_summary_before_diff():
    """Opening a change should show description/files first, not immediately open a diff."""
    from p5.tui.changes_app import ChangesApp

    app = ChangesApp(
        demo_records=[
            _demo_record(
                diff="--- a/src/file_0.cpp\n+++ b/src/file_0.cpp\n@@ -1 +1 @@\n-old\n+new\n",
            )
        ]
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.detail_open is True
        assert app._detail_rec is not None
        assert app._detail_diff_file is None
        assert app._detail_file_index == 0


@pytest.mark.asyncio
async def test_w_toggles_whitespace_mode_for_selected_file_diff():
    """Pressing w in file diff view should toggle whitespace handling."""
    from p5.tui.changes_app import ChangesApp

    app = ChangesApp(
        demo_records=[
            _demo_record(
                diff=(
                    "==== //depot/project/src/file_0.cpp#2 (text) ====\n"
                    "--- a/src/file_0.cpp\n"
                    "+++ b/src/file_0.cpp\n"
                    "@@ -1 +1 @@\n"
                    "-value = 1\n"
                    "+value    =    1\n"
                ),
            )
        ]
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app._ignore_whitespace is False
        assert app._detail_diff_file is not None

        await pilot.press("w")
        await pilot.pause()

        assert app._ignore_whitespace is True


@pytest.mark.asyncio
async def test_b_toggles_side_by_side_mode_for_selected_file_diff():
    """Pressing b in file diff view should toggle side-by-side rendering."""
    from p5.tui.changes_app import ChangesApp

    app = ChangesApp(
        demo_records=[
            _demo_record(
                diff="--- a/src/file_0.cpp\n+++ b/src/file_0.cpp\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
            )
        ]
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app._side_by_side is False
        assert app._detail_diff_file is not None

        await pilot.press("b")
        await pilot.pause()

        assert app._side_by_side is True


@pytest.mark.asyncio
async def test_cursor_keys_scroll_selected_file_diff_without_crashing():
    """Cursor navigation in diff view should use Textual's keyword scroll API."""
    from p5.tui.changes_app import ChangesApp

    app = ChangesApp(
        demo_records=[
            _demo_record(
                diff=(
                    "--- a/src/file_0.cpp\n"
                    "+++ b/src/file_0.cpp\n"
                    "@@ -1,20 +1,20 @@\n"
                    + "".join(f"-old {i}\n+new {i}\n" for i in range(20))
                ),
            )
        ]
    )

    async with app.run_test(size=(120, 12)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app._detail_diff_file is not None

        await pilot.press("down")
        await pilot.press("up")
        await pilot.pause()

        assert app.detail_open is True


def test_detail_diff_cursor_actions_use_scroll_relative_api():
    """Diff cursor actions should use Textual's distance-based scroll API."""
    from p5.tui.changes_app import ChangeFileRecord, ChangeRecord, ChangesApp, DiffView

    class FakeDiffView:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def scroll_relative(self, *, y: int) -> None:
            self.calls.append(y)

        def scroll_down(self, **_kwargs) -> None:
            raise AssertionError("scroll_down should not receive a distance")

        def scroll_up(self, **_kwargs) -> None:
            raise AssertionError("scroll_up should not receive a distance")

    app = ChangesApp(demo_records=[])
    app.detail_open = True
    app._detail_rec = ChangeRecord(
        cl="123456",
        date="2026-05-06",
        user="gigo",
        description="Demo",
        files=[ChangeFileRecord(action="edit", path="src/file_0.cpp")],
        loaded=True,
    )
    app._detail_diff_file = app._detail_rec.files[0]
    fake_view = FakeDiffView()

    with patch.object(app, "query_one", return_value=fake_view) as query_one:
        app.action_cursor_down()
        app.action_cursor_up()

    assert fake_view.calls == [3, -3]
    assert query_one.call_args_list[0].args == ("#detail-view", DiffView)


@pytest.mark.asyncio
async def test_diff_loading_indicator_animates():
    """The loading status should animate while a file diff fetch is in progress."""
    from textual.widgets import Static

    from p5.tui.changes_app import ChangeFileRecord, ChangeRecord, ChangesApp, _CancelledFetch

    record = ChangeRecord(
        cl="123456",
        date="2026-05-06",
        user="gigo",
        description="Slow diff",
        files=[
            ChangeFileRecord(
                action="edit",
                path="src/file_0.cpp",
                depot_file="//depot/project/src/file_0.cpp",
                rev="2",
                file_type="text",
            )
        ],
        loaded=True,
    )

    def fake_fetch(_rec, _file_rec, should_cancel):
        for _ in range(30):
            if should_cancel():
                raise _CancelledFetch()
            time.sleep(0.02)
        return "(no differences)"

    app = ChangesApp(demo_records=[record])
    with patch("p5.tui.changes_app._fetch_file_diff_for_change", side_effect=fake_fetch):
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            status = app.query_one("#loading-status", Static)
            first = status.content
            await pilot.pause(0.25)
            second = status.content

            assert first != second

            await pilot.press("escape")
            await pilot.pause(0.3)

@pytest.mark.asyncio
async def test_escape_cancels_pending_diff_and_returns_to_summary():
    """Esc during a file diff load should cancel the result and return to file summary."""
    from p5.tui.changes_app import ChangeFileRecord, ChangeRecord, ChangesApp, _CancelledFetch

    record = ChangeRecord(
        cl="123456",
        date="2026-05-06",
        user="gigo",
        description="Slow diff",
        files=[
            ChangeFileRecord(
                action="edit",
                path="src/file_0.cpp",
                depot_file="//depot/project/src/file_0.cpp",
                rev="2",
                file_type="text",
            )
        ],
        loaded=True,
    )

    def fake_fetch(_rec, file_rec, should_cancel):
        for _ in range(20):
            if should_cancel():
                raise _CancelledFetch()
            time.sleep(0.01)
        file_rec.diff = "--- a/src/file_0.cpp\n+++ b/src/file_0.cpp\n@@ -1 +1 @@\n-old\n+new\n"
        file_rec.diff_loaded = True
        return file_rec.diff

    app = ChangesApp(demo_records=[record])
    with patch("p5.tui.changes_app._fetch_file_diff_for_change", side_effect=fake_fetch):
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app._detail_diff_loading is True

            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause(0.3)

            assert app.detail_open is True
            assert app._detail_diff_loading is False
            assert app._detail_diff_file is None


def test_fetch_submitted_edit_diff_uses_p4_diff2():
    """Submitted edit diffs should be delegated to p4 to avoid blocking Textual's event loop."""
    from p5.tui.changes_app import ChangeFileRecord, ChangeRecord, _fetch_file_diff_for_change

    rec = ChangeRecord(cl="123456", date="2026-05-06", user="gigo", description="Demo")
    file_rec = ChangeFileRecord(
        action="edit",
        path="src/file_0.cpp",
        depot_file="//depot/project/src/file_0.cpp",
        rev="5",
        file_type="text",
    )

    should_cancel = lambda: False
    with patch("p5.tui.changes_app._run_p4_cancellable", return_value="diff from p4") as run_p4:
        diff = _fetch_file_diff_for_change(rec, file_rec, should_cancel)

    assert diff == "diff from p4"
    run_p4.assert_called_once_with(
        ["diff2", "-du", "//depot/project/src/file_0.cpp#4", "//depot/project/src/file_0.cpp#5"],
        should_cancel,
    )


def test_colorize_diff_can_hide_whitespace_only_changes():
    """Whitespace-only changes should collapse when the ignore option is active."""
    from p5.tui.changes_app import _colorize_diff

    raw = (
        "==== //depot/myproject/src/alpha.cpp#5 (text) ====\n"
        "--- a/src/alpha.cpp\n"
        "+++ b/src/alpha.cpp\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value    =    1\n"
    )

    with patch("p5.tui.changes_app.any_to_rel", return_value="src/alpha.cpp"):
        rendered = _colorize_diff(raw)
        assert rendered[0] == "[bold white]diff src/alpha.cpp[/bold white]"
        assert _colorize_diff(raw, ignore_whitespace=True) == ["[dim](no differences)[/dim]"]


def test_render_diff_lines_supports_side_by_side():
    """Side-by-side rendering should emit paired columns with a separator."""
    from p5.tui.changes_app import _render_diff_lines

    rendered = _render_diff_lines(
        "--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        side_by_side=True,
    )

    assert any("│" in line.plain for line in rendered)


def test_render_diff_lines_keeps_diff_colors_in_side_by_side():
    """Side-by-side rendering should keep add/delete styling."""
    from p5 import theme as T
    from p5.tui.changes_app import _render_diff_lines

    rendered = _render_diff_lines(
        "--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
        side_by_side=True,
    )

    spans = [span.style for line in rendered for span in line.spans if span.style]
    assert any(T.DIFF_DEL_BG in style for style in spans)
    assert any(T.DIFF_ADD_BG in style for style in spans)


def test_render_diff_lines_uses_provided_column_width():
    """Side-by-side rendering should expand columns when more width is available."""
    from p5.tui.changes_app import _render_diff_lines

    before_line = "left side " * 8
    after_line = "right side " * 8
    rendered = _render_diff_lines(
        f"--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n-{before_line}\n+{after_line}\n",
        side_by_side=True,
        column_width=90,
    )

    assert any(before_line in line.plain for line in rendered)
    assert any(after_line in line.plain for line in rendered)
    assert not any("…" in line.plain for line in rendered)


def test_render_diff_lines_does_not_show_spurious_bracket_escape():
    """Square brackets in diff content should not render a visible backslash."""
    from p5.tui.changes_app import _render_diff_lines

    rendered = _render_diff_lines(
        "--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n-old = []\n+new = []\n",
    )

    assert any("[]" in line.plain for line in rendered)
    assert not any("[\\]" in line.plain for line in rendered)


def test_render_diff_lines_does_not_render_literal_rich_closing_tags_with_escape_slash():
    """Literal text that looks like a Rich closing tag should remain plain text."""
    from p5.tui.changes_app import _render_diff_lines

    rendered = _render_diff_lines(
        "--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n+[/on #1a3a1a]\n",
    )

    assert any("[/on #1a3a1a]" in line.plain for line in rendered)
    assert not any("\\[/on #1a3a1a]" in line.plain for line in rendered)
