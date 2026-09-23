"""E2E: quality-tooling command sequences (ci, format, version-bump, etc.)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, skip_no_clang_format, write_spec

# ---------------------------------------------------------------------------
# ci — GitHub Actions workflow generation
# ---------------------------------------------------------------------------


def test_ci_writes_workflow_file(project: ProjectConfig) -> None:
    """ci --coverage creates at least one .yml workflow file."""
    invoke(project.root, "ci", "--coverage")
    workflows = list((project.root / ".github" / "workflows").glob("*.yml"))
    assert workflows, "ci wrote no workflow files"


def test_ci_workflow_is_valid_yaml(project: ProjectConfig) -> None:
    """Every workflow file written by ci parses as valid YAML."""
    import yaml

    invoke(project.root, "ci")
    for yml in (project.root / ".github" / "workflows").glob("*.yml"):
        data = yaml.safe_load(yml.read_text())
        assert isinstance(data, dict), f"{yml.name} is not a YAML mapping"


def test_ci_coverage_flag_adds_workflow(project: ProjectConfig) -> None:
    """ci --coverage writes a coverage-specific workflow."""
    invoke(project.root, "ci", "--coverage")
    files = [f.name for f in (project.root / ".github" / "workflows").glob("*.yml")]
    assert any("coverage" in f for f in files)


def test_ci_matrix_flag_adds_workflow(project: ProjectConfig) -> None:
    """ci --matrix writes a matrix-build workflow."""
    invoke(project.root, "ci", "--matrix")
    files = [f.name for f in (project.root / ".github" / "workflows").glob("*.yml")]
    assert any("matrix" in f for f in files)


# ---------------------------------------------------------------------------
# presets — CMakePresets.json
# ---------------------------------------------------------------------------


def test_presets_writes_cmake_presets(project: ProjectConfig) -> None:
    """presets --presets-only creates CMakePresets.json."""
    invoke(project.root, "presets", "--presets-only")
    assert (project.root / "CMakePresets.json").exists()


def test_presets_cmake_presets_is_valid_json(project: ProjectConfig) -> None:
    """CMakePresets.json is valid JSON after presets --presets-only."""
    invoke(project.root, "presets", "--presets-only")
    data = json.loads((project.root / "CMakePresets.json").read_text())
    assert "configurePresets" in data or "version" in data


# ---------------------------------------------------------------------------
# pre-commit
# ---------------------------------------------------------------------------


def test_precommit_writes_config(project: ProjectConfig) -> None:
    """pre-commit creates .pre-commit-config.yaml."""
    invoke(project.root, "pre-commit", "-y")
    assert (project.root / ".pre-commit-config.yaml").exists()


def test_precommit_config_is_valid_yaml(project: ProjectConfig) -> None:
    """pre-commit config parses as valid YAML."""
    import yaml

    invoke(project.root, "pre-commit", "-y")
    data = yaml.safe_load((project.root / ".pre-commit-config.yaml").read_text())
    assert isinstance(data, dict)
    assert "repos" in data


# ---------------------------------------------------------------------------
# vscode
# ---------------------------------------------------------------------------


def test_vscode_writes_settings(project: ProjectConfig) -> None:
    """vscode creates .vscode/settings.json."""
    invoke(project.root, "vscode", "-y")
    assert (project.root / ".vscode" / "settings.json").exists()


def test_vscode_settings_is_valid_json(project: ProjectConfig) -> None:
    """vscode settings.json is valid JSON."""
    invoke(project.root, "vscode", "-y")
    data = json.loads((project.root / ".vscode" / "settings.json").read_text())
    assert isinstance(data, dict)


def test_vscode_idempotent(project: ProjectConfig) -> None:
    """Calling vscode twice does not corrupt settings.json."""
    invoke(project.root, "vscode", "-y")
    invoke(project.root, "vscode", "-y")
    data = json.loads((project.root / ".vscode" / "settings.json").read_text())
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# format
# ---------------------------------------------------------------------------


def _run_cli_subprocess(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run gr4_modtool as a real subprocess (needed for commands that inherit stdout)."""
    binary = shutil.which("gr4_modtool") or str(Path(sys.executable).parent / "gr4_modtool")
    cmd = [binary, args[0], "--project-dir", str(root), *args[1:]]
    return subprocess.run(cmd, capture_output=True, text=True)


@skip_no_clang_format
def test_format_runs_on_project(project: ProjectConfig, tmp_path: Path) -> None:
    """format exits 0 on a project with generated headers."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))
    result = _run_cli_subprocess(project.root, "format")
    assert result.returncode == 0, f"format failed:\n{result.stdout}\n{result.stderr}"


@skip_no_clang_format
def test_format_then_check_passes(project: ProjectConfig, tmp_path: Path) -> None:
    """format --check exits 0 after format has been run on the project."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))
    _run_cli_subprocess(project.root, "format")
    result = _run_cli_subprocess(project.root, "format", "--check")
    assert result.returncode == 0, f"format --check failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# version-bump
# ---------------------------------------------------------------------------


