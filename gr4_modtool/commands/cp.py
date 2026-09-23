"""cp command — copy a block to a new name (optionally into a different group)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config
from gr4_modtool.templates import render


def copy_block(
    cfg: ProjectConfig,
    src_group: str,
    src_name: str,
    dst_name: str,
    dst_group: str | None = None,
    gen_test: bool = False,
) -> list[Path]:
    """Copy block src_name to dst_name (optionally into dst_group).

    Raises FileNotFoundError if src header does not exist.
    Raises FileExistsError if dst header already exists.
    """
    dst_group = dst_group or src_group

    src_header = cfg.group_include_dir(src_group) / f"{src_name}.hpp"
    dst_header = cfg.group_include_dir(dst_group) / f"{dst_name}.hpp"

    if not src_header.exists():
        raise FileNotFoundError(f"Source header not found: {src_header}")
    if dst_header.exists():
        raise FileExistsError(f"Destination header already exists: {dst_header}")

    cfg.group_include_dir(dst_group).mkdir(parents=True, exist_ok=True)

    # Whole-word rename of block name in header content
    text = src_header.read_text()
    text = re.sub(rf"\b{re.escape(src_name)}\b", dst_name, text)

    # Update namespace if moving to different group — everywhere the qualified
    # namespace appears: the declaration, the closing comment, and the
    # GR_REGISTER_BLOCK string/token references.
    if dst_group != src_group:
        src_ns = f"{cfg.cpp_namespace}::{src_group}"
        dst_ns = f"{cfg.cpp_namespace}::{dst_group}"
        text = re.sub(rf"\b{re.escape(src_ns)}\b", dst_ns, text)

    write_text(dst_header, text)
    written: list[Path] = [dst_header]

    if gen_test:
        from gr4_modtool.commands.add_test import parse_header_info
        from gr4_modtool.commands.newblock import _build_template_ctx

        info = parse_header_info(dst_header)
        ctx = _build_template_ctx(
            block_name=info["block_name"],
            namespace=info["namespace"],
            group=dst_group,
            description=info["description"],
            template_params=info["template_params"],
            in_ports=info["in_ports"],
            out_ports=info["out_ports"],
            type_list=info["type_list"],
            processing_style=info["processing_style"],
            gr4_include_prefix=cfg.gr4_include_prefix,
        )
        test_dir = cfg.group_test_dir(dst_group)
        test_dir.mkdir(parents=True, exist_ok=True)
        test_path = test_dir / f"qa_{dst_name}.cpp"
        write_text(test_path, render("qa_block.cpp.j2", ctx, cfg.root))
        written.append(test_path)

        cmake_test = test_dir / "CMakeLists.txt"
        if cfg.build_cmake and cmake_test.exists():
            target_libs = (
                f"{cfg.cmake_prefix}::blocks_headers"
                if not dst_group
                else f"{cfg.cmake_prefix}::blocks_{dst_group}_headers"
            )
            cmake_mod.append_test_entry(cmake_test, dst_name, target_libs)
            written.append(cmake_test)

    return written


@click.command("cp")
@click.argument("src_name", required=False)
@click.argument("dst_name", required=False)
@click.option("--from-group", default=None)
@click.option("--to-group", default=None)
@click.option("--gen-test", is_flag=True, default=False, help="Generate a new test from template.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    src_name: str | None,
    dst_name: str | None,
    from_group: str | None,
    to_group: str | None,
    gen_test: bool,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Copy a block to a new name (optionally into a different group)."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)
    group_names = [g.name for g in groups]

    if not group_names:
        click.echo("No groups found.", err=True)
        sys.exit(1)

    if cfg.flat:
        from_group = ""
    elif from_group is None:
        from_group = questionary.select("Source group:", choices=group_names).ask()
        if from_group is None:
            sys.exit(0)

    src_info = next((g for g in groups if g.name == from_group), None)
    if src_info is None:
        click.echo(f"Group '{from_group}' not found.", err=True)
        sys.exit(1)

    if src_name is None:
        block_names = [b.name for b in src_info.blocks]
        if not block_names:
            click.echo(f"No blocks in group '{from_group}'.", err=True)
            sys.exit(1)
        src_name = questionary.select("Block to copy:", choices=block_names).ask()
        if src_name is None:
            sys.exit(0)

    if dst_name is None:
        dst_name = questionary.text(
            "New block name (CamelCase):",
            validate=lambda v: bool(re.match(r"^[A-Z][A-Za-z0-9]*$", v)) or "Must be CamelCase",
        ).ask()
        if dst_name is None:
            sys.exit(0)

    if cfg.flat:
        to_group = ""
    elif to_group is None:
        if yes:
            to_group = from_group
        else:
            to_group = questionary.select(
                "Destination group:", choices=group_names, default=from_group
            ).ask()
            if to_group is None:
                sys.exit(0)

    location = f"(group: {to_group})" if to_group else "(flat layout)"
    click.echo(f"\nCopy '{src_name}' → '{dst_name}' {location}")
    if not yes:
        confirm = questionary.confirm("Proceed?", default=True).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = copy_block(
            cfg, from_group, src_name, dst_name, dst_group=to_group, gen_test=gen_test
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Created:")
    for p in written:
        click.echo(f"  {p}")
