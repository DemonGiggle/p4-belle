"""Tests for p5.workspace — path resolution without a real p4 server."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from p5.p4 import P4Error

# These tests construct a Workspace directly with controlled _info / depot_prefix.

FAKE_ROOT = "/home/testuser/workspace/myproject"
FAKE_PREFIX = "//depot/myproject"
FAKE_CLIENT = "testuser-myproject"

FAKE_P4_INFO = f"""\
User name: testuser
Client name: {FAKE_CLIENT}
Client host: devbox
Client root: {FAKE_ROOT}
"""

FAKE_P4_CLIENT_OUTPUT = f"""\
Client: {FAKE_CLIENT}
Root: {FAKE_ROOT}
View:
\t{FAKE_PREFIX}/... //{FAKE_CLIENT}/...
"""


@pytest.fixture(autouse=True)
def _reset_workspace():
    """Reset the module-level singleton before each test."""
    import p5.workspace as ws
    ws._workspace = None
    yield
    ws._workspace = None


@pytest.fixture()
def workspace():
    """Return a Workspace object backed by fake p4 output."""
    from p5.workspace import Workspace

    def _side_effect(args, *, cwd=None, check=True):
        joined = " ".join(args)
        if "info" in joined:
            return FAKE_P4_INFO
        if "client -o" in joined:
            return FAKE_P4_CLIENT_OUTPUT
        return ""

    with patch("p5.workspace.run_p4", side_effect=_side_effect), patch(
        "p5.p4.run_p4", side_effect=_side_effect
    ):
        ws = Workspace()
        # Force cache population
        _ = ws.client_root
        _ = ws.view_mappings
        _ = ws.depot_prefix
    return ws


class TestWorkspaceProperties:
    def test_client_root(self, workspace):
        assert str(workspace.client_root) == FAKE_ROOT

    def test_client_name(self, workspace):
        assert workspace.client_name == FAKE_CLIENT

    def test_depot_prefix(self, workspace):
        assert workspace.depot_prefix == FAKE_PREFIX


class TestDepotToRel:
    def test_depot_path_under_prefix(self, workspace):
        assert workspace.depot_to_rel("//depot/myproject/src/main.cpp") == "src/main.cpp"

    def test_depot_path_not_under_prefix(self, workspace):
        # Falls through — returns the depot path unchanged
        assert workspace.depot_to_rel("//other/repo/foo.cpp") == "//other/repo/foo.cpp"

    def test_non_depot_path_passthrough(self, workspace):
        assert workspace.depot_to_rel("just/a/path") == "just/a/path"


class TestLocalToDepot:
    def test_absolute_under_root(self, workspace):
        result = workspace.local_to_depot(f"{FAKE_ROOT}/src/main.cpp")
        assert result == f"{FAKE_PREFIX}/src/main.cpp"

    def test_depot_path_passthrough(self, workspace):
        assert workspace.local_to_depot("//depot/myproject/a.cpp") == "//depot/myproject/a.cpp"

    def test_outside_root(self, workspace):
        # Path not under client root — returned as-is
        result = workspace.local_to_depot("/tmp/random/file.cpp")
        assert result == "/tmp/random/file.cpp"


class TestLocalToRel:
    def test_abs_path(self, workspace):
        assert workspace.local_to_rel(f"{FAKE_ROOT}/src/foo.cpp") == "src/foo.cpp"

    def test_outside_root_returns_as_is(self, workspace):
        result = workspace.local_to_rel("/tmp/elsewhere/bar.cpp")
        assert result == "/tmp/elsewhere/bar.cpp"


class TestAnyToRel:
    def test_depot_path(self, workspace):
        assert workspace.any_to_rel("//depot/myproject/src/foo.cpp") == "src/foo.cpp"

    def test_absolute_local_path(self, workspace):
        assert workspace.any_to_rel(f"{FAKE_ROOT}/src/foo.cpp") == "src/foo.cpp"


class TestCheckCwdInWorkspace:
    def test_inside_workspace(self, workspace):
        from p5.workspace import check_cwd_in_workspace

        with patch("p5.workspace.get_workspace", return_value=workspace):
            # Should not raise
            check_cwd_in_workspace(cwd=f"{FAKE_ROOT}/src")

    def test_outside_workspace(self, workspace):
        from p5.workspace import check_cwd_in_workspace

        with patch("p5.workspace.get_workspace", return_value=workspace):
            with pytest.raises(P4Error, match="not inside workspace"):
                check_cwd_in_workspace(cwd="/tmp/elsewhere")

# ── Multi-map fixtures (issue #12) ──────────────────────────────────────────

MULTI_ROOT = "/home/testuser/workspace/multi"
MULTI_CLIENT = "testuser-multi"

MULTI_P4_INFO = f"""\
User name: testuser
Client name: {MULTI_CLIENT}
Client host: devbox
Client root: {MULTI_ROOT}
"""

MULTI_P4_CLIENT_OUTPUT = f"""\
Client: {MULTI_CLIENT}
Root: {MULTI_ROOT}
View:
\t//depot/main/... //{MULTI_CLIENT}/main/...
\t//depot/libs/foo/... //{MULTI_CLIENT}/libs/foo/...
"""


def _make_workspace(info: str, client_output: str):
    """Build a Workspace backed by the given fake `p4 info` / `p4 client -o`."""
    from p5.workspace import Workspace

    def _side_effect(args, *, cwd=None, check=True):
        joined = " ".join(args)
        if "info" in joined:
            return info
        if "client -o" in joined:
            return client_output
        return ""

    with patch("p5.workspace.run_p4", side_effect=_side_effect), patch(
        "p5.p4.run_p4", side_effect=_side_effect
    ):
        ws = Workspace()
        # Populate caches inside the patched context
        _ = ws.client_root
        _ = ws.view_mappings
        _ = ws.depot_prefix
    return ws


@pytest.fixture()
def multi_workspace():
    return _make_workspace(MULTI_P4_INFO, MULTI_P4_CLIENT_OUTPUT)


class TestMultiMapWorkspace:
    def test_depot_prefix_is_first_mapping(self, multi_workspace):
        assert multi_workspace.depot_prefix == "//depot/main"

    def test_view_mappings_ordered(self, multi_workspace):
        assert multi_workspace.view_mappings == [
            ("//depot/main", "main"),
            ("//depot/libs/foo", "libs/foo"),
        ]

    def test_local_to_depot_first_mapping(self, multi_workspace):
        result = multi_workspace.local_to_depot(f"{MULTI_ROOT}/main/src/a.cpp")
        assert result == "//depot/main/src/a.cpp"

    def test_local_to_depot_second_mapping(self, multi_workspace):
        # File outside the first mapping — the issue #12 bug returned
        # //depot/main/libs/foo/... instead of the correct second prefix.
        result = multi_workspace.local_to_depot(f"{MULTI_ROOT}/libs/foo/bar.cpp")
        assert result == "//depot/libs/foo/bar.cpp"

    def test_depot_to_rel_first_mapping(self, multi_workspace):
        assert multi_workspace.depot_to_rel("//depot/main/src/a.cpp") == "main/src/a.cpp"

    def test_depot_to_rel_second_mapping(self, multi_workspace):
        assert multi_workspace.depot_to_rel("//depot/libs/foo/bar.cpp") == "libs/foo/bar.cpp"

    def test_depot_to_rel_unknown_returns_unchanged(self, multi_workspace):
        assert multi_workspace.depot_to_rel("//other/repo/foo.cpp") == "//other/repo/foo.cpp"

    def test_any_to_rel_second_mapping(self, multi_workspace):
        assert multi_workspace.any_to_rel("//depot/libs/foo/bar.cpp") == "libs/foo/bar.cpp"


class TestLongestMatch:
    def test_depot_longest_match_wins(self):
        info = MULTI_P4_INFO
        client_output = (
            f"Client: {MULTI_CLIENT}\nRoot: {MULTI_ROOT}\nView:\n"
            f"\t//depot/a/... //{MULTI_CLIENT}/a/...\n"
            f"\t//depot/a/b/... //{MULTI_CLIENT}/c/...\n"
        )
        ws = _make_workspace(info, client_output)
        # //depot/a/b/f.cpp matches both depot bases; longest (//depot/a/b) wins.
        assert ws.depot_to_rel("//depot/a/b/f.cpp") == "c/f.cpp"
        assert ws.depot_to_rel("//depot/a/other.cpp") == "a/other.cpp"

    def test_client_longest_match_wins(self):
        info = MULTI_P4_INFO
        client_output = (
            f"Client: {MULTI_CLIENT}\nRoot: {MULTI_ROOT}\nView:\n"
            f"\t//depot/x/... //{MULTI_CLIENT}/shared/...\n"
            f"\t//depot/y/... //{MULTI_CLIENT}/shared/sub/...\n"
        )
        ws = _make_workspace(info, client_output)
        # shared/sub/f.cpp matches both client rels; longest (shared/sub) wins.
        assert ws.local_to_depot(f"{MULTI_ROOT}/shared/sub/f.cpp") == "//depot/y/f.cpp"
        assert ws.local_to_depot(f"{MULTI_ROOT}/shared/other.cpp") == "//depot/x/other.cpp"


# ── Exclusion-line fixtures (issue #12) ─────────────────────────────────────

EXCL_ROOT = FAKE_ROOT
EXCL_CLIENT = FAKE_CLIENT

EXCL_P4_INFO = FAKE_P4_INFO

EXCL_P4_CLIENT_OUTPUT = f"""\
Client: {EXCL_CLIENT}
Root: {EXCL_ROOT}
View:
\t{FAKE_PREFIX}/... //{EXCL_CLIENT}/...
\t-//depot/myproject/excluded/... //{EXCL_CLIENT}/excluded/...
\t//depot/other/... //{EXCL_CLIENT}/other/...
"""


@pytest.fixture()
def excl_workspace():
    return _make_workspace(EXCL_P4_INFO, EXCL_P4_CLIENT_OUTPUT)


class TestExclusionLines:
    def test_exclusion_not_treated_as_prefix(self, excl_workspace):
        assert excl_workspace.depot_prefix == FAKE_PREFIX
        assert all(not depot.startswith("-") for depot, _ in excl_workspace.view_mappings)

    def test_exclusion_skipped_in_mappings(self, excl_workspace):
        assert excl_workspace.view_mappings == [
            (FAKE_PREFIX, ""),
            ("//depot/other", "other"),
        ]

    def test_excluded_path_still_resolves_via_including_map(self, excl_workspace):
        # Exclusions are ignored (not treated as removals): a file under the
        # excluded depot path still maps through the covering root mapping.
        assert excl_workspace.depot_to_rel("//depot/myproject/excluded/foo.cpp") == "excluded/foo.cpp"
        assert (
            excl_workspace.local_to_depot(f"{EXCL_ROOT}/excluded/foo.cpp")
            == "//depot/myproject/excluded/foo.cpp"
        )

    def test_other_mapping_resolves(self, excl_workspace):
        assert excl_workspace.local_to_depot(f"{EXCL_ROOT}/other/bar.cpp") == "//depot/other/bar.cpp"
        assert excl_workspace.depot_to_rel("//depot/other/bar.cpp") == "other/bar.cpp"


class TestStreamLikeView:
    def test_stream_view_with_stream_field(self):
        # Stream clients emit a Stream: field plus generated View lines;
        # parsing must still pick up every mapping in order.
        info = (
            "User name: testuser\n"
            "Client name: stream-client\n"
            "Client host: devbox\n"
            "Client root: /home/testuser/workspace/stream\n"
        )
        client_output = (
            "Client: stream-client\n"
            "Root: /home/testuser/workspace/stream\n"
            "Stream: //streams/main\n"
            "View:\n"
            "\t//streams/main/src/... //stream-client/src/...\n"
            "\t//streams/main/tests/... //stream-client/tests/...\n"
        )
        ws = _make_workspace(info, client_output)
        assert ws.depot_prefix == "//streams/main/src"
        assert ws.view_mappings == [
            ("//streams/main/src", "src"),
            ("//streams/main/tests", "tests"),
        ]
        assert ws.local_to_depot("/home/testuser/workspace/stream/tests/a.cpp") == "//streams/main/tests/a.cpp"
        assert ws.depot_to_rel("//streams/main/src/b.cpp") == "src/b.cpp"
