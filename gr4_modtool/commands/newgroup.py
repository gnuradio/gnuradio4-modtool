"""newgroup command — add a new block group to a project."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig, load_config, save_config
from gr4_modtool.templates import render


def add_group(cfg: ProjectConfig, name: str) -> None:
    """Create a group skeleton, register it in the config, and wire the build.

    Raises ValueError if the project is flat or the group already exists.
    """
    if cfg.flat:
        raise ValueError("Flat projects do not support groups.")
    if name in cfg.groups:
        raise ValueError(f"Group '{name}' already exists.")

    write_group_skeleton(cfg, name)

    cfg.groups[name] = f"blocks/{name}"
    save_config(cfg)

    blocks_cmake = cfg.blocks_dir / "CMakeLists.txt"
    if cfg.build_cmake and blocks_cmake.exists():
        cmake_mod.add_group_to_blocks_cmake(blocks_cmake, name, cfg.cmake_prefix)


@click.command("newgroup")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--name", default=None, help="Group name (skips prompt).")
def cmd(project_dir: str | None, name: str | None) -> None:
    """Add a new block group directory to the project."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if cfg.flat:
        click.echo("Flat projects do not support groups.", err=True)
        sys.exit(1)

    if name is None:
        name = questionary.text(
            "Group name (e.g. filter):",
            validate=lambda v: bool(v.strip()) or "Name cannot be empty",
        ).ask()
        if name is None:
            sys.exit(1)

    name = name.strip()
    try:
        add_group(cfg, name)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    click.echo(f"Created group '{name}' at {cfg.group_path(name)}")


def write_group_skeleton(cfg: ProjectConfig, group_name: str) -> None:
    """Create the directory tree for a new group (called by newmod and newgroup)."""
    group_path = cfg.root / "blocks" / group_name
    include_dir = group_path / "include" / cfg.gr4_include_prefix / group_name
    test_dir = group_path / "test"

    include_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    from gr4_modtool.commands.newmod import block_library_name

    group_ctx = {
        "cmake_prefix": cfg.cmake_prefix,
        "group_name": group_name,
        "gr4_include_prefix": cfg.gr4_include_prefix,
        "block_library_name": block_library_name(cfg.name, group_name),
    }
    test_ctx = {"group_name": group_name}

    if cfg.build_cmake:
        write_text(
            group_path / "CMakeLists.txt",
            render("group_CMakeLists.txt.j2", group_ctx, cfg.root),
        )
        write_text(
            test_dir / "CMakeLists.txt",
            render("test_CMakeLists.txt.j2", test_ctx, cfg.root),
        )
