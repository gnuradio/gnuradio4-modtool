"""newparam command — add an Annotated<> parameter to an existing block header."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config


def add_param(
    cfg: ProjectConfig,
    group: str,
    block_name: str,
    param_name: str,
    param_type: str,
    description: str,
    default_value: str = "{}",
) -> list[Path]:
    """Insert an Annotated<> member into block_name's header and update GR_MAKE_REFLECTABLE.

    Raises FileNotFoundError if the header does not exist.
    Raises ValueError if param_name is already declared in the header.
    """
    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    if not header.exists():
        raise FileNotFoundError(f"Header not found: {header}")

    text = header.read_text()

    if re.search(rf"\b{re.escape(param_name)}\b", text):
        raise ValueError(f"'{param_name}' is already declared in {block_name}")

    param_line = (
        f'    Annotated<{param_type}, "{param_name}", Doc<"{description}">> '
        f"{param_name}{{{default_value}}};\n"
    )

    # Insert before the GR_MAKE_REFLECTABLE line
    text = re.sub(
        r"([ \t]*GR_MAKE_REFLECTABLE\()",
        param_line + r"\1",
        text,
    )

    # Append param_name inside the macro
    text = re.sub(
        r"(GR_MAKE_REFLECTABLE\([^)]+)\)",
        rf"\1, {param_name})",
        text,
    )

    write_text(header, text)
    return [header]


@click.command("newparam")
@click.argument("block_name", required=False)
@click.argument("param_name", required=False)
@click.option("--group", default=None, help="Group containing the block.")
@click.option("--type", "param_type", default=None, help="C++ type (e.g. float, int32_t).")
@click.option("--description", default=None, help="Short description for Doc<>.")
@click.option(
    "--default",
    "default_value",
    default=None,
    help="C++ default value (e.g. '1.0f', '0'). Defaults to '{}'.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    block_name: str | None,
    param_name: str | None,
    group: str | None,
    param_type: str | None,
    description: str | None,
    default_value: str | None,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Add an Annotated<> parameter to an existing block header."""
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

    if block_name is None:
        block_names = [b.name for b in group_info.blocks]
        if not block_names:
            click.echo(f"No blocks in group '{group}'.", err=True)
            sys.exit(1)
        block_name = questionary.select("Block:", choices=block_names).ask()
        if block_name is None:
            sys.exit(0)

    if param_name is None:
        param_name = questionary.text("Parameter name (snake_case):").ask()
        if not param_name:
            sys.exit(0)

    if param_type is None:
        param_type = questionary.text("C++ type:", default="float").ask()
        if not param_type:
            sys.exit(0)

    if description is None:
        description = questionary.text("Description:").ask()
        if description is None:
            sys.exit(0)

    if default_value is None:
        default_value = questionary.text("Default value:", default="{}").ask()
        if default_value is None:
            sys.exit(0)

    if not yes:
        confirm = questionary.confirm(
            f"Add '{param_name}: {param_type}' to {block_name}?", default=True
        ).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = add_param(
            cfg, group, block_name, param_name, param_type, description, default_value
        )
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Modified:")
    for p in written:
        click.echo(f"  {p}")
