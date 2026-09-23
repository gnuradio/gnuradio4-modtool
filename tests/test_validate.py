"""Tests for the validate command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.validate import (
    ValidationIssue,
    _check_build,
    _check_headers,
    _check_structure,
    cmd,
    validate_project,
)
from gr4_modtool.project.discovery import ProjectConfig

# ---------------------------------------------------------------------------
# Header templates
# ---------------------------------------------------------------------------

# Minimal well-formed filter block (1 in, 1 out, correct GR_REGISTER_BLOCK counts)
_GOOD_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    GR_MAKE_REFLECTABLE({name}, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

# Header WITHOUT #pragma once
_NO_PRAGMA_HEADER = """\
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    GR_MAKE_REFLECTABLE({name}, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

# Header where struct name is intentionally wrong (struct "OtherName" in file "name.hpp")
_WRONG_STRUCT_NAME_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct OtherName : Block<OtherName<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK(OtherName, 1, 1, [float, double])
    GR_MAKE_REFLECTABLE(OtherName, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

# Header with wrong namespace
_WRONG_NS_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::other::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 1, [float, double])
    GR_MAKE_REFLECTABLE({name}, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::other::basic
"""

# Header claiming 2 inputs but only 1 PortIn<>
_WRONG_IN_COUNT_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 2, 1, [float, double])
    GR_MAKE_REFLECTABLE({name}, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

# Header claiming 2 outputs but only 1 PortOut<>
_WRONG_OUT_COUNT_HEADER = """\
#pragma once
#include <gnuradio-4.0/Block.hpp>
namespace gr::testmod::basic {{
template <typename T>
struct {name} : Block<{name}<T>> {{
    PortIn<T>  in;
    PortOut<T> out;
    GR_REGISTER_BLOCK({name}, 1, 2, [float, double])
    GR_MAKE_REFLECTABLE({name}, in, out)
    [[nodiscard]] T processOne(T x) noexcept {{ return x; }}
}};
}} // namespace gr::testmod::basic
"""

# Header missing GR_MAKE_REFLECTABLE (triggers lint-headers inherited check)
_NO_REFLECTABLE_HEADER = """\
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_header(cfg: ProjectConfig, group: str, name: str, template: str = _GOOD_HEADER) -> Path:
    inc = cfg.group_include_dir(group)
    inc.mkdir(parents=True, exist_ok=True)
    p = inc / f"{name}.hpp"
    p.write_text(template.format(name=name))
    return p


def _write_raw_header(cfg: ProjectConfig, group: str, filename: str, content: str) -> Path:
    """Write a header with an explicit filename (used for H2 mismatch test)."""
    inc = cfg.group_include_dir(group)
    inc.mkdir(parents=True, exist_ok=True)
    p = inc / filename
    p.write_text(content)
    return p


def _write_test_file(cfg: ProjectConfig, group: str, block_name: str) -> Path:
    d = cfg.group_test_dir(group)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"qa_{block_name}.cpp"
    p.write_text("// stub\n")
    return p


def _write_bench_file(cfg: ProjectConfig, group: str, block_name: str) -> Path:
    d = cfg.group_bench_dir(group)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"bench_{block_name}.cpp"
    p.write_text("// stub\n")
    return p


def _write_cmake_test(cfg: ProjectConfig, group: str, *block_names: str) -> Path:
    d = cfg.group_test_dir(group)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "CMakeLists.txt"
    entries = "\n".join(
        f"gr4_modtool_add_ut_test(qa_{b} LIBRARIES gr4_testmod::blocks_basic_headers)"
        for b in block_names
    )
    p.write_text(entries + "\n")
    return p


def _ids(issues: list[ValidationIssue]) -> list[str]:
    return [i.check for i in issues]


def _severities(issues: list[ValidationIssue]) -> list[str]:
    return [i.severity for i in issues]


# ---------------------------------------------------------------------------
# Structure checks (S)
# ---------------------------------------------------------------------------


def test_s1_group_dir_missing(project: ProjectConfig) -> None:
    import shutil

    # Remove the basic group directory
    shutil.rmtree(project.root / "blocks" / "basic")
    issues = _check_structure(project)
    s1 = [i for i in issues if i.check == "S1"]
    assert len(s1) == 1
    assert s1[0].severity == "error"
    assert s1[0].group == "basic"


def test_s1_group_dir_present_clean(project: ProjectConfig) -> None:
    issues = _check_structure(project)
    assert not any(i.check == "S1" for i in issues)


def test_s2_version_mismatch_cmake(project: ProjectConfig) -> None:
    (project.root / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.22)\nproject(testmod LANGUAGES CXX VERSION 9.9.9)\n"
    )
    issues = _check_structure(project)
    s2 = [i for i in issues if i.check == "S2"]
    assert len(s2) == 1
    assert s2[0].severity == "warning"
    assert "9.9.9" in s2[0].detail


def test_s2_version_match_cmake_clean(project: ProjectConfig) -> None:
    (project.root / "CMakeLists.txt").write_text(
        f"project(testmod LANGUAGES CXX VERSION {project.version})\n"
    )
    issues = _check_structure(project)
    assert not any(i.check == "S2" for i in issues)


def test_s2_no_cmake_file_skips(project: ProjectConfig) -> None:
    # No root CMakeLists.txt → no S2 issue
    assert not (project.root / "CMakeLists.txt").exists()
    issues = _check_structure(project)
    assert not any(i.check == "S2" for i in issues)


# ---------------------------------------------------------------------------
# Header checks (H)
# ---------------------------------------------------------------------------


def test_h1_pragma_once_missing(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    issues = _check_headers(project)
    assert any(i.check == "H1" and i.severity == "error" for i in issues)


def test_h1_pragma_once_present_clean(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _GOOD_HEADER)
    issues = _check_headers(project)
    assert not any(i.check == "H1" for i in issues)


def test_h2_struct_name_matches_filename_clean(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _GOOD_HEADER)
    issues = _check_headers(project)
    assert not any(i.check == "H2" for i in issues)


def test_h2_struct_name_differs_from_filename(project: ProjectConfig) -> None:
    # Write a header with struct "OtherName" into file "MyFilter.hpp"
    _write_raw_header(project, "basic", "MyFilter.hpp", _WRONG_STRUCT_NAME_HEADER)
    issues = _check_headers(project)
    h2 = [i for i in issues if i.check == "H2"]
    assert len(h2) == 1
    assert h2[0].severity == "error"
    assert "OtherName" in h2[0].detail


def test_h3_namespace_matches_clean(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _GOOD_HEADER)
    issues = _check_headers(project)
    assert not any(i.check == "H3" for i in issues)


def test_h3_namespace_mismatch(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _WRONG_NS_HEADER)
    issues = _check_headers(project)
    h3 = [i for i in issues if i.check == "H3"]
    assert len(h3) == 1
    assert h3[0].severity == "warning"
    assert "gr::other::basic" in h3[0].detail


def test_h4_in_port_count_match_clean(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _GOOD_HEADER)
    issues = _check_headers(project)
    assert not any(i.check == "H4" for i in issues)


def test_h4_in_port_count_mismatch(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _WRONG_IN_COUNT_HEADER)
    issues = _check_headers(project)
    h4 = [i for i in issues if i.check == "H4"]
    assert len(h4) == 1
    assert h4[0].severity == "error"
    assert "2" in h4[0].detail


def test_h5_out_port_count_mismatch(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _WRONG_OUT_COUNT_HEADER)
    issues = _check_headers(project)
    h5 = [i for i in issues if i.check == "H5"]
    assert len(h5) == 1
    assert h5[0].severity == "error"
    assert "2" in h5[0].detail


def test_h6_duplicate_block_name(project: ProjectConfig) -> None:
    # Two files both define a block named "MyFilter"
    _write_header(project, "basic", "MyFilter", _GOOD_HEADER)
    # Write a second file with the same struct name
    _write_raw_header(
        project,
        "basic",
        "MyFilterCopy.hpp",
        _GOOD_HEADER.format(name="MyFilter"),
    )
    issues = _check_headers(project)
    h6 = [i for i in issues if i.check == "H6"]
    assert len(h6) == 1
    assert h6[0].severity == "error"
    assert "MyFilter" in h6[0].detail


def test_h6_unique_names_clean(project: ProjectConfig) -> None:
    _write_header(project, "basic", "BlockA", _GOOD_HEADER)
    _write_header(project, "basic", "BlockB", _GOOD_HEADER)
    issues = _check_headers(project)
    assert not any(i.check == "H6" for i in issues)


def test_lint_issues_surface_in_validate(project: ProjectConfig) -> None:
    # Header missing GR_MAKE_REFLECTABLE → lint-headers error surfaces in validate
    _write_header(project, "basic", "MyFilter", _NO_REFLECTABLE_HEADER)
    issues = _check_headers(project)
    lint_issues = [i for i in issues if i.check == "lint"]
    assert any("GR_MAKE_REFLECTABLE" in i.detail for i in lint_issues)


def test_h_group_filter(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    _write_header(cfg, "basic", "BlockA", _NO_PRAGMA_HEADER)
    _write_header(cfg, "filter", "BlockB", _GOOD_HEADER)
    issues = _check_headers(cfg, group_filter="filter")
    assert not any(i.check == "H1" for i in issues)


# ---------------------------------------------------------------------------
# Build checks (B)
# ---------------------------------------------------------------------------


def test_b_header_no_test_warning(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter")
    issues = _check_build(project)
    build = [i for i in issues if i.check == "build" and i.severity == "warning"]
    assert any("no test" in i.detail for i in build)


def test_b_test_no_cmake_entry_error(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter")
    _write_test_file(project, "basic", "MyFilter")
    # Provide an existing CMakeLists.txt with no entry for MyFilter
    _write_cmake_test(project, "basic")  # empty — no entries
    issues = _check_build(project)
    assert any("CMake" in i.detail and i.severity == "error" for i in issues)


def test_b_stale_cmake_entry_error(project: ProjectConfig) -> None:
    # CMake entry for "Ghost" but no qa_Ghost.cpp
    _write_cmake_test(project, "basic", "Ghost")
    issues = _check_build(project)
    assert any("CMake" in i.detail and i.severity == "error" for i in issues)


def test_b_clean_project_no_issues(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter")
    _write_test_file(project, "basic", "MyFilter")
    _write_cmake_test(project, "basic", "MyFilter")
    issues = _check_build(project)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_b_group_filter(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    _write_header(cfg, "basic", "BlockA")
    _write_header(cfg, "filter", "BlockB")
    # Only check "filter" — BlockA's missing test should not appear
    issues = _check_build(cfg, group_filter="filter")
    assert all(i.group != "basic" for i in issues)


# ---------------------------------------------------------------------------
# validate_project orchestrator
# ---------------------------------------------------------------------------


def test_skip_structure_omits_s_issues(project: ProjectConfig) -> None:
    import shutil

    shutil.rmtree(project.root / "blocks" / "basic")
    issues = validate_project(project, run_structure=False)
    assert not any(i.category == "structure" for i in issues)


def test_skip_headers_omits_h_issues(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    issues = validate_project(project, run_headers=False)
    assert not any(i.category == "header" for i in issues)


def test_skip_build_omits_b_issues(project: ProjectConfig) -> None:
    _write_header(project, "basic", "MyFilter")
    # Missing test file → build warning
    issues = validate_project(project, run_build=False)
    assert not any(i.category == "build" for i in issues)


def test_all_categories_run_by_default(project: ProjectConfig) -> None:
    import shutil

    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    shutil.rmtree(project.root / "blocks" / "basic")  # creates S1 after rmtree
    (project.root / "CMakeLists.txt").write_text("project(x VERSION 9.9.9)\n")
    issues = validate_project(project)
    cats = {i.category for i in issues}
    assert "structure" in cats


# ---------------------------------------------------------------------------
# --strict mode
# ---------------------------------------------------------------------------


def test_strict_warning_becomes_failure(project: ProjectConfig) -> None:
    (project.root / "CMakeLists.txt").write_text("project(x VERSION 9.9.9)\n")
    issues = validate_project(project)
    warnings = [i for i in issues if i.severity == "warning"]
    assert warnings  # S2 should be present

    def is_failure_strict(i: ValidationIssue) -> bool:
        return i.severity in ("error", "warning")

    assert any(is_failure_strict(i) for i in issues)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_cli_exits_0_clean_project(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0


def test_cli_exits_1_on_error(project: ProjectConfig, runner: CliRunner) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 1


def test_cli_json_flag(project: ProjectConfig, runner: CliRunner) -> None:
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "issues" in parsed
    assert "error_count" in parsed
    assert "warning_count" in parsed
    assert "category_counts" in parsed


def test_cli_json_has_check_id(project: ProjectConfig, runner: CliRunner) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    parsed = json.loads(result.output)
    checks = [i["check"] for i in parsed["issues"]]
    assert "H1" in checks


def test_cli_strict_exits_1_on_warning(project: ProjectConfig, runner: CliRunner) -> None:
    (project.root / "CMakeLists.txt").write_text("project(x VERSION 9.9.9)\n")
    # Without --strict: warning only → exit 0
    result = runner.invoke(cmd, ["--project-dir", str(project.root)])
    assert result.exit_code == 0
    # With --strict: warning → exit 1
    result = runner.invoke(cmd, ["--strict", "--project-dir", str(project.root)])
    assert result.exit_code == 1


def test_cli_skip_structure(project: ProjectConfig, runner: CliRunner) -> None:
    import shutil

    shutil.rmtree(project.root / "blocks" / "basic")
    result = runner.invoke(cmd, ["--skip-structure", "--json", "--project-dir", str(project.root)])
    parsed = json.loads(result.output)
    assert not any(i["category"] == "structure" for i in parsed["issues"])


def test_cli_skip_headers(project: ProjectConfig, runner: CliRunner) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--skip-headers", "--json", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert not any(i["category"] == "header" for i in parsed["issues"])


def test_cli_skip_build(project: ProjectConfig, runner: CliRunner) -> None:
    _write_header(project, "basic", "MyFilter")
    result = runner.invoke(cmd, ["--skip-build", "--json", "--project-dir", str(project.root)])
    parsed = json.loads(result.output)
    assert not any(i["category"] == "build" for i in parsed["issues"])


def test_cli_group_filter(project_two_groups: ProjectConfig, runner: CliRunner) -> None:
    cfg = project_two_groups
    _write_header(cfg, "basic", "BlockA", _NO_PRAGMA_HEADER)
    _write_header(cfg, "filter", "BlockB", _GOOD_HEADER)
    result = runner.invoke(cmd, ["--group", "filter", "--json", "--project-dir", str(cfg.root)])
    parsed = json.loads(result.output)
    header_issues = [i for i in parsed["issues"] if i["category"] == "header"]
    assert not any(i["group"] == "basic" for i in header_issues)


def test_cli_exits_1_on_json_error(project: ProjectConfig, runner: CliRunner) -> None:
    _write_header(project, "basic", "MyFilter", _NO_PRAGMA_HEADER)
    result = runner.invoke(cmd, ["--json", "--project-dir", str(project.root)])
    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert parsed["error_count"] > 0
