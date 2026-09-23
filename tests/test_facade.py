"""Tests for gr4_modtool.facade.Project — the object-oriented API layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.api import ARCHETYPES, Project
from gr4_modtool.project.discovery import ProjectConfig


def _block_entry(block_name: str, group: str = "basic") -> dict:
    arch = ARCHETYPES["sync"]
    return {
        "group_name": group,
        "block_name": block_name,
        "description": f"Test {block_name}",
        "template_params": ["T"],
        "in_ports": arch["in_ports"],
        "out_ports": arch["out_ports"],
        "processing_style": arch["processing_style"],
        "type_list": "float, double",
        "gen_test": True,
        "simd": False,
    }


@pytest.fixture()
def proj(project: ProjectConfig) -> Project:
    """Project facade over the shared single-group fixture."""
    return Project(project)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_load_walks_up_from_path(project: ProjectConfig) -> None:
    loaded = Project.load(project.root)
    assert loaded.name == project.name
    assert loaded.root == project.root


def test_load_missing_project_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Project.load(tmp_path)


def test_create_scaffolds_project(tmp_path: Path) -> None:
    created = Project.create(tmp_path / "gr4_demo", "gr4_demo", first_group="basic")
    assert (created.root / ".gr4modtool.toml").exists()
    assert (created.root / "CMakeLists.txt").exists()
    assert created.cfg.groups == {"basic": "blocks/basic"}
    assert not created.cfg.flat


def test_create_flat_project(tmp_path: Path) -> None:
    created = Project.create(tmp_path / "gr4_flat", "gr4_flat")
    assert created.cfg.flat


def test_repr_names_project(proj: Project) -> None:
    assert "Project(" in repr(proj)
    assert proj.name in repr(proj)


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def test_groups_discovers_fixture_group(proj: Project) -> None:
    names = [g.name for g in proj.groups()]
    assert names == ["basic"]


def test_inventory_and_status(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    inv = proj.inventory()
    assert inv["project"]["name"] == proj.name
    assert inv["groups"][0]["blocks"][0]["name"] == "Alpha"

    status = proj.status()
    assert status.groups[0].block_count == 1


def test_audit_and_validate_clean_block(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    assert proj.audit() == []
    errors = [i for i in proj.validate() if i.severity == "error"]
    assert errors == []


def test_lint_headers_returns_list(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    assert isinstance(proj.lint_headers(), list)


def test_catalog_lists_block(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    assert "Alpha" in proj.catalog()


def test_export_spec_writes_yaml(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    written = proj.export_spec(output="project")
    assert written and all(p.exists() for p in written)


# ---------------------------------------------------------------------------
# Scaffolding and block lifecycle
# ---------------------------------------------------------------------------


def test_new_group_registers_and_saves(proj: Project) -> None:
    proj.new_group("filters")
    assert "filters" in proj.cfg.groups
    reloaded = Project.load(proj.root)
    assert "filters" in reloaded.cfg.groups


def test_new_group_duplicate_raises(proj: Project) -> None:
    with pytest.raises(ValueError, match="already exists"):
        proj.new_group("basic")


def test_new_block_writes_header_and_test(proj: Project) -> None:
    written = proj.new_block(**_block_entry("Alpha"))
    header = proj.cfg.group_include_dir("basic") / "Alpha.hpp"
    assert header in written
    assert header.exists()


def test_new_block_invalid_entry_raises(proj: Project) -> None:
    entry = _block_entry("badName")  # not CamelCase
    with pytest.raises(ValueError):
        proj.new_block(**entry)


def test_new_block_keyword_form_defaults(proj: Project) -> None:
    written = proj.new_block(block_name="Alpha", group_name="basic")
    header = proj.cfg.group_include_dir("basic") / "Alpha.hpp"
    assert header in written
    text = header.read_text()
    assert "struct Alpha" in text
    assert "processOne" in text  # sync archetype default
    assert (proj.cfg.group_test_dir("basic") / "qa_Alpha.cpp").exists()  # gen_test default


def test_new_block_keyword_form_archetype(proj: Project) -> None:
    proj.new_block(block_name="Src", group_name="basic", archetype="source", gen_test=False)
    text = (proj.cfg.group_include_dir("basic") / "Src.hpp").read_text()
    assert "processBulk" in text
    assert not (proj.cfg.group_test_dir("basic") / "qa_Src.cpp").exists()


def test_new_block_keyword_form_explicit_ports_win(proj: Project) -> None:
    proj.new_block(
        block_name="Dual",
        group_name="basic",
        out_ports=[{"name": "out0", "type": "T"}, {"name": "out1", "type": "T"}],
        gen_test=False,
    )
    text = (proj.cfg.group_include_dir("basic") / "Dual.hpp").read_text()
    assert "out0" in text
    assert "out1" in text


def test_new_block_unknown_archetype_raises(proj: Project) -> None:
    with pytest.raises(ValueError, match="Unknown archetype"):
        proj.new_block(block_name="Alpha", group_name="basic", archetype="nope")


def test_new_block_keyword_form_missing_group_raises(proj: Project) -> None:
    with pytest.raises(ValueError, match="group is required"):
        proj.new_block(block_name="Alpha")


def test_copy_move_rename_remove_roundtrip(proj: Project) -> None:
    proj.new_group("filters")
    proj.new_block(**_block_entry("Alpha"))

    proj.copy_block("basic", "Alpha", "Beta")
    assert (proj.cfg.group_include_dir("basic") / "Beta.hpp").exists()

    proj.move_block("basic", "Beta", "filters")
    assert (proj.cfg.group_include_dir("filters") / "Beta.hpp").exists()

    proj.rename_block("filters", "Beta", "Gamma")
    assert (proj.cfg.group_include_dir("filters") / "Gamma.hpp").exists()

    removed = proj.remove_block("filters", "Gamma")
    assert removed
    assert not (proj.cfg.group_include_dir("filters") / "Gamma.hpp").exists()


def test_remove_block_unknown_raises(proj: Project) -> None:
    with pytest.raises(ValueError, match="not found"):
        proj.remove_block("basic", "Nope")


def test_add_test_and_new_bench(proj: Project) -> None:
    entry = _block_entry("Alpha")
    entry["gen_test"] = False
    proj.new_block(**entry)

    test_paths = proj.add_test("basic", "Alpha")
    assert (proj.cfg.group_test_dir("basic") / "qa_Alpha.cpp") in test_paths

    bench_paths = proj.new_bench("basic", "Alpha")
    assert (proj.cfg.group_bench_dir("basic") / "bench_Alpha.cpp") in bench_paths


def test_add_param_updates_header(proj: Project) -> None:
    proj.new_block(**_block_entry("Alpha"))
    proj.add_param("basic", "Alpha", "gain", "float", "Gain factor", "1.0f")
    header = proj.cfg.group_include_dir("basic") / "Alpha.hpp"
    assert "gain" in header.read_text()


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_sync_plan_and_apply(proj: Project) -> None:
    entry = _block_entry("Alpha")
    entry["gen_test"] = False
    proj.new_block(**entry)

    actions = proj.sync_plan()
    assert any(a.action == "generate_test" for a in actions)

    proj.sync_apply(actions)
    assert (proj.cfg.group_test_dir("basic") / "qa_Alpha.cpp").exists()
    assert proj.sync_plan() == []


# ---------------------------------------------------------------------------
# Tooling writers
# ---------------------------------------------------------------------------


def test_tooling_writers_create_files(proj: Project) -> None:
    assert all(p.exists() for p in proj.write_devcontainer())
    assert all(p.exists() for p in proj.write_vscode())
    assert all(p.exists() for p in proj.write_precommit())
    assert all(p.exists() for p in proj.write_clang_config())
    assert all(p.exists() for p in proj.write_cmake_presets())
    assert all(p.exists() for p in proj.write_doxyfile())


def test_write_ci_selected_workflows(proj: Project) -> None:
    written = proj.write_ci(coverage=True, release=True)
    names = {p.name for p in written}
    assert len(written) == 2
    assert all(p.parent == proj.root / ".github" / "workflows" for p in written)
    assert names == {"coverage.yml", "release.yml"} or len(names) == 2


def test_write_ci_none_selected_is_empty(proj: Project) -> None:
    assert proj.write_ci() == []


# ---------------------------------------------------------------------------
# Dependencies, templates, versioning
# ---------------------------------------------------------------------------


def test_add_dependency_requires_a_source(proj: Project) -> None:
    with pytest.raises(ValueError):
        proj.add_dependency("FFTW3")


def test_list_and_override_templates(proj: Project) -> None:
    statuses = proj.list_templates()
    assert statuses.get("block.hpp.j2") == "built-in"

    dest = proj.init_template_override("block.hpp.j2")
    assert dest.exists()
    assert proj.list_templates()["block.hpp.j2"] == "overridden"

    with pytest.raises(FileExistsError):
        proj.init_template_override("block.hpp.j2")

    assert proj.check_templates() == {"block.hpp.j2": None}


def test_init_template_override_unknown_raises(proj: Project) -> None:
    with pytest.raises(ValueError, match="Unknown template"):
        proj.init_template_override("nope.j2")


def test_check_templates_reports_broken_override(proj: Project) -> None:
    dest = proj.init_template_override("block.hpp.j2")
    dest.write_text("{% if unclosed %}")
    results = proj.check_templates()
    assert results["block.hpp.j2"] is not None


def test_bump_version_updates_config(proj: Project) -> None:
    proj.bump_version("2.0.0")
    assert proj.version == "2.0.0"
    assert Project.load(proj.root).version == "2.0.0"
