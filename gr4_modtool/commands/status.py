"""status command — project health dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import discover_groups, load_config


@dataclass
class GroupSummary:
    name: str
    block_count: int
    tested_count: int
    missing_tests: list[str] = field(default_factory=list)


@dataclass
class ProjectStatus:
    name: str
    version: str
    root: Path
    groups: list[GroupSummary]
    flat: bool
    build_cmake: bool
    ci_workflows: list[str]
    has_clang_format: bool
    has_clang_tidy: bool
    has_doxyfile: bool
    has_precommit: bool


def gather_status(cfg) -> ProjectStatus:
    """Inspect the project on disk and return a ProjectStatus snapshot."""
    group_summaries = []
    for group_info in discover_groups(cfg):
        test_dir = cfg.group_test_dir(group_info.name)
        tested = {p.stem[3:] for p in test_dir.glob("qa_*.cpp")} if test_dir.exists() else set()
        blocks = [b.name for b in group_info.blocks]
        missing = [b for b in blocks if b not in tested]
        group_summaries.append(
            GroupSummary(
                name=group_info.name,
                block_count=len(blocks),
                tested_count=len(blocks) - len(missing),
                missing_tests=missing,
            )
        )

    workflow_dir = cfg.root / ".github" / "workflows"
    ci_workflows = (
        [p.name for p in sorted(workflow_dir.glob("*.yml"))] if workflow_dir.exists() else []
    )

    return ProjectStatus(
        name=cfg.name,
        version=cfg.version,
        root=cfg.root,
        groups=group_summaries,
        flat=cfg.flat,
        build_cmake=cfg.build_cmake,
        ci_workflows=ci_workflows,
        has_clang_format=(cfg.root / ".clang-format").exists(),
        has_clang_tidy=(cfg.root / ".clang-tidy").exists(),
        has_doxyfile=(cfg.root / "Doxyfile").exists(),
        has_precommit=(cfg.root / ".pre-commit-config.yaml").exists(),
    )


def _tick(ok: bool) -> str:
    return "[green]✓[/green]" if ok else "[dim]✗[/dim]"


def render_status(status: ProjectStatus) -> None:
    console = Console()

    total_blocks = sum(g.block_count for g in status.groups)
    build_str = "cmake" if status.build_cmake else "none"

    console.print()
    console.rule(f"[bold]{status.name}[/bold]  [dim]v{status.version}[/dim]")
    console.print(f"  [dim]{status.root}[/dim]")
    if status.flat:
        console.print(f"  flat layout · {total_blocks} block(s) · {build_str}")
    else:
        console.print(f"  {len(status.groups)} group(s) · {total_blocks} block(s) · {build_str}")
    console.print()

    # Groups / test coverage
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", padding=(0, 2))
    if not status.flat:
        table.add_column("Group")
    table.add_column("Blocks", justify="right")
    table.add_column("Tests", justify="right")
    for g in status.groups:
        if g.block_count == 0:
            test_str = "[dim]—[/dim]"
        elif g.missing_tests:
            test_str = f"[yellow]{g.tested_count}/{g.block_count}[/yellow]"
        else:
            test_str = f"[green]{g.tested_count}/{g.block_count}[/green]"
        if status.flat:
            table.add_row(str(g.block_count), test_str)
        else:
            table.add_row(g.name, str(g.block_count), test_str)
    console.print(table)

    # CI workflows
    console.print("  [bold]CI workflows[/bold]")
    if status.ci_workflows:
        for wf in status.ci_workflows:
            console.print(f"    [green]✓[/green]  {wf}")
    else:
        console.print("    [dim]none — run 'gr4_modtool ci' to generate[/dim]")
    console.print()

    # Quality tools
    console.print("  [bold]Quality tools[/bold]")
    console.print(f"    {_tick(status.has_clang_format)}  .clang-format")
    console.print(f"    {_tick(status.has_clang_tidy)}  .clang-tidy")
    console.print(f"    {_tick(status.has_doxyfile)}  Doxyfile")
    console.print(f"    {_tick(status.has_precommit)}  .pre-commit-config.yaml")
    console.print()

    # Warnings
    all_missing = [(g.name, b) for g in status.groups for b in g.missing_tests]
    if all_missing:
        console.print("  [bold yellow]⚠  Warnings[/bold yellow]")
        for grp, blk in all_missing:
            label = blk if not grp else f"{grp}/{blk}"
            console.print(f"    [yellow]•[/yellow]  {label} — no test file")
        console.print()
    else:
        console.print("  [green]✓  All blocks have test files[/green]")
        console.print()


@click.command("status")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(project_dir: str | None) -> None:
    """Show a health summary of the current project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    status = gather_status(cfg)
    render_status(status)
