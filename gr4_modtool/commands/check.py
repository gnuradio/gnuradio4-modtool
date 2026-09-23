"""check command — audit the project for out-of-sync state."""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


@dataclass
class BlockIssue:
    group: str
    block: str
    issue: str
    severity: str  # "error" | "warning"


def _cmake_test_entries(cmake_path: Path) -> set[str]:
    if not cmake_path.exists():
        return set()
    text = cmake_path.read_text()
    return set(re.findall(r"add_ut_test\(qa_(\w+)", text))


def audit_project(cfg: ProjectConfig, groups: list[str] | None = None) -> list[BlockIssue]:
    """Scan the project and return a list of BlockIssue records."""
    issues: list[BlockIssue] = []
    all_groups = discover_groups(cfg)

    for group_info in all_groups:
        if groups is not None and group_info.name not in groups:
            continue

        g = group_info.name
        include_dir = cfg.group_include_dir(g)
        test_dir = cfg.group_test_dir(g)

        headers: set[str] = set()
        if include_dir.exists():
            for hpp in include_dir.glob("*.hpp"):
                headers.add(hpp.stem)
                text = hpp.read_text()
                if "GR_REGISTER_BLOCK" not in text:
                    issues.append(
                        BlockIssue(g, hpp.stem, "missing GR_REGISTER_BLOCK macro", "warning")
                    )

        test_srcs: set[str] = set()
        if test_dir.exists():
            for qa in test_dir.glob("qa_*.cpp"):
                test_srcs.add(qa.stem[3:])  # strip "qa_"

        cmake_entries = _cmake_test_entries(test_dir / "CMakeLists.txt")

        for block in headers:
            if block not in test_srcs:
                issues.append(BlockIssue(g, block, "no test source (qa_*.cpp missing)", "warning"))

        cmake_file = test_dir / "CMakeLists.txt"
        for block in test_srcs:
            if cfg.build_cmake and cmake_file.exists() and block not in cmake_entries:
                issues.append(BlockIssue(g, block, "test source has no CMake entry", "error"))

        for block in cmake_entries:
            if block not in test_srcs:
                issues.append(BlockIssue(g, block, "CMake entry has no test source", "error"))

    return issues


@click.command("check")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Audit only this group.")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def cmd(project_dir: str | None, group: str | None, output_json: bool) -> None:
    """Audit the project for out-of-sync headers, tests, and build entries."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    filter_groups = [group] if group else None
    issues = audit_project(cfg, groups=filter_groups)

    if output_json:
        data = {
            "issues": [dataclasses.asdict(i) for i in issues],
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
        }
        click.echo(json.dumps(data, indent=2))
        if any(i.severity == "error" for i in issues):
            sys.exit(1)
        return

    console = Console()

    if not issues:
        console.print("[green]No issues found.[/green]")
        return

    table = Table(title="Project Issues", show_header=True, header_style="bold cyan")
    table.add_column("Group", style="green")
    table.add_column("Block", style="white")
    table.add_column("Issue", style="white")
    table.add_column("Severity", style="white")

    has_errors = False
    for issue in issues:
        severity_style = "red" if issue.severity == "error" else "yellow"
        table.add_row(
            issue.group,
            issue.block,
            issue.issue,
            f"[{severity_style}]{issue.severity}[/{severity_style}]",
        )
        if issue.severity == "error":
            has_errors = True

    console.print(table)
    if has_errors:
        sys.exit(1)
