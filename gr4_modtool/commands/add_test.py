"""add-test command — generate a test for an existing block that has none."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import discover_groups, load_config
from gr4_modtool.templates import render


def parse_header_info(header_path: Path) -> dict:
    """Parse a GNURadio 4 block header and return metadata dict.

    Returns keys: block_name, namespace, template_params, in_ports, out_ports,
                  type_list, processing_style, description.
    Raises ValueError if block_name or template_params cannot be found.
    """
    text = header_path.read_text()

    m = re.search(r"struct\s+(\w+)\s*:\s*Block<", text)
    if not m:
        raise ValueError(f"Cannot find 'struct Foo : Block<' in {header_path}")
    block_name = m.group(1)

    tp_match = re.search(r"template\s*<([^>]+)>", text)
    if not tp_match:
        raise ValueError(f"Cannot find template declaration in {header_path}")
    raw_params = tp_match.group(1)
    template_params = [
        p.strip().removeprefix("typename").strip() for p in raw_params.split(",") if p.strip()
    ]

    in_ports = [
        {"type": t.strip(), "name": n.strip()}
        for t, n in re.findall(r"PortIn<([^>]+)>\s+(\w+)", text)
    ]
    out_ports = [
        {"type": t.strip(), "name": n.strip()}
        for t, n in re.findall(r"PortOut<([^>]+)>\s+(\w+)", text)
    ]

    tl_match = re.search(r"GR_REGISTER_BLOCK\([^,]+,[^,]+,[^,]+,\s*\[([^\]]+)\]", text)
    type_list = tl_match.group(1).strip() if tl_match else "float, double"

    processing_style = "processBulk" if "processBulk" in text else "processOne"

    ns_match = re.search(r"namespace\s+([\w:]+)\s*\{", text)
    namespace = ns_match.group(1) if ns_match else ""

    desc_match = re.search(r'Doc<"([^"]*)">', text)
    description = desc_match.group(1) if desc_match else ""

    return {
        "block_name": block_name,
        "namespace": namespace,
        "template_params": template_params,
        "in_ports": in_ports,
        "out_ports": out_ports,
        "type_list": type_list,
        "processing_style": processing_style,
        "description": description,
    }


def parse_annotated_params(text: str) -> list[dict]:
    """Extract Annotated<> member declarations from a block header.

    Handles the gnuradio4 form ``Annotated<T, "name", ..., Doc<"desc">> name``
    as well as the legacy ``Annotated<T, Doc<"desc">> name``.
    """
    member_re = re.compile(r"Annotated<(.+)>\s+(\w+)\s*(?:\{|=)")
    params = []
    for line in text.splitlines():
        m = member_re.search(line)
        if not m:
            continue
        inner, name = m.group(1), m.group(2)
        doc = re.search(r'Doc<"([^"]*)">', inner)
        params.append(
            {
                "type": inner.split(",", 1)[0].strip(),
                "description": doc.group(1) if doc else "",
                "name": name,
            }
        )
    return params


def write_test_for_block(cfg, group: str, block_name: str) -> list[Path]:
    """Generate qa_<BlockName>.cpp and update build files.

    Raises FileNotFoundError if header is missing.
    Raises FileExistsError if qa_*.cpp already exists.
    """
    from gr4_modtool.commands.newblock import _build_template_ctx

    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    if not header.exists():
        raise FileNotFoundError(f"Header not found: {header}")

    test = cfg.group_test_dir(group) / f"qa_{block_name}.cpp"
    if test.exists():
        raise FileExistsError(f"Test already exists: {test}")

    info = parse_header_info(header)
    ctx = _build_template_ctx(
        block_name=info["block_name"],
        namespace=info["namespace"],
        group=group,
        description=info["description"],
        template_params=info["template_params"],
        in_ports=info["in_ports"],
        out_ports=info["out_ports"],
        type_list=info["type_list"],
        processing_style=info["processing_style"],
        gr4_include_prefix=cfg.gr4_include_prefix,
    )

    write_text(test, render("qa_block.cpp.j2", ctx, cfg.root))
    written: list[Path] = [test]

    cmake_test = cfg.group_test_dir(group) / "CMakeLists.txt"
    if cfg.build_cmake and cmake_test.exists():
        target_libs = (
            f"{cfg.cmake_prefix}::blocks_headers"
            if not group
            else f"{cfg.cmake_prefix}::blocks_{group}_headers"
        )
        cmake_mod.append_test_entry(cmake_test, block_name, target_libs)
        written.append(cmake_test)

    return written


@click.command("add-test")
@click.argument("block_name", required=False)
@click.option("--group", default=None)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(block_name: str | None, group: str | None, project_dir: str | None, yes: bool) -> None:
    """Generate a test file for an existing block that has none."""
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

    # Only offer blocks that have no existing test
    testless = [
        b.name
        for b in group_info.blocks
        if not (cfg.group_test_dir(group) / f"qa_{b.name}.cpp").exists()
    ]

    if block_name is None:
        if not testless:
            click.echo(f"All blocks in '{group}' already have tests.")
            sys.exit(0)
        block_name = questionary.select("Block (no test yet):", choices=testless).ask()
        if block_name is None:
            sys.exit(0)

    if not yes:
        confirm = questionary.confirm(
            f"Generate test for '{block_name}' in group '{group}'?", default=True
        ).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = write_test_for_block(cfg, group, block_name)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Created:")
    for p in written:
        click.echo(f"  {p}")
