"""rm command — remove a block and its test from the project."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import remove_file
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


def remove_block(cfg: ProjectConfig, group: str, block_name: str) -> list[Path]:
    """Remove a block's header, test source, and CMake test entry.

    Returns the paths that were deleted or modified.
    Raises ValueError if the block has no header or test source in *group*.
    """
    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    test_src = cfg.group_test_dir(group) / f"qa_{block_name}.cpp"

    files_to_remove = [f for f in (header, test_src) if f.exists()]
    if not files_to_remove:
        location = f"group '{group}'" if group else "flat layout"
        raise ValueError(f"Block '{block_name}' not found in {location}.")

    affected: list[Path] = []
    for f in files_to_remove:
        remove_file(f, missing_ok=False)
        affected.append(f)

    build_cmake = cfg.group_test_dir(group) / "CMakeLists.txt"
    if cfg.build_cmake and build_cmake.exists():
        cmake_mod.remove_test_entry(build_cmake, block_name)
        affected.append(build_cmake)

    return affected


@click.command("rm")
@click.argument("block_name", required=False)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Group containing the block.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def cmd(block_name: str | None, project_dir: str | None, group: str | None, yes: bool) -> None:
    """Remove a block (header, test, build entries) from the project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found in project.", err=True)
        sys.exit(1)

    # Select group
    if cfg.flat:
        group = ""
    elif group is None:
        group = questionary.select("Group:", choices=[g.name for g in groups]).ask()
        if group is None:
            sys.exit(0)

    group_info = next((g for g in groups if g.name == group), None)
    if group_info is None:
        click.echo(f"Group '{group}' not found.", err=True)
        sys.exit(1)

    # Select block
    if block_name is None:
        block_names = [b.name for b in group_info.blocks]
        if not block_names:
            click.echo(f"No blocks found in group '{group}'.", err=True)
            sys.exit(1)
        block_name = questionary.select("Block to remove:", choices=block_names).ask()
        if block_name is None:
            sys.exit(0)

    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    test_src = cfg.group_test_dir(group) / f"qa_{block_name}.cpp"

    files_to_remove = [f for f in [header, test_src] if f.exists()]
    build_cmake = cfg.group_test_dir(group) / "CMakeLists.txt"

    click.echo("\nWill remove:")
    for f in files_to_remove:
        click.echo(f"  {f}")
    if build_cmake.exists():
        click.echo(f"  (update) {build_cmake}")

    if not yes:
        confirm = questionary.confirm("Proceed?", default=False).ask()
        if not confirm:
            sys.exit(0)

    try:
        remove_block(cfg, group, block_name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    location = f"from group '{group}'" if group else "(flat layout)"
    click.echo(f"Removed block '{block_name}' {location}.")