def test_version_bump_patch_increments_version(project: ProjectConfig) -> None:
    """version-bump --patch updates the version in .gr4modtool.toml."""
    from gr4_modtool.project.discovery import load_config

    original = load_config(project.root).version
    major, minor, patch = (int(x) for x in original.split("."))

    invoke(project.root, "version-bump", "--patch", "-y")

    new = load_config(project.root).version
    assert new == f"{major}.{minor}.{patch + 1}"


def test_version_bump_minor_resets_patch(project: ProjectConfig) -> None:
    """version-bump --minor bumps minor and resets patch to 0."""
    from gr4_modtool.project.discovery import load_config

    original = load_config(project.root).version
    major, minor, _ = (int(x) for x in original.split("."))

    invoke(project.root, "version-bump", "--minor", "-y")

    assert load_config(project.root).version == f"{major}.{minor + 1}.0"


def test_version_bump_set_exact(project: ProjectConfig) -> None:
    """version-bump --set writes the exact version string."""
    from gr4_modtool.project.discovery import load_config

    invoke(project.root, "version-bump", "--set", "9.8.7", "-y")
    assert load_config(project.root).version == "9.8.7"


def test_version_bump_dry_run_no_change(project: ProjectConfig) -> None:
    """version-bump --dry-run does not modify the config."""
    from gr4_modtool.project.discovery import load_config

    original = load_config(project.root).version
    invoke(project.root, "version-bump", "--patch", "--dry-run")
    assert load_config(project.root).version == original


def test_version_bump_updates_cmake(project: ProjectConfig) -> None:
    """version-bump also updates the version in CMakeLists.txt when present."""
    cmake = project.root / "CMakeLists.txt"
    cmake.write_text("cmake_minimum_required(VERSION 3.22)\nproject(testmod VERSION 0.1.0)\n")

    invoke(project.root, "version-bump", "--patch", "-y")

    assert "0.1.1" in cmake.read_text()
    assert "0.1.0" not in cmake.read_text()


def test_ci_release_creates_workflow(project: ProjectConfig) -> None:
    """ci --release writes a release workflow file."""
    invoke(project.root, "ci", "--release")
    files = [f.name for f in (project.root / ".github" / "workflows").glob("*.yml")]
    assert any("release" in f for f in files)


def test_ci_no_flags_exits_ok(project: ProjectConfig) -> None:
    """ci with no flags exits 0 and prints a hint about available flags."""
    result = invoke(project.root, "ci")
    assert (
        "--coverage" in result.output or "--matrix" in result.output or "Specify" in result.output
    )


def test_presets_init_creates_ci_workflow(project: ProjectConfig) -> None:
    """presets --init writes CMakePresets.json and a sanitizers workflow."""
    invoke(project.root, "presets", "--init")
    assert (project.root / "CMakePresets.json").exists()
    workflow_files = [f.name for f in (project.root / ".github" / "workflows").glob("*.yml")]
    assert any("sanitizer" in f for f in workflow_files)


def test_docs_catalog_writes_to_file(project: ProjectConfig, tmp_path: Path) -> None:
    """docs --catalog --output <file> writes the Markdown catalog to a file."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    out_file = tmp_path / "catalog.md"
    invoke(project.root, "docs", "--catalog", "--output", str(out_file))

    assert out_file.exists()
    assert "|" in out_file.read_text()


def test_version_bump_major_resets_minor_and_patch(project: ProjectConfig) -> None:
    """version-bump --major increments major and resets minor and patch to 0."""
    from gr4_modtool.project.discovery import load_config

    original = load_config(project.root).version
    major, _, _ = (int(x) for x in original.split("."))

    invoke(project.root, "version-bump", "--major", "-y")

    assert load_config(project.root).version == f"{major + 1}.0.0"


# ---------------------------------------------------------------------------
# completion
# ---------------------------------------------------------------------------


def test_completion_bash_emits_snippet(project: ProjectConfig) -> None:
    """completion --shell bash exits 0 and prints a non-empty eval snippet."""
    from click.testing import CliRunner

    from gr4_modtool.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "--shell", "bash"])
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------


def test_docs_catalog_output_contains_table(project: ProjectConfig, tmp_path: Path) -> None:
    """docs --catalog prints a Markdown table."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "docs", "--catalog")
    assert "|" in result.output  # Markdown table delimiter


def test_docs_doxyfile_is_created(project: ProjectConfig) -> None:
    """docs (no flags) creates a Doxyfile in the project root."""
    invoke(project.root, "docs")
    assert (project.root / "Doxyfile").exists()


# ---------------------------------------------------------------------------
# devcontainer
# ---------------------------------------------------------------------------


def test_devcontainer_creates_dockerfile(project: ProjectConfig) -> None:
    """devcontainer creates .devcontainer/Dockerfile."""
    invoke(project.root, "devcontainer", "-y")
    assert (project.root / ".devcontainer" / "Dockerfile").exists()


def test_devcontainer_creates_json(project: ProjectConfig) -> None:
    """devcontainer creates .devcontainer/devcontainer.json."""
    invoke(project.root, "devcontainer", "-y")
    data = json.loads((project.root / ".devcontainer" / "devcontainer.json").read_text())
    assert isinstance(data, dict)
