"""Unified TUI keybindings matrix — core keys identical, app-specific keys reserved."""
from __future__ import annotations


def _binding_keys(bindings):
    keys: set[str] = set()
    for b in bindings:
        # Textual Binding.key may be "j,down,n" or single key.
        raw = getattr(b, "key", "")
        for part in str(raw).split(","):
            part = part.strip()
            if part:
                keys.add(part)
    return keys


def _binding_actions(bindings):
    return {getattr(b, "key", ""): getattr(b, "action", "") for b in bindings}


def test_core_nav_keys_present_everywhere():
    from p5.commands.diff import DiffApp
    from p5.tui.change_app import ChangeApp
    from p5.tui.changes_app import ChangesApp
    from p5.tui.submit_app import SubmitApp
    from p5.tui.ws_app import WorkspaceApp

    for app_cls in (ChangesApp, ChangeApp, WorkspaceApp, SubmitApp, DiffApp):
        keys = _binding_keys(app_cls.BINDINGS)
        # j/k + arrows + n/p aliases for next/prev
        assert "j" in keys, app_cls
        assert "k" in keys, app_cls
        assert "n" in keys, app_cls
        assert "p" in keys, app_cls
        assert "q" in keys, app_cls
        assert "slash" in keys, app_cls
        assert "r" in keys, app_cls
        assert "question_mark" in keys, app_cls


def test_primary_and_back_keys():
    from p5.commands.diff import DiffApp
    from p5.tui.change_app import ChangeApp
    from p5.tui.changes_app import ChangesApp
    from p5.tui.submit_app import SubmitApp
    from p5.tui.ws_app import WorkspaceApp

    for app_cls in (ChangesApp, ChangeApp, WorkspaceApp, SubmitApp, DiffApp):
        keys = _binding_keys(app_cls.BINDINGS)
        assert "enter" in keys, app_cls
        assert "space" in keys, app_cls
        assert "escape" in keys, app_cls


def test_whitespace_view_page_keys_where_applicable():
    from p5.commands.diff import DiffApp
    from p5.tui.change_app import ChangeApp
    from p5.tui.changes_app import ChangesApp
    from p5.tui.submit_app import SubmitApp

    for app_cls in (ChangesApp, ChangeApp, SubmitApp, DiffApp):
        keys = _binding_keys(app_cls.BINDINGS)
        assert "w" in keys, app_cls
        assert "b" in keys, app_cls
        assert "ctrl+f" in keys, app_cls
        assert "ctrl+b" in keys, app_cls


def test_ws_reserves_diff_keys():
    from p5.tui.ws_app import WorkspaceApp

    keys = _binding_keys(WorkspaceApp.BINDINGS)
    # ws has no diffs: w/b/x/c/m/e/s/u must stay reserved (absent).
    for reserved in ("w", "b", "x", "c", "m", "e", "s", "u", "a"):
        assert reserved not in keys, f"ws should reserve {reserved!r}"


def test_no_key_collisions_for_breaking_renames():
    from p5.tui.change_app import ChangeApp
    from p5.tui.submit_app import SubmitApp

    change_actions = _binding_actions(ChangeApp.BINDINGS)
    submit_actions = _binding_actions(SubmitApp.BINDINGS)

    def action_for(bindings_map, key):
        for k, action in bindings_map.items():
            parts = [p.strip() for p in k.split(",")]
            if key in parts:
                return action
        return None

    # r = reload everywhere (not revert)
    assert action_for(change_actions, "r") == "reload_files"
    assert action_for(submit_actions, "r") == "reload_current"
    # x = revert
    assert action_for(change_actions, "x") == "revert_file"
    assert action_for(submit_actions, "x") == "revert_file"
    # c = new CL (change only)
    assert action_for(change_actions, "c") == "new_cl"


def test_diff_tabs_and_filter():
    from p5.commands.diff import DiffApp

    keys = _binding_keys(DiffApp.BINDINGS)
    assert "[" in keys
    assert "]" in keys
    assert "slash" in keys


def test_add_edit_registered_with_dummy_data():
    from click.testing import CliRunner

    from p5.cli import main

    runner = CliRunner()
    for cmd in ("add", "edit"):
        result = runner.invoke(main, [cmd, "--help"])
        assert result.exit_code == 0, result.output
        assert "--dummy-data" in result.output
        assert "-c" in result.output

    for cmd, args in (
        ("add", ["add", "src/auth/token_cache.cpp", "--dummy-data"]),
        ("edit", ["edit", "src/auth/login.cpp", "--dummy-data"]),
    ):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
        assert "opened" in result.output


def test_global_dummy_data_help_consistent():
    from click.testing import CliRunner

    from p5.cli import main

    runner = CliRunner()
    for cmd in ("status", "diff", "delete", "sync", "change", "submit", "changes", "filelog", "ws", "add", "edit"):
        result = runner.invoke(main, [cmd, "--help"])
        assert result.exit_code == 0, result.output
        assert "--dummy-data" in result.output, cmd
        normalized = " ".join(result.output.split())
        assert "sample output instead of querying Perforce" in normalized, cmd
