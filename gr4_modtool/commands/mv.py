"""mv command — move a block from one group to another."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import remove_file, write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


def move_block(cfg: ProjectConfig, src_group: str, block_name: str, dst_group: str) -> list[Path]:
    """Move block_name from src_group to dst_group.

    Raises FileNotFoundError if source header does not exist.
    Raises FileExistsError if destination header already exists.
    """
    src_header = cfg.group_include_dir(src_group) / f"{block_name}.hpp"
    dst_header = cfg.group_include_dir(dst_group) / f"{block_name}.hpp"
    src_test = cfg.group_test_dir(src_group) / f"qa_{block_name}.cpp"
    dst_test = cfg.group_test_dir(dst_group) / f"qa_{block_name}.cpp"

    if not src_header.exists():
        raise FileNotFoundError(f"Source header not found: {src_header}")
    if dst_header.exists():
        raise FileExistsError(f"Destination header already exists: {dst_header}")

    cfg.group_include_dir(dst_group).mkdir(parents=True, exist_ok=True)

    # Update header: replace all occurrences of src namespace (declaration, closing comment,
    # GR_REGISTER_BLOCK, etc.)
    text = src_header.read_text()
    src_ns = f"{cfg.cpp_namespace}::{src_group}"
    dst_ns = f"{cfg.cpp_namespace}::{dst_group}"
    text = text.replace(src_ns, dst_ns)
    write_text(dst_header, text)
    remove_file(src_header, missing_ok=False)
    affected: list[Path] = [dst_header]

    # Update test source
    if src_test.exists():
        cfg.group_test_dir(dst_group).mkdir(parents=True, exist_ok=True)
        ttext = src_test.read_text()
        # Update #include path
        ttext = re.sub(
            rf"({re.escape(cfg.gr4_include_prefix)}/){re.escape(src_group)}/",
            rf"\1{dst_group}/",
            ttext,
        )
        # Update namespace references
        ttext = ttext.replace(src_ns, dst_ns)
        write_text(dst_test, ttext)
        remove_file(src_test, missing_ok=False)
        affected.append(dst_test)

    # Source build files — remove
    src_cmake = cfg.group_test_dir(src_group) / "CMakeLists.txt"
    if cfg.build_cmake and src_cmake.exists():
        cmake_mod.remove_test_entry(src_cmake, block_name)
        affected.append(src_cmake)

    # Destination build files — add
    dst_cmake = cfg.group_test_dir(dst_group) / "CMakeLists.txt"
    if cfg.build_cmake and dst_cmake.exists() and dst_test.exists():
        target_libs = f"{cfg.cmake_prefix}::blocks_{dst_group}_headers"
        cmake_mod.append_test_entry(dst_cmake, block_name, target_libs)
        if dst_cmake not in affected:
            affected.append(dst_cmake)

    return affected


@click.command("mv")
@click.argument("block_name", required=False)
@click.option("--from", "src_group", default=None, help="Source group.")
@click.option("--to", "dst_group", default=None, help="Destination group.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    block_name: str | None,
    src_group: str | None,
    dst_group: str | None,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Move a block (header, test, build entries) from one group to another."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if cfg.flat:
        click.echo("Flat projects do not support groups.", err=True)
        sys.exit(1)

    groups = discover_groups(cfg)
    group_names = [g.name for g in groups]

    if not group_names:
        click.echo("No groups found.", err=True)
        sys.exit(1)

    if src_group is None:
        src_group = questionary.select("Source group:", choices=group_names).ask()
        if src_group is None:
            sys.exit(0)

    src_info = next((g for g in groups if g.name == src_group), None)
    if src_info is None:
        click.echo(f"Group '{src_group}' not found.", err=True)
        sys.exit(1)

    if block_name is None:
        block_names = [b.name for b in src_info.blocks]
        if not block_names:
            click.echo(f"No blocks in group '{src_group}'.", err=True)
            sys.exit(1)
        block_name = questionary.select("Block to move:", choices=block_names).ask()
        if block_name is None:
            sys.exit(0)

    if dst_group is None:
        dst_choices = [n for n in group_names if n != src_group]
        if not dst_choices:
            click.echo("No other groups to move to.", err=True)
            sys.exit(1)
        dst_group = questionary.select("Destination group:", choices=dst_choices).ask()
        if dst_group is None:
            sys.exit(0)

    click.echo(f"\nMove '{block_name}': {src_group} → {dst_group}")
    if not yes:
        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            sys.exit(0)

    try:
        affected = move_block(cfg, src_group, block_name, dst_group)
    except (FileNotFoundError, FileExistsError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Done:")
    for p in affected:
        click.echo(f"  {p}")
