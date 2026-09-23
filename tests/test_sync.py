"""Tests for gr4_modtool sync command (plan_sync / apply_sync / CLI)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gr4_modtool.commands.sync import SyncAction, apply_sync, cmd, plan_sync

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_header(cfg, group: str, block: str) -> Path:
    """Create a minimal header file for *block* in *group*."""
    hpp = cfg.group_include_dir(group) / f"{block}.hpp"
    hpp.write_text(
        f"// auto-generated stub\n"
        f"template <typename T>\n"
        f"struct {block} : Block<{block}<T>> {{\n"
        f"    PortIn<T> in{{}};\n"
        f"    PortOut<T> out{{}};\n"
        f"    [[nodiscard]] T processOne(T x) {{ return x; }}\n"
        f"}};\n"
    )
    return hpp


def _write_test_src(cfg, group: str, block: str) -> Path:
    """Create a minimal qa_<block>.cpp in the test dir."""
    src = cfg.group_test_dir(group) / f"qa_{block}.cpp"
    src.write_text(f"// qa stub for {block}\n")
    return src


def _write_cmake_entry(cfg, group: str, block: str) -> None:
    cmake_file = cfg.group_test_dir(group) / "CMakeLists.txt"
    text = cmake_file.read_text()
    cmake_file.write_text(
        text.rstrip() + f"\ngr4_modtool_add_ut_test(qa_{block} qa_{block}.cpp)\n"
        f"target_link_libraries(qa_{block} PRIVATE gr4_testmod::blocks_{group}_headers)\n"
    )


# ---------------------------------------------------------------------------
# plan_sync — no-op
# ---------------------------------------------------------------------------


def test_nothing_to_sync(project) -> None:
    """Empty group produces no actions."""
    actions = plan_sync(project)
    assert actions == []


# ---------------------------------------------------------------------------
# plan_sync — generate_test
# ---------------------------------------------------------------------------


def test_plan_generate_test(project) -> None:
    """Header with no test source → generate_test action."""
    _write_header(project, "basic", "Foo")
    actions = plan_sync(project)
    assert any(a.action == "generate_test" and a.block == "Foo" for a in actions)


def test_plan_no_extra_entries_when_generating(project) -> None:
    """When generate_test is planned, no add_cmake for the same block."""
    _write_header(project, "basic", "Foo")
    actions = plan_sync(project)
    extra = [a for a in actions if a.block == "Foo" and a.action in ("add_cmake_entry",)]
    assert not extra


# ---------------------------------------------------------------------------
# plan_sync — add missing build entries
# ---------------------------------------------------------------------------


def test_plan_add_cmake_entry(project) -> None:
    """Test source exists without cmake entry → add_cmake_entry."""
    _write_header(project, "basic", "Foo")
    _write_test_src(project, "basic", "Foo")
    # no cmake entry yet
    actions = plan_sync(project)
    assert any(a.action == "add_cmake_entry" and a.block == "Foo" for a in actions)


def test_plan_no_actions_when_fully_registered(project) -> None:
    """Header + test source + build entries → no actions."""
    _write_header(project, "basic", "Foo")
    _write_test_src(project, "basic", "Foo")
    _write_cmake_entry(project, "basic", "Foo")
    actions = plan_sync(project)
    # Only possible remaining action: warn_orphan — not expected here since header exists
    actionable = [a for a in actions if a.action != "warn_orphan"]
    assert not actionable


# ---------------------------------------------------------------------------
# plan_sync — prune stale entries
# ---------------------------------------------------------------------------


def test_plan_stale_not_in_plan_without_prune(project) -> None:
    """Stale cmake entry (no source, no header) not reported without --prune."""
    _write_cmake_entry(project, "basic", "Gone")
    actions = plan_sync(project, prune=False)
    assert not any(a.action == "remove_cmake_entry" for a in actions)


def test_plan_prune_stale_cmake(project) -> None:
    """cmake entry with no test source AND no header → remove_cmake_entry with --prune."""
    _write_cmake_entry(project, "basic", "Gone")
    actions = plan_sync(project, prune=True)
    assert any(a.action == "remove_cmake_entry" and a.block == "Gone" for a in actions)


def test_plan_prune_does_not_remove_generating_block(project) -> None:
    """Block with a cmake entry AND a header (but no test source) is regenerated,
    not removed, even with --prune."""
    _write_header(project, "basic", "Regen")
    _write_cmake_entry(project, "basic", "Regen")
    actions = plan_sync(project, prune=True)
    assert not any(a.action == "remove_cmake_entry" and a.block == "Regen" for a in actions)
    assert any(a.action == "generate_test" and a.block == "Regen" for a in actions)


# ---------------------------------------------------------------------------
# plan_sync — orphan warning
# ---------------------------------------------------------------------------


def test_plan_orphan_source_warned(project) -> None:
    """Test source with no header → warn_orphan action."""
    _write_test_src(project, "basic", "Orphan")
    actions = plan_sync(project)
    assert any(a.action == "warn_orphan" and a.block == "Orphan" for a in actions)


# ---------------------------------------------------------------------------
# apply_sync — generate_test
# ---------------------------------------------------------------------------


def test_apply_generates_test_and_build_entries(project) -> None:
    """apply_sync with generate_test creates qa_Foo.cpp and build entries."""
    _write_header(project, "basic", "Foo")
    actions = plan_sync(project)
    assert any(a.action == "generate_test" for a in actions)

    apply_sync(project, actions)

    test_file = project.group_test_dir("basic") / "qa_Foo.cpp"
    assert test_file.exists()


# ---------------------------------------------------------------------------
# apply_sync — add build entries
# ---------------------------------------------------------------------------


def test_apply_adds_cmake_entry(project) -> None:
    """apply_sync with add_cmake_entry writes the entry to CMakeLists.txt."""
    _write_header(project, "basic", "Foo")
    _write_test_src(project, "basic", "Foo")

    actions = [a for a in plan_sync(project) if a.action == "add_cmake_entry"]
    assert actions

    apply_sync(project, actions)

    cmake_text = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_Foo" in cmake_text


# ---------------------------------------------------------------------------
# apply_sync — prune stale cmake entry
# ---------------------------------------------------------------------------


def test_apply_prune_removes_stale_cmake(project) -> None:
    """apply_sync remove_cmake_entry deletes the entry from CMakeLists.txt."""
    _write_cmake_entry(project, "basic", "Gone")

    actions = plan_sync(project, prune=True)
    remove_actions = [a for a in actions if a.action == "remove_cmake_entry"]
    assert remove_actions

    apply_sync(project, remove_actions)

    cmake_text = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "qa_Gone" not in cmake_text


# ---------------------------------------------------------------------------
# apply_sync — parse failure is skipped gracefully
# ---------------------------------------------------------------------------


def test_apply_parse_failure_skips(project) -> None:
    """write_test_for_block parse failure is captured as a warning, not an exception."""
    hpp = project.group_include_dir("basic") / "BadBlock.hpp"
    hpp.write_text("// this header has no struct definition\n")

    actions = [SyncAction("basic", "BadBlock", "generate_test")]
    warnings = apply_sync(project, actions)

    assert any("BadBlock" in w for w in warnings)


# ---------------------------------------------------------------------------
# Flat project
# ---------------------------------------------------------------------------


def test_flat_project_sync(project_flat) -> None:
    """Flat project (no groups) without any headers produces no actions."""
    actions = plan_sync(project_flat)
    assert actions == []


# ---------------------------------------------------------------------------
# CLI — dry-run
# ---------------------------------------------------------------------------


def test_cli_dry_run_no_changes(project) -> None:
    """--dry-run prints the plan but writes no files."""
    _write_header(project, "basic", "Foo")

    runner = CliRunner()
    result = runner.invoke(cmd, ["--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0

    test_file = project.group_test_dir("basic") / "qa_Foo.cpp"
    assert not test_file.exists()


# ---------------------------------------------------------------------------
# CLI — --yes applies without prompt
# ---------------------------------------------------------------------------


def test_cli_yes_applies(project) -> None:
    """--yes applies all actions without interactive confirmation."""
    _write_header(project, "basic", "Foo")

    runner = CliRunner()
    result = runner.invoke(cmd, ["--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0

    test_file = project.group_test_dir("basic") / "qa_Foo.cpp"
    assert test_file.exists()
