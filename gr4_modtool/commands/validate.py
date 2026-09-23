"""validate command — comprehensive project validation across structure, headers, and build."""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


@dataclass
class ValidationIssue:
    category: str  # "structure" | "header" | "build"
    group: str  # "" for project-level issues
    subject: str  # block name, filename, or ""
    check: str  # stable check ID: "S1", "H2", "B6", "lint", "build", …
    detail: str  # human-readable description
    severity: str  # "error" | "warning"


# ---------------------------------------------------------------------------
# Converters from legacy dataclasses
# ---------------------------------------------------------------------------


def _from_lint_issue(issue) -> ValidationIssue:
    return ValidationIssue(
        category="header",
        group=issue.group,
        subject=issue.block,
        check="lint",
        detail=issue.issue,
        severity=issue.severity,
    )


def _from_block_issue(issue) -> ValidationIssue:
    return ValidationIssue(
        category="build",
        group=issue.group,
        subject=issue.block,
        check="build",
        detail=issue.issue,
        severity=issue.severity,
    )


# ---------------------------------------------------------------------------
# Benchmark build-file scanners
# ---------------------------------------------------------------------------

_CMAKE_BENCH_RE = re.compile(r"add_executable\(bench_(\w+)\b")


def _cmake_bench_entries(cmake_path: Path) -> set[str]:
    if not cmake_path.exists():
        return set()
    return set(_CMAKE_BENCH_RE.findall(cmake_path.read_text()))


# ---------------------------------------------------------------------------
# Category S — structure checks
# ---------------------------------------------------------------------------

_CMAKE_VERSION_RE = re.compile(r"project\([^)]*\bVERSION\s+([\d.]+)", re.DOTALL)


