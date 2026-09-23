"""lint-headers command — check block headers for common content issues."""

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

from gr4_modtool.commands.add_test import parse_annotated_params, parse_header_info
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config

# Matches GR_MAKE_REFLECTABLE(BlockName, a, b, c)
_REFLECTABLE_RE = re.compile(r"GR_MAKE_REFLECTABLE\s*\(([^)]+)\)")
# Matches the type list (last [...]) in GR_REGISTER_BLOCK — catches empty []
_REGISTER_TYPE_LIST_RE = re.compile(r"GR_REGISTER_BLOCK\b.*\[\s*([^\]]*)\s*\]\s*\)")


@dataclass
class LintIssue:
    group: str
    block: str
    issue: str
    severity: str  # "error" | "warning"


def _reflectable_names(text: str, block_name: str) -> list[str] | None:
    """Return member names from GR_MAKE_REFLECTABLE, or None if macro is absent."""
    m = _REFLECTABLE_RE.search(text)
    if not m:
        return None
    args = [a.strip() for a in m.group(1).split(",")]
    # First arg is the block name itself; remaining are member names.
    return args[1:] if len(args) > 1 else []


def lint_header(hpp: Path, group: str) -> list[LintIssue]:
    """Return lint issues for a single block header."""
    try:
        info = parse_header_info(hpp)
    except ValueError:
        return []  # not a recognisable block header — skip silently

    text = hpp.read_text()
    block = info["block_name"]
    issues: list[LintIssue] = []

    # ------------------------------------------------------------------ #
    # GR_REGISTER_BLOCK presence and type list
    # ------------------------------------------------------------------ #
    if "GR_REGISTER_BLOCK" not in text:
        issues.append(LintIssue(group, block, "missing GR_REGISTER_BLOCK macro", "error"))
    else:
        tl_m = _REGISTER_TYPE_LIST_RE.search(text)
        if tl_m and not tl_m.group(1).strip():
            issues.append(
                LintIssue(group, block, "GR_REGISTER_BLOCK has empty type list", "warning")
            )

    # ------------------------------------------------------------------ #
    # Block description
    # ------------------------------------------------------------------ #
    if not info["description"].strip():
        issues.append(
            LintIssue(group, block, 'block has no description (Doc<""> is empty)', "warning")
        )

    # ------------------------------------------------------------------ #
    # GR_MAKE_REFLECTABLE — presence and port/member consistency
    # ------------------------------------------------------------------ #
    reflectable = _reflectable_names(text, block)
    if reflectable is None:
        issues.append(LintIssue(group, block, "missing GR_MAKE_REFLECTABLE macro", "error"))
    else:
        port_names = {p["name"] for p in info["in_ports"] + info["out_ports"]}
        param_names = {p["name"] for p in parse_annotated_params(text)}
        known_names = port_names | param_names

        for name in sorted(port_names):
            if name not in reflectable:
                issues.append(
                    LintIssue(
                        group,
                        block,
                        f"port '{name}' is declared but absent from GR_MAKE_REFLECTABLE",
                        "error",
                    )
                )

        for name in reflectable:
            if name not in known_names:
                issues.append(
                    LintIssue(
                        group,
                        block,
                        f"'{name}' listed in GR_MAKE_REFLECTABLE but not declared as a port or parameter",
                        "warning",
                    )
                )

    # ------------------------------------------------------------------ #
    # Annotated<> parameters without Doc<> description
    # ------------------------------------------------------------------ #
    for line in text.splitlines():
        stripped = line.strip()
        if "Annotated<" in stripped and "Doc<" not in stripped:
            m = re.search(r"Annotated<[^>]+>\s+(\w+)", stripped)
            if m:
                param = m.group(1)
                issues.append(
                    LintIssue(
                        group,
                        block,
                        f"parameter '{param}' uses Annotated<> without a Doc<> description",
                        "warning",
                    )
                )

    return issues


def lint_headers(cfg: ProjectConfig, groups: list[str] | None = None) -> list[LintIssue]:
    """Lint all block headers in the project and return issues."""
    all_groups = discover_groups(cfg)
    issues: list[LintIssue] = []
    for group_info in all_groups:
        if groups is not None and group_info.name not in groups:
            continue
        include_dir = cfg.group_include_dir(group_info.name)
        if not include_dir.exists():
            continue
        for hpp in sorted(include_dir.glob("*.hpp")):
            issues.extend(lint_header(hpp, group_info.name))
    return issues


@click.command("lint-headers")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Check only this group.")
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as errors (exit 1 if any warnings).",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def cmd(
    project_dir: str | None,
    group: str | None,
    strict: bool,
    output_json: bool,
) -> None:
    """Check block headers for missing macros, empty descriptions, and port mismatches."""
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    filter_groups = [group] if group else None
    issues = lint_headers(cfg, groups=filter_groups)

    def _is_failure(issue: LintIssue) -> bool:
        return issue.severity == "error" or (strict and issue.severity == "warning")

    if output_json:
        data = {
            "issues": [dataclasses.asdict(i) for i in issues],
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
        }
        click.echo(json.dumps(data, indent=2))
        if any(_is_failure(i) for i in issues):
            sys.exit(1)
        return

    console = Console()

    if not issues:
        console.print("[green]No issues found.[/green]")
        return

    table = Table(title="Header Lint Issues", show_header=True, header_style="bold cyan")
    table.add_column("Group", style="green")
    table.add_column("Block", style="white")
    table.add_column("Issue", style="white")
    table.add_column("Severity", style="white")

    for issue in issues:
        sev_style = "red" if issue.severity == "error" else "yellow"
        table.add_row(
            issue.group,
            issue.block,
            issue.issue,
            f"[{sev_style}]{issue.severity}[/{sev_style}]",
        )

    console.print(table)

    if any(_is_failure(i) for i in issues):
        sys.exit(1)
