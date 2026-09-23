"""Tests for gr4_modtool templates command group (list / init / check)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.templates import CONTEXT_FREE_TEMPLATES, TEMPLATE_CONTEXT, cmd
from gr4_modtool.templates import builtin_templates_dir


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# templates list
# ---------------------------------------------------------------------------


def test_list_no_overrides(runner: CliRunner, project: object) -> None:
    """All built-ins listed; none shown as overridden."""
    root = project.root  # type: ignore[attr-defined]
    result = runner.invoke(cmd, ["list", "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "block.hpp.j2" in result.output
    assert "overridden" not in result.output


def test_list_with_override(runner: CliRunner, project: object) -> None:
    """A file placed in .gr4modtool/templates/ is shown as overridden."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    (override_dir / "block.hpp.j2").write_text("// custom")

    result = runner.invoke(cmd, ["list", "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "overridden" in result.output


def test_list_outside_project(runner: CliRunner, tmp_path: Path) -> None:
    """Works without a project config — lists built-ins only."""
    result = runner.invoke(cmd, ["list", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "block.hpp.j2" in result.output


# ---------------------------------------------------------------------------
# templates init
# ---------------------------------------------------------------------------


def test_init_copies_template(runner: CliRunner, project: object) -> None:
    """Copied file content matches the built-in."""
    root = project.root  # type: ignore[attr-defined]
    result = runner.invoke(cmd, ["init", "block.hpp.j2", "--project-dir", str(root)])
    assert result.exit_code == 0
    dest = root / ".gr4modtool" / "templates" / "block.hpp.j2"
    builtin = builtin_templates_dir() / "block.hpp.j2"
    assert dest.read_text() == builtin.read_text()


def test_init_creates_dir(runner: CliRunner, project: object) -> None:
    """.gr4modtool/templates/ is created when absent."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    assert not override_dir.exists()
    runner.invoke(cmd, ["init", "block.hpp.j2", "--project-dir", str(root)])
    assert override_dir.is_dir()


def test_init_prints_context_vars(runner: CliRunner, project: object) -> None:
    """Output includes block_name and namespace for block.hpp.j2."""
    root = project.root  # type: ignore[attr-defined]
    result = runner.invoke(cmd, ["init", "block.hpp.j2", "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "block_name" in result.output
    assert "namespace" in result.output


@pytest.mark.skipif(not CONTEXT_FREE_TEMPLATES, reason="no context-free built-in templates")
def test_init_context_free_template(runner: CliRunner, project: object) -> None:
    """A context-free template prints the 'no context variables' message."""
    root = project.root  # type: ignore[attr-defined]
    # Pick the first context-free template deterministically
    template_name = sorted(CONTEXT_FREE_TEMPLATES)[0]
    result = runner.invoke(cmd, ["init", template_name, "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "No context variables" in result.output


def test_init_unknown_template_exits(runner: CliRunner, project: object) -> None:
    """Exits non-zero with a helpful message for unknown template names."""
    root = project.root  # type: ignore[attr-defined]
    result = runner.invoke(cmd, ["init", "nonexistent.j2", "--project-dir", str(root)])
    assert result.exit_code != 0
    assert "Unknown template" in result.output


def test_init_no_overwrite_without_force(runner: CliRunner, project: object) -> None:
    """Exits non-zero; existing override file is unchanged."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    dest = override_dir / "block.hpp.j2"
    dest.write_text("// sentinel")

    result = runner.invoke(cmd, ["init", "block.hpp.j2", "--project-dir", str(root)])
    assert result.exit_code != 0
    assert dest.read_text() == "// sentinel"


def test_init_force_overwrites(runner: CliRunner, project: object) -> None:
    """--force replaces the existing override with built-in content."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    dest = override_dir / "block.hpp.j2"
    dest.write_text("// sentinel")

    result = runner.invoke(cmd, ["init", "--force", "block.hpp.j2", "--project-dir", str(root)])
    assert result.exit_code == 0
    builtin = builtin_templates_dir() / "block.hpp.j2"
    assert dest.read_text() == builtin.read_text()


# ---------------------------------------------------------------------------
# templates check
# ---------------------------------------------------------------------------


def test_check_no_overrides(runner: CliRunner, project: object) -> None:
    """Prints 'No override templates found', exits 0."""
    root = project.root  # type: ignore[attr-defined]
    result = runner.invoke(cmd, ["check", "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "No override templates found" in result.output


def test_check_valid_override(runner: CliRunner, project: object) -> None:
    """Built-in copied as override renders OK, exits 0."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    builtin = builtin_templates_dir() / "gitignore.j2"
    (override_dir / "gitignore.j2").write_text(builtin.read_text())

    result = runner.invoke(cmd, ["check", "--project-dir", str(root)])
    assert result.exit_code == 0
    assert "OK" in result.output
    assert "ERROR" not in result.output


def test_check_invalid_undefined_var(runner: CliRunner, project: object) -> None:
    """Template using an unknown variable → ERROR in output, exits non-zero."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    (override_dir / "gitignore.j2").write_text("{{ totally_undefined_var }}\n")

    result = runner.invoke(cmd, ["check", "--project-dir", str(root)])
    assert result.exit_code != 0
    assert "ERROR" in result.output


def test_check_invalid_syntax(runner: CliRunner, project: object) -> None:
    """Bad Jinja2 syntax → exits non-zero."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    (override_dir / "gitignore.j2").write_text("{% if %}\n")

    result = runner.invoke(cmd, ["check", "--project-dir", str(root)])
    assert result.exit_code != 0
    assert "ERROR" in result.output


def test_check_multiple_some_fail(runner: CliRunner, project: object) -> None:
    """Two overrides, one invalid → only the invalid one reported as ERROR."""
    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    builtin = builtin_templates_dir() / "gitignore.j2"
    (override_dir / "gitignore.j2").write_text(builtin.read_text())
    (override_dir / "clang-format.j2").write_text("{{ totally_undefined }}\n")

    result = runner.invoke(cmd, ["check", "--project-dir", str(root)])
    assert result.exit_code != 0
    assert "clang-format.j2" in result.output
    assert "ERROR" in result.output
    assert result.output.count("OK") >= 1


# ---------------------------------------------------------------------------
# End-to-end: override is actually used by write_block_files / write_test_for_block
# ---------------------------------------------------------------------------


def test_override_used_by_write_block_files(project: object) -> None:
    """Custom block.hpp.j2 with a sentinel comment is picked up by write_block_files."""
    from gr4_modtool.commands.newblock import write_block_files

    root = project.root  # type: ignore[attr-defined]
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    builtin = (builtin_templates_dir() / "block.hpp.j2").read_text()
    (override_dir / "block.hpp.j2").write_text("// CUSTOM_SENTINEL\n" + builtin)

    answers = {
        "block_name": "Foo",
        "group_name": "basic",
        "description": "Test block",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "type_list": "float",
        "processing_style": "processOne",
        "gen_test": False,
        "simd": False,
    }
    write_block_files(project, answers)

    header = project.group_include_dir("basic") / "Foo.hpp"  # type: ignore[attr-defined]
    assert header.exists()
    assert "CUSTOM_SENTINEL" in header.read_text()


def test_override_used_by_add_test(project: object) -> None:
    """Custom qa_block.cpp.j2 with a sentinel is picked up by write_test_for_block."""
    from gr4_modtool.commands.add_test import write_test_for_block
    from gr4_modtool.commands.newblock import write_block_files

    root = project.root  # type: ignore[attr-defined]

    # Write the block header first (needed by write_test_for_block)
    answers = {
        "block_name": "Bar",
        "group_name": "basic",
        "description": "Test block",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "type_list": "float",
        "processing_style": "processOne",
        "gen_test": False,
        "simd": False,
    }
    write_block_files(project, answers)

    # Install custom qa template
    override_dir = root / ".gr4modtool" / "templates"
    override_dir.mkdir(parents=True)
    builtin = (builtin_templates_dir() / "qa_block.cpp.j2").read_text()
    (override_dir / "qa_block.cpp.j2").write_text("// QA_SENTINEL\n" + builtin)

    write_test_for_block(project, "basic", "Bar")

    test_file = project.group_test_dir("basic") / "qa_Bar.cpp"  # type: ignore[attr-defined]
    assert test_file.exists()
    assert "QA_SENTINEL" in test_file.read_text()


# ---------------------------------------------------------------------------
# Safety net: registry coverage
# ---------------------------------------------------------------------------


def test_context_registry_covers_all_builtin_templates() -> None:
    """Every .j2 file in the built-in directory is covered by TEMPLATE_CONTEXT
    or CONTEXT_FREE_TEMPLATES."""
    builtin_names = {p.name for p in builtin_templates_dir().glob("*.j2")}
    registered = set(TEMPLATE_CONTEXT.keys()) | CONTEXT_FREE_TEMPLATES
    missing = builtin_names - registered
    assert not missing, (
        f"Built-in templates not in registry: {sorted(missing)}\n"
        "Add them to TEMPLATE_CONTEXT or CONTEXT_FREE_TEMPLATES in commands/templates.py"
    )