def _check_structure(cfg: ProjectConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # S1 — group directory existence
    for group_name, rel_path in cfg.groups.items():
        if not (cfg.root / rel_path).exists():
            issues.append(
                ValidationIssue(
                    category="structure",
                    group=group_name,
                    subject="",
                    check="S1",
                    detail=f"group directory '{rel_path}' declared in config but does not exist",
                    severity="error",
                )
            )

    # S2 — CMakeLists.txt VERSION vs config
    cmake_path = cfg.root / "CMakeLists.txt"
    if cmake_path.exists():
        m = _CMAKE_VERSION_RE.search(cmake_path.read_text())
        if m and m.group(1) != cfg.version:
            issues.append(
                ValidationIssue(
                    category="structure",
                    group="",
                    subject="CMakeLists.txt",
                    check="S2",
                    detail=(
                        f"VERSION '{m.group(1)}' in CMakeLists.txt "
                        f"differs from config version '{cfg.version}'"
                    ),
                    severity="warning",
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Category H — header quality checks
# ---------------------------------------------------------------------------

_REGISTER_COUNTS_RE = re.compile(r"GR_REGISTER_BLOCK\(\s*\w+\s*,\s*(\d+)\s*,\s*(\d+)\s*,")


def _check_headers(cfg: ProjectConfig, group_filter: str | None = None) -> list[ValidationIssue]:
    from gr4_modtool.commands.add_test import parse_header_info
    from gr4_modtool.commands.lint_headers import lint_header

    issues: list[ValidationIssue] = []

    all_groups = discover_groups(cfg)
    if group_filter:
        all_groups = [g for g in all_groups if g.name == group_filter]

    for group_info in all_groups:
        g = group_info.name
        include_dir = cfg.group_include_dir(g)
        if not include_dir.exists():
            continue

        expected_ns = f"{cfg.cpp_namespace}::{g}" if g else cfg.cpp_namespace

        seen_names: dict[str, str] = {}  # block_name → filename (H6 duplicate detection)

        for hpp in sorted(include_dir.glob("*.hpp")):
            try:
                info = parse_header_info(hpp)
            except ValueError:
                continue

            text = hpp.read_text()
            block = info["block_name"]

            # H1 — #pragma once
            if "#pragma once" not in text:
                issues.append(
                    ValidationIssue(
                        category="header",
                        group=g,
                        subject=hpp.name,
                        check="H1",
                        detail="missing #pragma once",
                        severity="error",
                    )
                )

            # H2 — block struct name matches filename
            if block != hpp.stem:
                issues.append(
                    ValidationIssue(
                        category="header",
                        group=g,
                        subject=hpp.name,
                        check="H2",
                        detail=f"struct name '{block}' does not match filename '{hpp.name}'",
                        severity="error",
                    )
                )

            # H3 — namespace matches expected
            ns = info.get("namespace", "")
            if ns and ns != expected_ns:
                issues.append(
                    ValidationIssue(
                        category="header",
                        group=g,
                        subject=block,
                        check="H3",
                        detail=f"namespace '{ns}' should be '{expected_ns}'",
                        severity="warning",
                    )
                )

            # H4 / H5 — GR_REGISTER_BLOCK port counts vs actual declarations
            m = _REGISTER_COUNTS_RE.search(text)
            if m:
                reg_in, reg_out = int(m.group(1)), int(m.group(2))
                actual_in = len(info["in_ports"])
                actual_out = len(info["out_ports"])
                if reg_in != actual_in:
                    issues.append(
                        ValidationIssue(
                            category="header",
                            group=g,
                            subject=block,
                            check="H4",
                            detail=(
                                f"GR_REGISTER_BLOCK declares {reg_in} input(s) "
                                f"but {actual_in} PortIn<> found"
                            ),
                            severity="error",
                        )
                    )
                if reg_out != actual_out:
                    issues.append(
                        ValidationIssue(
                            category="header",
                            group=g,
                            subject=block,
                            check="H5",
                            detail=(
                                f"GR_REGISTER_BLOCK declares {reg_out} output(s) "
                                f"but {actual_out} PortOut<> found"
                            ),
                            severity="error",
                        )
                    )

            # H6 — duplicate block name within group
            if block in seen_names:
                issues.append(
                    ValidationIssue(
                        category="header",
                        group=g,
                        subject=block,
                        check="H6",
                        detail=f"block name '{block}' also defined in '{seen_names[block]}'",
                        severity="error",
                    )
                )
            else:
                seen_names[block] = hpp.name

            # Inherited lint-headers checks
            for lint_issue in lint_header(hpp, g):
                issues.append(_from_lint_issue(lint_issue))

    return issues


# ---------------------------------------------------------------------------
# Category B — build consistency checks
# ---------------------------------------------------------------------------


def _check_build(cfg: ProjectConfig, group_filter: str | None = None) -> list[ValidationIssue]:
    from gr4_modtool.commands.check import audit_project

    filter_groups = [group_filter] if group_filter else None
    issues = [_from_block_issue(i) for i in audit_project(cfg, groups=filter_groups)]

    # B6 — benchmark sources not registered in build files
    all_groups = discover_groups(cfg)
    if group_filter:
        all_groups = [g for g in all_groups if g.name == group_filter]

    for grp in all_groups:
        bench_dir = cfg.group_bench_dir(grp.name)
        if not bench_dir.exists():
            continue

        bench_files = sorted(bench_dir.glob("bench_*.cpp"))
        if not bench_files:
            continue

        cmake_entries = _cmake_bench_entries(bench_dir / "CMakeLists.txt")

        for bf in bench_files:
            block_name = bf.stem[6:]  # strip "bench_"

            if cfg.build_cmake and block_name not in cmake_entries:
                issues.append(
                    ValidationIssue(
                        category="build",
                        group=grp.name,
                        subject=block_name,
                        check="B6",
                        detail=f"bench_{block_name}.cpp has no CMake benchmark entry",
                        severity="warning",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_project(
    cfg: ProjectConfig,
    group_filter: str | None = None,
    run_structure: bool = True,
    run_headers: bool = True,
    run_build: bool = True,
) -> list[ValidationIssue]:
    """Run all enabled validation categories and return a combined issue list."""
    issues: list[ValidationIssue] = []
    if run_structure:
        issues.extend(_check_structure(cfg))
    if run_headers:
        issues.extend(_check_headers(cfg, group_filter))
    if run_build:
        issues.extend(_check_build(cfg, group_filter))
    return issues


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

_CAT_STYLE = {"structure": "yellow", "header": "cyan", "build": "blue"}


def _render_table(issues: list[ValidationIssue]) -> None:
    console = Console()

    if not issues:
        console.print("[green]✓  No issues found.[/green]")
        return

    tbl = Table(
        title="Validation Issues",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan",
    )
    tbl.add_column("Category")
    tbl.add_column("Group", style="green")
    tbl.add_column("Subject", style="white")
    tbl.add_column("Check", style="dim")
    tbl.add_column("Detail", style="white")
    tbl.add_column("Sev.", style="white")

    for issue in sorted(issues, key=lambda i: (i.category, i.group, i.subject)):
        sev_style = "red" if issue.severity == "error" else "yellow"
        cat_style = _CAT_STYLE.get(issue.category, "white")
        tbl.add_row(
            f"[{cat_style}]{issue.category}[/{cat_style}]",
            issue.group or "(project)",
            issue.subject or "—",
            issue.check,
            issue.detail,
            f"[{sev_style}]{issue.severity}[/{sev_style}]",
        )

    console.print(tbl)

    n_err = sum(1 for i in issues if i.severity == "error")
    n_warn = sum(1 for i in issues if i.severity == "warning")
    parts = []
    if n_err:
        parts.append(f"[red]{n_err} error(s)[/red]")
    if n_warn:
        parts.append(f"[yellow]{n_warn} warning(s)[/yellow]")
    console.print("  " + "  ·  ".join(parts))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("validate")
@click.option("--group", "group_filter", default=None, help="Restrict to one group.")
@click.option(
    "--skip-structure",
    is_flag=True,
    default=False,
    help="Skip project-structure checks (S1–S3).",
)
@click.option(
    "--skip-headers",
    is_flag=True,
    default=False,
    help="Skip header-quality checks (H1–H6 and lint-headers).",
)
@click.option(
    "--skip-build",
    is_flag=True,
    default=False,
    help="Skip build-consistency checks (B1–B6).",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as errors (exit 1 if any warnings).",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    group_filter: str | None,
    skip_structure: bool,
    skip_headers: bool,
    skip_build: bool,
    strict: bool,
    output_json: bool,
    project_dir: str | None,
) -> None:
    """Comprehensive project validation: structure, header quality, and build consistency."""
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    issues = validate_project(
        cfg,
        group_filter=group_filter,
        run_structure=not skip_structure,
        run_headers=not skip_headers,
        run_build=not skip_build,
    )

    def _is_failure(issue: ValidationIssue) -> bool:
        return issue.severity == "error" or (strict and issue.severity == "warning")

    if output_json:
        data = {
            "issues": [dataclasses.asdict(i) for i in issues],
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
            "category_counts": {
                cat: sum(1 for i in issues if i.category == cat)
                for cat in ("structure", "header", "build")
            },
        }
        click.echo(json.dumps(data, indent=2))
        if any(_is_failure(i) for i in issues):
            sys.exit(1)
        return

    _render_table(issues)

    if any(_is_failure(i) for i in issues):
        sys.exit(1)
