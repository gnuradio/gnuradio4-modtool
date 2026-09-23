"""rename-group command — rename a block group and update all references."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import move_path, write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config, save_config

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def rename_group(cfg: ProjectConfig, old_name: str, new_name: str) -> list[Path]:
    """Rename a block group directory and update all references.

    Updates in order:
      1. Move blocks/<old>/ → blocks/<new>/
      2. Rename include/<prefix>/<old>/ → include/<prefix>/<new>/
      3. Block headers: namespace and include-path occurrences
      4. Test .cpp files: include-path occurrences
      5. Group-level CMakeLists.txt and test/CMakeLists.txt: target names
      6. blocks/CMakeLists.txt: add_subdirectory + target_link_libraries
      7. .gr4modtool.toml: groups mapping

    Returns list of created/modified paths.

    Raises:
        ValueError: if old_name is not registered, new_name is already registered,
                    or new_name is not valid snake_case.
        FileNotFoundError: if the group directory does not exist on disk.
    """
    if old_name not in cfg.groups:
        raise ValueError(f"Group '{old_name}' not found. Known groups: {sorted(cfg.groups)}")
    if new_name in cfg.groups:
        raise ValueError(f"Group '{new_name}' already exists.")
    if not _NAME_RE.match(new_name):
        raise ValueError(
            f"Group name '{new_name}' must be snake_case "
            "(lowercase letters, digits, underscores, starting with a letter)."
        )

    old_group_path = cfg.group_path(old_name)
    new_group_path = cfg.root / "blocks" / new_name

    if not old_group_path.exists():
        raise FileNotFoundError(f"Group directory not found: {old_group_path}")

    modified: list[Path] = []

    # ------------------------------------------------------------------
    # 1. Move the group directory
    # ------------------------------------------------------------------
    move_path(old_group_path, new_group_path)
    modified.append(new_group_path)

    # ------------------------------------------------------------------
    # 2. Rename the include sub-directory
    # ------------------------------------------------------------------
    old_inc = new_group_path / "include" / cfg.gr4_include_prefix / old_name
    new_inc = new_group_path / "include" / cfg.gr4_include_prefix / new_name
    if old_inc.exists():
        move_path(old_inc, new_inc)

    # ------------------------------------------------------------------
    # 3. Update block headers: namespace and include-path references
    # ------------------------------------------------------------------
    if new_inc.exists():
        for hpp in sorted(new_inc.glob("*.hpp")):
            text = hpp.read_text()
            # Namespace: ::old_name (covers ::old_name { and ::old_name::)
            text = text.replace(f"::{old_name}", f"::{new_name}")
            # Include path: /old_name/
            text = text.replace(f"/{old_name}/", f"/{new_name}/")
            write_text(hpp, text)
            modified.append(hpp)

    # ------------------------------------------------------------------
    # 4. Update test .cpp files: include-path references
    # ------------------------------------------------------------------
    test_dir = new_group_path / "test"
    if test_dir.exists():
        for cpp in sorted(test_dir.glob("qa_*.cpp")):
            text = cpp.read_text()
            text = text.replace(f"/{old_name}/", f"/{new_name}/")
            write_text(cpp, text)
            modified.append(cpp)

    # ------------------------------------------------------------------
    # 5. Update group-level and test CMakeLists.txt (target names)
    # ------------------------------------------------------------------
    for cmake_path in [
        new_group_path / "CMakeLists.txt",
        new_group_path / "test" / "CMakeLists.txt",
    ]:
        if cmake_path.exists():
            text = cmake_path.read_text()
            # Target names: blocks_<old> → blocks_<new>
            text = text.replace(f"blocks_{old_name}", f"blocks_{new_name}")
            # Install/include path: /gnuradio-4.0/<old>
            text = text.replace(
                f"/{cfg.gr4_include_prefix}/{old_name}", f"/{cfg.gr4_include_prefix}/{new_name}"
            )
            # Comment header: # Tests for <old>
            text = text.replace(f"# Tests for {old_name}", f"# Tests for {new_name}")
            write_text(cmake_path, text)
            modified.append(cmake_path)

    # ------------------------------------------------------------------
    # 6. Update blocks/CMakeLists.txt
    # ------------------------------------------------------------------
    blocks_cmake = cfg.blocks_dir / "CMakeLists.txt"
    if blocks_cmake.exists():
        text = blocks_cmake.read_text()
        text = text.replace(f"add_subdirectory({old_name})", f"add_subdirectory({new_name})")
        text = text.replace(f"blocks_{old_name}", f"blocks_{new_name}")
        write_text(blocks_cmake, text)
        modified.append(blocks_cmake)

    # ------------------------------------------------------------------
    # 8. Update .gr4modtool.toml
    # ------------------------------------------------------------------
    old_rel = cfg.groups.pop(old_name)
    cfg.groups[new_name] = old_rel.replace(f"/{old_name}", f"/{new_name}", 1)
    save_config(cfg)
    modified.append(cfg.root / ".gr4modtool.toml")

    return modified


@click.command("rename-group")
@click.argument("old_name")
@click.argument("new_name")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def cmd(old_name: str, new_name: str, project_dir: str | None, yes: bool) -> None:
    """Rename a block group and update all references."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if old_name not in cfg.groups:
        click.echo(f"Error: group '{old_name}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Rename group '{old_name}' → '{new_name}'")
    click.echo(f"  {cfg.group_path(old_name)}  →  {cfg.root / 'blocks' / new_name}")
    click.echo(
        "  Updates: include subdir, .hpp namespaces, .cpp includes, CMakeLists.txt, .gr4modtool.toml"
    )

    if not yes:
        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = rename_group(cfg, old_name, new_name)
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"\nRenamed '{old_name}' → '{new_name}'  ({len(written)} path(s) updated)")
    click.echo("Run 'gr4_modtool info' to verify.")
