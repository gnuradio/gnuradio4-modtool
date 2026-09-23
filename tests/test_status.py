"""Tests for the status dashboard command."""

from __future__ import annotations

from click.testing import CliRunner

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.commands.status import cmd, gather_status
from gr4_modtool.project.discovery import ProjectConfig


def _add_block(project: ProjectConfig, name: str = "MyFilter", gen_test: bool = True) -> None:
    write_block_files(
        project,
        {
            "group_name": "basic",
            "block_name": name,
            "description": "test",
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": "float, double",
            "gen_test": gen_test,
        },
    )


# ---------------------------------------------------------------------------
# gather_status() unit tests
# ---------------------------------------------------------------------------


def test_gather_status_project_name(project: ProjectConfig) -> None:
    status = gather_status(project)
    assert status.name == "testmod"


def test_gather_status_project_version(project: ProjectConfig) -> None:
    status = gather_status(project)
    assert status.version == "0.1.0"


def test_gather_status_group_present(project: ProjectConfig) -> None:
    status = gather_status(project)
    names = [g.name for g in status.groups]
    assert "basic" in names


def test_gather_status_block_count(project: ProjectConfig) -> None:
    _add_block(project, "FilterA")
    _add_block(project, "FilterB")
    status = gather_status(project)
    basic = next(g for g in status.groups if g.name == "basic")
    assert basic.block_count == 2


def test_gather_status_all_tested(project: ProjectConfig) -> None:
    _add_block(project, gen_test=True)
    status = gather_status(project)
    basic = next(g for g in status.groups if g.name == "basic")
    assert basic.missing_tests == []
    assert basic.tested_count == basic.block_count


def test_gather_status_detects_missing_test(project: ProjectConfig) -> None:
    _add_block(project, gen_test=False)
    status = gather_status(project)
    basic = next(g for g in status.groups if g.name == "basic")
    assert "MyFilter" in basic.missing_tests


def test_gather_status_detects_cmake(project: ProjectConfig) -> None:
    status = gather_status(project)
    assert status.build_cmake is True


def test_gather_status_detects_ci_workflow(project: ProjectConfig) -> None:
    wf_dir = project.root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("name: CI\n")
    status = gather_status(project)
    assert "ci.yml" in status.ci_workflows


def test_gather_status_no_ci_workflow(project: ProjectConfig) -> None:
    status = gather_status(project)
    assert status.ci_workflows == []


def test_gather_status_detects_doxyfile(project: ProjectConfig) -> None:
    (project.root / "Doxyfile").write_text("PROJECT_NAME = testmod\n")
    status = gather_status(project)
    assert status.has_doxyfile is True


def test_gather_status_no_doxyfile(project: ProjectConfig) -> None:
    status = gather_status(project)
    assert status.has_doxyfile is False


def test_gather_status_detects_precommit(project: ProjectConfig) -> None:
    (project.root / ".pre-commit-config.yaml").write_text("repos: []\n")
    status = gather_status(project)
    assert status.has_precommit is True


# ---------------------------------------------------------------------------
# CLI / render tests
# ---------------------------------------------------------------------------


def test_status_cli_shows_project_name(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0, result.output
    assert "testmod" in result.output


def test_status_cli_shows_group_name(project: ProjectConfig) -> None:
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0, result.output
    assert "basic" in result.output


def test_status_cli_shows_warning_for_missing_test(project: ProjectConfig) -> None:
    _add_block(project, gen_test=False)
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0, result.output
    assert "MyFilter" in result.output
    assert "no test file" in result.output


def test_status_cli_all_clear_when_no_warnings(project: ProjectConfig) -> None:
    _add_block(project, gen_test=True)
    runner = CliRunner()
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0, result.output
    assert "All blocks have test files" in result.output
