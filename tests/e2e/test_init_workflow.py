"""E2E: init command — adopts an existing project tree without .gr4modtool.toml."""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import CONFIG_FILE, load_config

from .conftest import invoke

# ---------------------------------------------------------------------------
# Helpers — build realistic directory trees without using gr4_modtool
# ---------------------------------------------------------------------------

_BLOCK_HPP = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::{namespace} {{
template <typename T>
struct {name} : Block<{name}<T>> {{}};
}} // namespace gr::{namespace}
GR_REGISTER_BLOCK({name}, gr::{namespace}, {name}, [float, double])
"""


def _make_grouped_tree(
    root: Path,
    name: str = "mymod",
    version: str = "0.1.0",
    groups: dict[str, list[str]] | None = None,
) -> Path:
    """Create a standard grouped OOT directory tree without a config file."""
    if groups is None:
        groups = {"basic": ["Alpha", "Beta"]}

    (root / "CMakeLists.txt").write_text(
        f"cmake_minimum_required(VERSION 3.22)\nproject({name} LANGUAGES CXX VERSION {version})\n"
    )

    blocks = root / "blocks"
    blocks.mkdir()
    for group, block_names in groups.items():
        prefix = "gnuradio-4.0"
        inc = blocks / group / "include" / prefix / group
        inc.mkdir(parents=True)
        test = blocks / group / "test"
        test.mkdir(parents=True)
        for bname in block_names:
            (inc / f"{bname}.hpp").write_text(
                _BLOCK_HPP.format(name=bname, namespace=f"{name}::{group}")
            )

    return root


def _make_flat_tree(root: Path, name: str = "flatmod", version: str = "0.1.0") -> Path:
    """Create a flat OOT directory tree without a config file."""
    (root / "CMakeLists.txt").write_text(
        f"cmake_minimum_required(VERSION 3.22)\nproject({name} LANGUAGES CXX VERSION {version})\n"
    )

    inc = root / "blocks" / "include" / "gnuradio-4.0"
    inc.mkdir(parents=True)
    (root / "blocks" / "test").mkdir(parents=True)
    (inc / "Mixer.hpp").write_text(_BLOCK_HPP.format(name="Mixer", namespace=name))
    return root


# ---------------------------------------------------------------------------
# Basic detection
# ---------------------------------------------------------------------------


def test_init_creates_config(tmp_path: Path) -> None:
    """init writes .gr4modtool.toml into the project root."""
    _make_grouped_tree(tmp_path)
    invoke(tmp_path, "init", "--yes")

    assert (tmp_path / CONFIG_FILE).exists()


def test_init_detects_project_name(tmp_path: Path) -> None:
    """init reads the project name from CMakeLists.txt."""
    _make_grouped_tree(tmp_path, name="myfilters")
    invoke(tmp_path, "init", "--yes")

    cfg = load_config(tmp_path)
    assert cfg.name == "myfilters"


def test_init_detects_version(tmp_path: Path) -> None:
    """init reads the version from CMakeLists.txt."""
    _make_grouped_tree(tmp_path, version="1.2.3")
    invoke(tmp_path, "init", "--yes")

    cfg = load_config(tmp_path)
    assert cfg.version == "1.2.3"


def test_init_detects_all_groups(tmp_path: Path) -> None:
    """init discovers all group directories in the tree."""
    _make_grouped_tree(tmp_path, groups={"basic": ["A"], "dsp": ["B"], "channel": ["C"]})
    invoke(tmp_path, "init", "--yes")

    cfg = load_config(tmp_path)
    assert set(cfg.groups.keys()) == {"basic", "dsp", "channel"}


def test_init_followed_by_check_clean(tmp_path: Path) -> None:
    """After init the project passes check."""
    _make_grouped_tree(tmp_path, groups={"basic": ["MyFilter"]})

    # Provide minimal test stubs so check finds no errors
    test_dir = tmp_path / "blocks" / "basic" / "test"
    (test_dir / "CMakeLists.txt").write_text(
        "gr4_modtool_add_ut_test(qa_MyFilter SOURCES qa_MyFilter.cpp\n"
        "  LINK_LIBRARIES gr4_testmod::blocks_basic_headers)\n"
    )
    (test_dir / "qa_MyFilter.cpp").write_text("int main() { return 0; }\n")

    invoke(tmp_path, "init", "--yes")

    result = invoke(tmp_path, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


# ---------------------------------------------------------------------------
# Flat detection
# ---------------------------------------------------------------------------


def test_init_detects_flat_layout(tmp_path: Path) -> None:
    """init on a flat tree registers no groups (flat structure has no group dirs)."""
    _make_flat_tree(tmp_path)
    invoke(tmp_path, "init", "--yes")

    cfg = load_config(tmp_path)
    assert len(cfg.groups) == 0


def test_init_flat_info_json_group_empty(tmp_path: Path) -> None:
    """After init on a flat tree, info --json has an empty groups list."""
    _make_flat_tree(tmp_path)
    invoke(tmp_path, "init", "--yes")

    result = invoke(tmp_path, "info", "--json")
    data = json.loads(result.output)
    assert data["groups"] == []


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def test_init_dry_run_writes_nothing(tmp_path: Path) -> None:
    """init --dry-run exits 0 but does not create .gr4modtool.toml."""
    _make_grouped_tree(tmp_path)
    invoke(tmp_path, "init", "--dry-run")

    assert not (tmp_path / CONFIG_FILE).exists()


def test_init_force_overwrites_existing(tmp_path: Path) -> None:
    """init --force replaces an existing config."""
    _make_grouped_tree(tmp_path, name="original")
    invoke(tmp_path, "init", "--yes")

    # Manually change the project name in the CMakeLists.txt
    cmake = tmp_path / "CMakeLists.txt"
    cmake.write_text(cmake.read_text().replace("original", "replaced"))

    invoke(tmp_path, "init", "--force", "--yes")
    assert load_config(tmp_path).name == "replaced"
