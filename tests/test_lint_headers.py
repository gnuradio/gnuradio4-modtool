"""Tests for lint-headers command."""

from __future__ import annotations

from pathlib import Path

from gr4_modtool.commands.lint_headers import LintIssue, lint_header, lint_headers
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_answers(block_name: str = "MyFilter", group: str = "basic") -> dict:
    return {
        "block_name": block_name,
        "group_name": group,
        "description": "A test filter block",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": False,
        "simd": False,
    }


def _severities(issues: list[LintIssue], sev: str) -> list[str]:
    return [i.issue for i in issues if i.severity == sev]


# ---------------------------------------------------------------------------
# Clean block → no issues
# ---------------------------------------------------------------------------


def test_lint_clean_block_no_issues(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    issues = lint_header(hpp, "basic")
    assert issues == []


# ---------------------------------------------------------------------------
# Individual checks — each test plants a deliberately broken header
# ---------------------------------------------------------------------------


def test_lint_missing_register_block(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    # Remove GR_REGISTER_BLOCK line
    text = hpp.read_text()
    hpp.write_text("\n".join(line for line in text.splitlines() if "GR_REGISTER_BLOCK" not in line))
    issues = lint_header(hpp, "basic")
    errors = _severities(issues, "error")
    assert any("GR_REGISTER_BLOCK" in e for e in errors)


def test_lint_empty_type_list(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    text = hpp.read_text()
    # Replace the type list with empty brackets
    hpp.write_text(__import__("re").sub(r"\[\s*float,\s*double\s*\]", "[]", text))
    issues = lint_header(hpp, "basic")
    warnings = _severities(issues, "warning")
    assert any("empty type list" in w for w in warnings)


def test_lint_missing_description(project: ProjectConfig) -> None:
    answers = _valid_answers()
    answers["description"] = ""
    write_block_files(project, answers)
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    issues = lint_header(hpp, "basic")
    warnings = _severities(issues, "warning")
    assert any("description" in w for w in warnings)


def test_lint_missing_reflectable(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    text = hpp.read_text()
    hpp.write_text(
        "\n".join(line for line in text.splitlines() if "GR_MAKE_REFLECTABLE" not in line)
    )
    issues = lint_header(hpp, "basic")
    errors = _severities(issues, "error")
    assert any("GR_MAKE_REFLECTABLE" in e for e in errors)


def test_lint_port_missing_from_reflectable(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    text = hpp.read_text()
    # Replace reflectable to omit the 'out' port
    hpp.write_text(
        __import__("re").sub(
            r"GR_MAKE_REFLECTABLE\([^)]+\)",
            "GR_MAKE_REFLECTABLE(MyFilter, in)",
            text,
        )
    )
    issues = lint_header(hpp, "basic")
    errors = _severities(issues, "error")
    assert any("'out'" in e and "absent from GR_MAKE_REFLECTABLE" in e for e in errors)


def test_lint_unknown_name_in_reflectable(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    text = hpp.read_text()
    # Add a phantom name to the reflectable macro
    hpp.write_text(
        __import__("re").sub(
            r"GR_MAKE_REFLECTABLE\([^)]+\)",
            "GR_MAKE_REFLECTABLE(MyFilter, in, out, phantom_member)",
            text,
        )
    )
    issues = lint_header(hpp, "basic")
    warnings = _severities(issues, "warning")
    assert any("'phantom_member'" in w and "not declared" in w for w in warnings)


def test_lint_param_missing_doc(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    hpp = project.group_include_dir("basic") / "MyFilter.hpp"
    text = hpp.read_text()
    # Insert an Annotated<> param without Doc<> before the GR_MAKE_REFLECTABLE line
    insertion = "    Annotated<float> gain{1.0f};\n"
    hpp.write_text(
        text.replace(
            "    GR_MAKE_REFLECTABLE",
            insertion + "    GR_MAKE_REFLECTABLE",
        )
    )
    issues = lint_header(hpp, "basic")
    warnings = _severities(issues, "warning")
    assert any("'gain'" in w and "Doc<>" in w for w in warnings)


def test_lint_skips_non_block_headers(tmp_path: Path) -> None:
    hpp = tmp_path / "utils.hpp"
    hpp.write_text("#pragma once\n// utility header\n")
    issues = lint_header(hpp, "basic")
    assert issues == []


# ---------------------------------------------------------------------------
# lint_headers — project-level orchestration
# ---------------------------------------------------------------------------


def test_lint_headers_clean_project(project: ProjectConfig) -> None:
    write_block_files(project, _valid_answers())
    issues = lint_headers(project)
    assert issues == []


def test_lint_headers_group_filter(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _valid_answers("Alpha", "basic"))
    # Plant a broken header only in the filter group
    write_block_files(cfg, _valid_answers("Beta", "filter"))
    hpp = cfg.group_include_dir("filter") / "Beta.hpp"
    text = hpp.read_text()
    hpp.write_text(
        "\n".join(line for line in text.splitlines() if "GR_MAKE_REFLECTABLE" not in line)
    )

    # With group filter — only filter group issues
    issues = lint_headers(cfg, groups=["filter"])
    assert all(i.group == "filter" for i in issues)
    assert any("GR_MAKE_REFLECTABLE" in i.issue for i in issues)

    # Without filter — same issues still present in filter group
    all_issues = lint_headers(cfg)
    filter_issues = [i for i in all_issues if i.group == "filter"]
    assert any("GR_MAKE_REFLECTABLE" in i.issue for i in filter_issues)
    # basic group is clean
    basic_issues = [i for i in all_issues if i.group == "basic"]
    assert basic_issues == []


def test_lint_headers_returns_correct_group(project: ProjectConfig) -> None:
    answers = _valid_answers()
    answers["description"] = ""  # trigger a warning
    write_block_files(project, answers)
    issues = lint_headers(project)
    assert all(i.group == "basic" for i in issues)
    assert all(i.block == "MyFilter" for i in issues)
