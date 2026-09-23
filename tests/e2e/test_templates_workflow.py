"""E2E: templates subcommand workflow.

Tests the three subcommands:
  - templates list   (show built-in templates and any overrides)
  - templates init   (copy a built-in template to the project-local override dir)
  - templates check  (render all overrides to catch Jinja2 errors early)

The templates group command has --project-dir on each subcommand (not on the
group), so these tests call CliRunner directly rather than via the shared
invoke() helper.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gr4_modtool.cli import cli
from gr4_modtool.project.discovery import ProjectConfig


def _templates(root: Path, subcommand: str, *args: str, expect_ok: bool = True):
    runner = CliRunner()
    full_args = ["templates", subcommand, "--project-dir", str(root), *args]
    result = runner.invoke(cli, full_args)
    if expect_ok:
        assert result.exit_code == 0, (
            f"templates {subcommand} {list(args)!r} exited {result.exit_code}:\n{result.output}"
        )
    return result


# ---------------------------------------------------------------------------
# templates list
# ---------------------------------------------------------------------------


def test_templates_list_exits_ok(project: ProjectConfig) -> None:
    """templates list exits 0."""
    _templates(project.root, "list")


def test_templates_list_shows_known_template(project: ProjectConfig) -> None:
    """templates list output includes at least one known built-in template name."""
    result = _templates(project.root, "list")
    assert "block.hpp.j2" in result.output


def test_templates_list_no_overrides_by_default(project: ProjectConfig) -> None:
    """A fresh project has no overrides; list shows only built-in status."""
    result = _templates(project.root, "list")
    assert "overridden" not in result.output
    assert "custom" not in result.output


# ---------------------------------------------------------------------------
# templates init
# ---------------------------------------------------------------------------


def test_templates_init_copies_file(project: ProjectConfig) -> None:
    """templates init copies a built-in template into .gr4modtool/templates/."""
    _templates(project.root, "init", "block.hpp.j2")

    override = project.root / ".gr4modtool" / "templates" / "block.hpp.j2"
    assert override.exists()


def test_templates_init_idempotent_with_force(project: ProjectConfig) -> None:
    """templates init --force overwrites an existing override without error."""
    _templates(project.root, "init", "block.hpp.j2")
    _templates(project.root, "init", "block.hpp.j2", "--force")

    override = project.root / ".gr4modtool" / "templates" / "block.hpp.j2"
    assert override.exists()


def test_templates_init_errors_on_duplicate_without_force(project: ProjectConfig) -> None:
    """templates init exits nonzero when override exists and --force is not given."""
    _templates(project.root, "init", "block.hpp.j2")
    result = _templates(project.root, "init", "block.hpp.j2", expect_ok=False)
    assert result.exit_code != 0


def test_templates_init_errors_on_unknown_template(project: ProjectConfig) -> None:
    """templates init exits nonzero for a template name that does not exist."""
    result = _templates(project.root, "init", "nonexistent_template.j2", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# templates check
# ---------------------------------------------------------------------------


def test_templates_check_no_overrides(project: ProjectConfig) -> None:
    """templates check exits 0 when there are no override templates."""
    _templates(project.root, "check")


def test_templates_check_passes_on_unmodified_override(project: ProjectConfig) -> None:
    """templates check exits 0 after init (unmodified built-in copy is valid)."""
    _templates(project.root, "init", "block.hpp.j2")
    _templates(project.root, "check")


def test_templates_check_fails_on_broken_jinja(project: ProjectConfig) -> None:
    """templates check exits nonzero when an override has a Jinja2 syntax error."""
    _templates(project.root, "init", "block.hpp.j2")

    override = project.root / ".gr4modtool" / "templates" / "block.hpp.j2"
    override.write_text("{{ unclosed_tag\n")

    result = _templates(project.root, "check", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# override used by newblock
# ---------------------------------------------------------------------------


def test_templates_override_content_used_by_newblock(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """A sentinel comment in an overridden template appears in the generated file."""
    from .conftest import invoke, write_spec

    _templates(project.root, "init", "block.hpp.j2")

    override = project.root / ".gr4modtool" / "templates" / "block.hpp.j2"
    original = override.read_text()
    override.write_text("// SENTINEL_E2E_TEST\n" + original)

    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    header = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "SENTINEL_E2E_TEST" in header
