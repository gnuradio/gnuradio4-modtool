"""Tests for the publish command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from rich.console import Console

from gr4_modtool.commands.publish import (
    KNOWN_TARGETS,
    PreFlightResult,
    _check_cmake_sync,
    _check_git_clean,
    _check_git_tag,
    _check_validate,
    _check_version,
    _do_publish,
    _render_table,
    cmd,
    pre_flight,
)
from gr4_modtool.project.discovery import ProjectConfig, save_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

_NO_PRAGMA_HEADER = """\
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""


def _write_block(cfg: ProjectConfig, group: str, name: str, template: str = _GOOD_HEADER) -> Path:
    inc = cfg.group_include_dir(group)
    inc.mkdir(parents=True, exist_ok=True)
    p = inc / f"{name}.hpp"
    p.write_text(template.format(name=name))
    return p


def _make_git_result(stdout: str = "", returncode: int = 0) -> MagicMock:
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.returncode = returncode
    return r


# ---------------------------------------------------------------------------
# Pre-flight: version check
# ---------------------------------------------------------------------------


def test_check_version_valid(project: ProjectConfig) -> None:
    r = _check_version(project)
    assert r.check_id == "version"
    assert r.status == "pass"


def test_pre_flight_bad_version(project: ProjectConfig) -> None:
    project.version = "not-a-version"
    save_config(project)
    r = _check_version(project)
    assert r.status == "fail"
    assert "X.Y.Z" in r.detail


# ---------------------------------------------------------------------------
# Pre-flight: validate check
# ---------------------------------------------------------------------------


def test_pre_flight_clean_project(project: ProjectConfig) -> None:
    r = _check_validate(project)
    assert r.status == "pass"


def test_pre_flight_validation_errors(project: ProjectConfig) -> None:
    _write_block(project, "basic", "MyFilter", template=_NO_PRAGMA_HEADER)
    r = _check_validate(project)
    assert r.status == "fail"
    assert "error" in r.detail


# ---------------------------------------------------------------------------
# Pre-flight: cmake_sync
# ---------------------------------------------------------------------------


def test_pre_flight_cmake_absent(project: ProjectConfig) -> None:
    r = _check_cmake_sync(project)
    assert r.status == "skip"


def test_pre_flight_cmake_match(project: ProjectConfig) -> None:
    (project.root / "CMakeLists.txt").write_text(
        f"project(testmod LANGUAGES CXX VERSION {project.version})\n"
    )
    r = _check_cmake_sync(project)
    assert r.status == "pass"


def test_pre_flight_cmake_mismatch(project: ProjectConfig) -> None:
    (project.root / "CMakeLists.txt").write_text("project(testmod LANGUAGES CXX VERSION 9.9.9)\n")
    r = _check_cmake_sync(project)
    assert r.status == "warn"
    assert "9.9.9" in r.detail


# ---------------------------------------------------------------------------
# Pre-flight: git checks (monkeypatched)
# ---------------------------------------------------------------------------


def test_pre_flight_git_clean(project: ProjectConfig, monkeypatch) -> None:
    monkeypatch.setattr(
        "gr4_modtool.commands.publish._git_run",
        lambda *_a, **_kw: _make_git_result(""),
    )
    r = _check_git_clean(project)
    assert r.status == "pass"


def test_pre_flight_git_dirty(project: ProjectConfig, monkeypatch) -> None:
    monkeypatch.setattr(
        "gr4_modtool.commands.publish._git_run",
        lambda *_a, **_kw: _make_git_result(" M somefile.cpp\n"),
    )
    r = _check_git_clean(project)
    assert r.status == "warn"
    assert "1 uncommitted" in r.detail


def test_pre_flight_git_unavailable(project: ProjectConfig, monkeypatch) -> None:
    monkeypatch.setattr(
        "gr4_modtool.commands.publish._git_run",
        lambda *_a, **_kw: None,
    )
    r_clean = _check_git_clean(project)
    r_tag = _check_git_tag(project)
    assert r_clean.status == "skip"
    assert r_tag.status == "skip"


def test_pre_flight_git_tag_absent(project: ProjectConfig, monkeypatch) -> None:
    monkeypatch.setattr(
        "gr4_modtool.commands.publish._git_run",
        lambda *_a, **_kw: _make_git_result(""),
    )
    r = _check_git_tag(project)
    assert r.status == "pass"


def test_pre_flight_git_tag_exists(project: ProjectConfig, monkeypatch) -> None:
    monkeypatch.setattr(
        "gr4_modtool.commands.publish._git_run",
        lambda *_a, **_kw: _make_git_result(f"v{project.version}\n"),
    )
    r = _check_git_tag(project)
    assert r.status == "warn"
    assert "already exists" in r.detail


# ---------------------------------------------------------------------------
# pre_flight orchestrator
# ---------------------------------------------------------------------------


def test_pre_flight_returns_all_checks(project: ProjectConfig) -> None:
    results = pre_flight(project)
    ids = {r.check_id for r in results}
    assert {"version", "validate", "cmake_sync", "git_clean", "git_tag"} == ids


# ---------------------------------------------------------------------------
# KNOWN_TARGETS
# ---------------------------------------------------------------------------


def test_known_targets_contains_local() -> None:
    assert "local" in KNOWN_TARGETS


def test_known_targets_contains_github() -> None:
    assert "github" in KNOWN_TARGETS


# ---------------------------------------------------------------------------
# _do_publish stub
# ---------------------------------------------------------------------------


def test_do_publish_stub_output(
    project: ProjectConfig, tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    for target in KNOWN_TARGETS:
        _do_publish(project, target)
        # Just verify it doesn't raise and says something
        assert capsys.readouterr().out.strip()


def test_do_publish_github_mentions_version(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(cmd, ["--target", "github", "--yes", "--project-dir", str(project.root)])
    assert project.version in result.output


# ---------------------------------------------------------------------------
# _render_table
# ---------------------------------------------------------------------------


def test_render_table_all_pass(project: ProjectConfig) -> None:
    results = [PreFlightResult(c, "pass", "ok") for c in ("version", "validate")]
    console = Console(record=True, no_color=True)
    _render_table(results, console)
    assert "Ready to publish" in console.export_text()


def test_render_table_failure(project: ProjectConfig) -> None:
    results = [
        PreFlightResult("version", "pass", "ok"),
        PreFlightResult("validate", "fail", "2 errors"),
    ]
    console = Console(record=True, no_color=True)
    _render_table(results, console)
    text = console.export_text()
    assert "failed" in text.lower() or "check(s)" in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_cli_clean_project_exits_0(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0


def test_cli_exits_1_on_fail(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter", template=_NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--project-dir", str(project.root), "--yes"])
    assert result.exit_code == 1


def test_cli_dry_run_no_publish(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--dry-run", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_cli_target_local_yes(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--target", "local", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0


def test_cli_target_github_yes(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--target", "github", "--yes", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "stub" in result.output.lower() or "github" in result.output.lower()


def test_cli_invalid_target(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--target", "nonexistent", "--project-dir", str(project.root)])
    assert result.exit_code != 0


def test_cli_json_output_passes(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "results" in data
    assert data["ready"] is True


def test_cli_json_output_fails(project: ProjectConfig, runner: CliRunner) -> None:
    _write_block(project, "basic", "MyFilter", template=_NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ready"] is False
    assert data["fail_count"] > 0


def test_cli_json_has_check_ids(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    data = json.loads(result.output)
    ids = {r["check_id"] for r in data["results"]}
    assert "version" in ids
    assert "validate" in ids
    assert "cmake_sync" in ids
