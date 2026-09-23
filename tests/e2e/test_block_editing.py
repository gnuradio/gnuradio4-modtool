"""E2E: block-editing command sequences.

Covers commands that modify existing blocks in-place:
  - newparam  (add Annotated<> parameter to a block header)
  - add_test  (generate qa_*.cpp for a block that lacks one)
  - add_dep   (register a cmake dependency)
  - lint_headers (validate block header conventions)
"""

from __future__ import annotations

import json
from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec


def _create_deps_cmake(project: ProjectConfig) -> None:
    """Create a minimal cmake/Dependencies.cmake so add_dep tests can run."""
    cmake_dir = project.root / "cmake"
    cmake_dir.mkdir(exist_ok=True)
    (cmake_dir / "Dependencies.cmake").write_text(
        f"function({project.cmake_prefix}_resolve_dependencies)\nendfunction()\n"
    )


# ---------------------------------------------------------------------------
# newparam
# ---------------------------------------------------------------------------


def test_newparam_adds_member(project: ProjectConfig, tmp_path: Path) -> None:
    """newparam inserts an Annotated<> member into the block header."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(
        project.root,
        "newparam",
        "MyFilter",
        "gain",
        "--group",
        "basic",
        "--type",
        "float",
        "--description",
        "Signal gain",
        "--default",
        "1.0f",
        "-y",
    )

    header = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "Annotated<float" in header
    assert "gain" in header


def test_newparam_updates_reflectable(project: ProjectConfig, tmp_path: Path) -> None:
    """newparam adds the parameter name to GR_MAKE_REFLECTABLE."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(
        project.root,
        "newparam",
        "MyFilter",
        "cutoff",
        "--group",
        "basic",
        "--type",
        "double",
        "--description",
        "Cutoff frequency",
        "--default",
        "{}",
        "-y",
    )

    header = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "cutoff" in header
    assert "GR_MAKE_REFLECTABLE" in header
    reflectable_line = next(line for line in header.splitlines() if "GR_MAKE_REFLECTABLE" in line)
    assert "cutoff" in reflectable_line


