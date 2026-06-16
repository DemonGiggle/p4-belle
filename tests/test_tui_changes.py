"""TUI tests for ChangesApp diff interactions."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_w_toggles_whitespace_mode_for_change_list_diff():
    """Pressing w in changelist detail should toggle whitespace handling."""
    from p5.tui.changes_app import ChangeRecord, ChangesApp

    app = ChangesApp(
        demo_records=[
            ChangeRecord(
                cl="123456",
                date="2026-05-06",
                user="gigo",
                description="Whitespace-only tweak",
                diff=(
                    "==== //depot/myproject/src/alpha.cpp#5 (text) ====\n"
                    "--- a/src/alpha.cpp\n"
                    "+++ b/src/alpha.cpp\n"
                    "@@ -1 +1 @@\n"
                    "-value = 1\n"
                    "+value    =    1\n"
                ),
                loaded=True,
            )
        ]
    )

    with patch("p5.tui.changes_app.any_to_rel", return_value="src/alpha.cpp"):
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert app._ignore_whitespace is False

            await pilot.press("w")
            await pilot.pause()

            assert app._ignore_whitespace is True


@pytest.mark.asyncio
async def test_b_toggles_side_by_side_mode_for_change_list_diff():
    """Pressing b in changelist detail should toggle side-by-side rendering."""
    from p5.tui.changes_app import ChangeRecord, ChangesApp

    app = ChangesApp(
        demo_records=[
            ChangeRecord(
                cl="123456",
                date="2026-05-06",
                user="gigo",
                description="View toggle",
                diff="--- a/src/alpha.cpp\n+++ b/src/alpha.cpp\n@@ -1 +1 @@\n-value = 1\n+value = 2\n",
                loaded=True,
            )
        ]
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert app._side_by_side is False

        await pilot.press("b")
        await pilot.pause()

        assert app._side_by_side is True


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
