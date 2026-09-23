"""E2E: multi-block YAML spec files.

Tests the code path in ``load_spec`` where the YAML is a list of block
mappings rather than a single mapping.  A single ``newblock --spec`` call
should create all listed blocks atomically.
"""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke

_MULTI_SPEC = """\
- block_name: BlockAlpha
  group: basic
  archetype: sync
  type_list: "float"
  gen_test: true

- block_name: BlockBeta
  group: basic
  archetype: sink
  type_list: "float"
  gen_test: true

- block_name: BlockGamma
  group: basic
  archetype: source
  type_list: "float"
  gen_test: true
"""

_MIXED_ARCHETYPE_SPEC = """\
- block_name: MyFilter
  group: basic
  archetype: sync
  type_list: "float"
  gen_test: true

- block_name: MyDecimator
  group: basic
  archetype: decimator
  type_list: "float"
  gen_test: true
"""


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_multi_block_spec_creates_all_headers(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock --spec creates a header for every block in a list spec."""
    spec = tmp_path / "multi.yaml"
    spec.write_text(_MULTI_SPEC)
    invoke(project.root, "newblock", "--spec", str(spec))

    for name in ("BlockAlpha", "BlockBeta", "BlockGamma"):
        assert (project.group_include_dir("basic") / f"{name}.hpp").exists()


def test_multi_block_spec_creates_all_tests(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock --spec creates a qa_*.cpp for every block in a list spec."""
    spec = tmp_path / "multi.yaml"
    spec.write_text(_MULTI_SPEC)
    invoke(project.root, "newblock", "--spec", str(spec))

    for name in ("BlockAlpha", "BlockBeta", "BlockGamma"):
        assert (project.group_test_dir("basic") / f"qa_{name}.cpp").exists()


def test_multi_block_spec_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes with no errors after a multi-block spec is applied."""
    spec = tmp_path / "multi.yaml"
    spec.write_text(_MULTI_SPEC)
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_multi_block_spec_info_shows_all(project: ProjectConfig, tmp_path: Path) -> None:
    """info --json lists every block created by a multi-block spec."""
    spec = tmp_path / "multi.yaml"
    spec.write_text(_MULTI_SPEC)
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "info", "--json")
    data = json.loads(result.output)
    group_data = next(g for g in data["groups"] if g["name"] == "basic")
    names = {b["name"] for b in group_data["blocks"]}
    assert {"BlockAlpha", "BlockBeta", "BlockGamma"}.issubset(names)


def test_multi_block_spec_mixed_archetypes(project: ProjectConfig, tmp_path: Path) -> None:
    """A list spec with mixed archetypes (sync + decimator) passes check."""
    spec = tmp_path / "mixed.yaml"
    spec.write_text(_MIXED_ARCHETYPE_SPEC)
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0
    assert (project.group_include_dir("basic") / "MyFilter.hpp").exists()
    assert (project.group_include_dir("basic") / "MyDecimator.hpp").exists()