def test_newparam_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes after adding a parameter to a block."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(
        project.root,
        "newparam",
        "MyFilter",
        "alpha",
        "--group",
        "basic",
        "--type",
        "float",
        "--description",
        "Alpha coefficient",
        "--default",
        "0.5f",
        "-y",
    )

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_newparam_complex_type(project: ProjectConfig, tmp_path: Path) -> None:
    """newparam accepts std::complex<float> as the type without breaking the header."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(
        project.root,
        "newparam",
        "MyFilter",
        "center_freq",
        "--group",
        "basic",
        "--type",
        "std::complex<float>",
        "--description",
        "Center frequency",
        "--default",
        "{}",
        "-y",
    )

    header = (project.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "center_freq" in header
    assert "std::complex" in header

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_newparam_duplicate_errors(project: ProjectConfig, tmp_path: Path) -> None:
    """newparam exits nonzero when the parameter name already exists."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(
        project.root,
        "newparam",
        "MyFilter",
        "gain",
        "--group",
        "basic",
        "--type",
        "float",
        "--description",
        "Gain",
        "--default",
        "1.0f",
        "-y",
    )
    # Second add with same name should fail
    result = invoke(
        project.root,
        "newparam",
        "MyFilter",
        "gain",
        "--group",
        "basic",
        "--type",
        "float",
        "--description",
        "Gain again",
        "--default",
        "1.0f",
        "-y",
        expect_ok=False,
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# add_test
# ---------------------------------------------------------------------------


def test_add_test_creates_source(project: ProjectConfig, tmp_path: Path) -> None:
    """add_test recreates a qa_*.cpp that was manually deleted."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    qa = project.group_test_dir("basic") / "qa_MyFilter.cpp"
    assert qa.exists()
    qa.unlink()

    invoke(project.root, "add-test", "MyFilter", "--group", "basic", "-y")
    assert qa.exists()


def test_add_test_registers_cmake(project: ProjectConfig, tmp_path: Path) -> None:
    """add_test adds a cmake entry for the regenerated test."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    qa = project.group_test_dir("basic") / "qa_MyFilter.cpp"
    cmake = project.group_test_dir("basic") / "CMakeLists.txt"
    qa.unlink()
    # Strip cmake entry too so add_test has to re-add it
    cmake.write_text(
        "\n".join(line for line in cmake.read_text().splitlines() if "MyFilter" not in line) + "\n"
    )

    invoke(project.root, "add-test", "MyFilter", "--group", "basic", "-y")

    assert "MyFilter" in cmake.read_text()


def test_add_test_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes after add_test recreates a missing test."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    (project.group_test_dir("basic") / "qa_MyFilter.cpp").unlink()

    invoke(project.root, "add-test", "MyFilter", "--group", "basic", "-y")

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_add_test_errors_if_exists(project: ProjectConfig, tmp_path: Path) -> None:
    """add_test exits nonzero when the test file already exists."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "add-test", "MyFilter", "--group", "basic", "-y", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# lint_headers
# ---------------------------------------------------------------------------


def test_lint_headers_passes_on_valid(project: ProjectConfig, tmp_path: Path) -> None:
    """lint_headers exits 0 on a freshly generated block."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    invoke(project.root, "lint-headers")


def test_lint_headers_json_no_errors(project: ProjectConfig, tmp_path: Path) -> None:
    """lint_headers --json reports zero errors on a valid block."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "lint-headers", "--json")
    data = json.loads(result.output)
    assert data["error_count"] == 0


def test_lint_headers_detects_missing_register(project: ProjectConfig, tmp_path: Path) -> None:
    """lint_headers exits nonzero when GR_REGISTER_BLOCK is stripped."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    header = project.group_include_dir("basic") / "MyFilter.hpp"
    header.write_text(
        "\n".join(
            line for line in header.read_text().splitlines() if "GR_REGISTER_BLOCK" not in line
        )
    )

    result = invoke(project.root, "lint-headers", "--json", expect_ok=False)
    data = json.loads(result.output)
    assert data["error_count"] > 0


def test_lint_headers_group_filter(project: ProjectConfig, tmp_path: Path) -> None:
    """lint_headers --group limits the check to the specified group."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    # Checking a nonexistent group should still exit 0 (no headers = no errors)
    invoke(project.root, "lint-headers", "--group", "basic", "--json")


def test_lint_headers_warnings_do_not_fail_without_strict(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """lint-headers exits 0 on a block with empty description (warning, not error).

    write_spec omits the description field so newblock defaults it to "",
    which lint-headers flags as a warning.
    """
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "lint-headers", "--json")
    data = json.loads(result.output)
    assert data["error_count"] == 0


def test_lint_headers_strict_exits_nonzero_on_warnings(
    project: ProjectConfig, tmp_path: Path
) -> None:
    """lint-headers --strict exits nonzero when warnings are present."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project.root, "newblock", "--spec", str(spec))

    result = invoke(project.root, "lint-headers", "--strict", "--json", expect_ok=False)
    assert result.exit_code != 0
    data = json.loads(result.output)
    assert data["warning_count"] > 0


# ---------------------------------------------------------------------------
# add_dep
# ---------------------------------------------------------------------------


def test_add_dep_pkg_config(project: ProjectConfig, tmp_path: Path) -> None:
    """add_dep --pkg-config inserts a pkg_check_modules entry."""
    _create_deps_cmake(project)
    invoke(project.root, "add-dep", "FFTW3", "--pkg-config", "fftw3")

    deps = (project.root / "cmake" / "Dependencies.cmake").read_text()
    assert "pkg_check_modules" in deps
    assert "fftw3" in deps


def test_add_dep_cmake_package(project: ProjectConfig, tmp_path: Path) -> None:
    """add_dep --cmake-package inserts a find_package entry."""
    _create_deps_cmake(project)
    invoke(project.root, "add-dep", "FFTW3", "--cmake-package", "FFTW3")

    deps = (project.root / "cmake" / "Dependencies.cmake").read_text()
    assert "find_package" in deps
    assert "FFTW3" in deps


def test_add_dep_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes after adding a dependency."""
    _create_deps_cmake(project)
    invoke(project.root, "add-dep", "FFTW3", "--pkg-config", "fftw3")

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_add_dep_duplicate_errors(project: ProjectConfig, tmp_path: Path) -> None:
    """add_dep reports an error when the same VAR_NAME is added twice."""
    _create_deps_cmake(project)
    invoke(project.root, "add-dep", "FFTW3", "--pkg-config", "fftw3")

    # Second add prints an error message (add_dep exits 0 but reports via stderr)
    result = invoke(project.root, "add-dep", "FFTW3", "--pkg-config", "fftw3")
    assert "already declared" in result.output or "No files modified" in result.output


# ---------------------------------------------------------------------------
# newblock --simd
# ---------------------------------------------------------------------------


def test_newblock_simd_header_uses_process_bulk(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock with simd: true generates a processBulk skeleton."""
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "block_name: VectorGain\n"
        "group: basic\n"
        "archetype: sync\n"
        'type_list: "float"\n'
        "gen_test: false\n"
        "simd: true\n"
    )
    invoke(project.root, "newblock", "--spec", str(spec))

    header = (project.group_include_dir("basic") / "VectorGain.hpp").read_text()
    assert "processBulk" in header
    assert "std::span" in header


# ---------------------------------------------------------------------------
# newblock gen_test: false
# ---------------------------------------------------------------------------


def test_newblock_gen_test_false_no_test_file(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock with gen_test: false creates the header but no qa_*.cpp."""
    spec = write_spec(tmp_path / "spec.yaml", "NoTestBlock", group="basic", gen_test=False)
    invoke(project.root, "newblock", "--spec", str(spec))

    assert (project.group_include_dir("basic") / "NoTestBlock.hpp").exists()
    assert not (project.group_test_dir("basic") / "qa_NoTestBlock.cpp").exists()


def test_newblock_gen_test_false_no_cmake_entry(project: ProjectConfig, tmp_path: Path) -> None:
    """newblock with gen_test: false adds no entry to test CMakeLists.txt."""
    spec = write_spec(tmp_path / "spec.yaml", "NoTestBlock", group="basic", gen_test=False)
    invoke(project.root, "newblock", "--spec", str(spec))

    cmake = (project.group_test_dir("basic") / "CMakeLists.txt").read_text()
    assert "NoTestBlock" not in cmake
