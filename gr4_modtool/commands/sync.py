"""sync command — reconcile headers, test sources, and build entries."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import click
import questionary
from rich.console import Console
from rich.table import Table

from gr4_modtool.commands.check import _cmake_test_entries
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import discover_groups, load_config

# (color, label) for each action type
_ACTION_META: dict[str, tuple[str, str]] = {
    "generate_test": ("green", "generate test + register"),
    "add_cmake_entry": ("cyan", "add CMake entry"),
    "remove_cmake_entry": ("yellow", "remove stale CMake entry"),
    "warn_orphan": ("red", "orphan source (no header)"),
}


@dataclass
class SyncAction:
    group: str
    block: str
    action: str  # one of the keys in _ACTION_META


def plan_sync(cfg, prune: bool = False) -> list[SyncAction]:
    """Return the list of actions needed to bring the project into sync."""
    actions: list[SyncAction] = []

    for group_info in discover_groups(cfg):
        g = group_info.name
        include_dir = cfg.group_include_dir(g)
        test_dir = cfg.group_test_dir(g)

        headers: set[str] = (
            {hpp.stem for hpp in include_dir.glob("*.hpp")} if include_dir.exists() else set()
        )
        test_srcs: set[str] = (
            {qa.stem[3:] for qa in test_dir.glob("qa_*.cpp")} if test_dir.exists() else set()
        )
        cmake_set = _cmake_test_entries(test_dir / "CMakeLists.txt") if cfg.build_cmake else set()

        # 1. Header with no test source → generate test (write_test_for_block also adds build entries)
        generating: set[str] = set()
        for block in sorted(headers - test_srcs):
            actions.append(SyncAction(g, block, "generate_test"))
            generating.add(block)

        # 2. Test source exists but build entry missing (skip blocks already being generated)
        cmake_file = test_dir / "CMakeLists.txt"
        for block in sorted((test_srcs - cmake_set) - generating):
            if cfg.build_cmake and cmake_file.exists():
                actions.append(SyncAction(g, block, "add_cmake_entry"))

        # 3. Stale build entries (only with --prune; skip blocks being regenerated)
        if prune:
            for block in sorted((cmake_set - test_srcs) - generating):
                actions.append(SyncAction(g, block, "remove_cmake_entry"))

        # 4. Orphan test sources (warn regardless of prune)
        for block in sorted(test_srcs - headers):
            actions.append(SyncAction(g, block, "warn_orphan"))

    return actions


def apply_sync(cfg, actions: list[SyncAction]) -> list[str]:
    """Apply the sync actions. Returns a list of warning strings for skipped items."""
    from gr4_modtool.commands.add_test import write_test_for_block

    warnings: list[str] = []

    for action in actions:
        g, block = action.group, action.block
        test_dir = cfg.group_test_dir(g)
        target_libs = (
            f"{cfg.cmake_prefix}::blocks_headers"
            if not g
            else f"{cfg.cmake_prefix}::blocks_{g}_headers"
        )

        if action.action == "generate_test":
            try:
                write_test_for_block(cfg, g, block)
            except ValueError as exc:
                warnings.append(f"  {block}: could not parse header ({exc}); skipped")
            except FileExistsError:
                pass  # already exists — harmless race

        elif action.action == "add_cmake_entry":
            cmake_mod.append_test_entry(test_dir / "CMakeLists.txt", block, target_libs)

        elif action.action == "remove_cmake_entry":
            cmake_mod.remove_test_entry(test_dir / "CMakeLists.txt", block)

        # warn_orphan: informational only — already shown in the plan table

    return warnings


def _print_plan(actions: list[SyncAction]) -> None:
    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Group")
    table.add_column("Block")
    table.add_column("Action")
    for a in actions:
        color, label = _ACTION_META.get(a.action, ("white", a.action))
        table.add_row(
            a.group or "(flat)",
            a.block,
            f"[{color}]{label}[/{color}]",
        )
    console.print(table)


@click.command("sync")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", "groups", multiple=True, help="Limit sync to this group (repeatable).")
@click.option(
    "--prune",
    is_flag=True,
    default=False,
    help="Also remove stale build entries that point at missing test sources.",
)
@click.option(
    "--yes", "-y", is_flag=True, default=False, help="Apply without interactive confirmation."
)
@click.option(
    "--dry-run", "-n", is_flag=True, default=False, help="Show plan without modifying any files."
)
def cmd(
    project_dir: str | None,
    groups: tuple[str, ...],
    prune: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    """Reconcile headers, test sources, and build entries across all groups.

    By default, sync generates missing test files and adds missing build entries.
    Use --prune to also remove stale entries that point at deleted test sources.
    """
    cfg = load_config(Path(project_dir) if project_dir else None)

    all_actions = plan_sync(cfg, prune=prune)

    # Filter by --group if specified
    if groups:
        all_actions = [a for a in all_actions if a.group in groups]

    if not all_actions:
        click.echo("Nothing to sync.")
        return

    _print_plan(all_actions)

    # Separate informational warnings from actionable items
    apply_actions = [a for a in all_actions if a.action != "warn_orphan"]

    if not apply_actions:
        sys.exit(0)

    if dry_run:
        sys.exit(0)

    if not yes:
        confirmed = questionary.confirm("Apply these changes?", default=False).ask()
        if not confirmed:
            sys.exit(0)

    warnings = apply_sync(cfg, apply_actions)
    if warnings:
        click.echo("\nWarnings:")
        for w in warnings:
            click.echo(w)
