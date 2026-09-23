"""rename-block command — rename a block within a group."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import remove_file, write_text
from gr4_modtool.project.discovery import discover_groups, load_config

_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def rename_block(cfg, group: str, old_name: str, new_name: str) -> list[Path]:
    """Rename *old_name* to *new_name* inside *group*.

    Updates the header, test source, CMakeLists.txt.
    Returns a list of written/removed paths (new paths only).
    """
    if not _NAME_RE.match(new_name):
        raise ValueError(
            f"'{new_name}' is not valid — block names must be CamelCase "
            "(start with uppercase, letters and digits only)."
        )

    old_header = cfg.group_include_dir(group) / f"{old_name}.hpp"
    if not old_header.exists():
        raise ValueError(f"Block '{old_name}' not found in group '{group}'.")

    new_header = cfg.group_include_dir(group) / f"{new_name}.hpp"
    if new_header.exists():
        raise ValueError(f"Block '{new_name}' already exists in group '{group}'.")

    modified: list[Path] = []

    # --- header ---
    text = old_header.read_text()
    write_text(new_header, text.replace(old_name, new_name))
    remove_file(old_header, missing_ok=False)
    modified.append(new_header)

    # --- test source ---
    old_lower, new_lower = old_name.lower(), new_name.lower()
    old_test = cfg.group_test_dir(group) / f"qa_{old_name}.cpp"
    new_test = cfg.group_test_dir(group) / f"qa_{new_name}.cpp"
    if old_test.exists():
        text = old_test.read_text()
        # Replace lowercase suite variable names first (longer match, no overlap with CamelCase)
        text = text.replace(f"{old_lower}GraphTests", f"{new_lower}GraphTests")
        text = text.replace(f"{old_lower}Tests", f"{new_lower}Tests")
        text = text.replace(old_name, new_name)
        write_text(new_test, text)
        remove_file(old_test, missing_ok=False)
        modified.append(new_test)

    # --- test CMakeLists.txt ---
    cmake_test = cfg.group_test_dir(group) / "CMakeLists.txt"
    if cmake_test.exists():
        text = cmake_test.read_text()
        updated = text.replace(f"qa_{old_name}", f"qa_{new_name}")
        if updated != text:
            write_text(cmake_test, updated)
            modified.append(cmake_test)

    return modified


@click.command("rename-block")
@click.argument("old_name")
@click.argument("new_name")
@click.option("--group", default=None, help="Group containing the block.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    old_name: str,
    new_name: str,
    group: str | None,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Rename a block within a group."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if group is None:
        groups = discover_groups(cfg)
        matching = [
            g.name for g in groups if (cfg.group_include_dir(g.name) / f"{old_name}.hpp").exists()
        ]
        if not matching:
            raise click.ClickException(f"Block '{old_name}' not found in any group.")
        if len(matching) > 1:
            raise click.ClickException(
                f"Block '{old_name}' found in multiple groups: {matching}. "
                "Use --group to specify which one."
            )
        group = matching[0]

    click.echo(f"Renaming '{old_name}' → '{new_name}' in group '{group}'")

    if not yes:
        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = rename_block(cfg, group, old_name, new_name)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Modified:")
    for p in written:
        click.echo(f"  {p}")
