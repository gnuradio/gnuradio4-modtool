"""rename command — rename a block everywhere in the project."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import move_path, write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import discover_groups, load_config


def _rename_in_header(header: Path, old_name: str, new_name: str) -> None:
    """Rename struct name, GR_REGISTER_BLOCK, and GR_MAKE_REFLECTABLE in the header."""
    text = header.read_text()
    # Rename the struct name (whole-word)
    text = re.sub(rf"\b{re.escape(old_name)}\b", new_name, text)
    write_text(header, text)


@click.command("rename")
@click.argument("old_name", required=False)
@click.argument("new_name", required=False)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def cmd(
    old_name: str | None,
    new_name: str | None,
    project_dir: str | None,
    group: str | None,
    yes: bool,
) -> None:
    """Rename a block everywhere (header, test, build files)."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found.", err=True)
        sys.exit(1)

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

    if old_name is None:
        block_names = [b.name for b in group_info.blocks]
        if not block_names:
            click.echo(f"No blocks in group '{group}'.", err=True)
            sys.exit(1)
        old_name = questionary.select("Block to rename:", choices=block_names).ask()
        if old_name is None:
            sys.exit(0)

    if new_name is None:
        new_name = questionary.text(
            f"New name for '{old_name}' (CamelCase):",
            validate=lambda v: bool(re.match(r"^[A-Z][A-Za-z0-9]*$", v)) or "Must be CamelCase",
        ).ask()
        if new_name is None:
            sys.exit(0)

    old_header = cfg.group_include_dir(group) / f"{old_name}.hpp"
    new_header = cfg.group_include_dir(group) / f"{new_name}.hpp"
    old_test = cfg.group_test_dir(group) / f"qa_{old_name}.cpp"
    new_test = cfg.group_test_dir(group) / f"qa_{new_name}.cpp"
    cmake_test = cfg.group_test_dir(group) / "CMakeLists.txt"

    click.echo("\nWill rename:")
    if old_header.exists():
        click.echo(f"  {old_header} → {new_header}")
    if old_test.exists():
        click.echo(f"  {old_test} → {new_test}")
    if cmake_test.exists():
        click.echo(f"  (update) {cmake_test}")

    if not yes:
        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            sys.exit(0)

    if old_header.exists():
        _rename_in_header(old_header, old_name, new_name)
        move_path(old_header, new_header)

    if old_test.exists():
        text = old_test.read_text()
        text = re.sub(rf"\b{re.escape(old_name)}\b", new_name, text)
        write_text(old_test, text)
        move_path(old_test, new_test)

    if cfg.build_cmake and cmake_test.exists():
        cmake_mod.rename_test_entry(cmake_test, old_name, new_name)

    location = f"in group '{group}'" if group else "(flat layout)"
    click.echo(f"Renamed '{old_name}' → '{new_name}' {location}.")
