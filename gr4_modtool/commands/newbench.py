"""newbench command — add a benchmark for an existing block."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config
from gr4_modtool.templates import render


def _build_bench_ctx(cfg: ProjectConfig, group: str, info: dict) -> dict:
    """Build template context for bench_block.cpp.j2 from parse_header_info output."""
    from gr4_modtool.commands.newblock import _build_template_ctx

    full_ctx = _build_template_ctx(
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
    return full_ctx


def write_plot_script(cfg: ProjectConfig, group: str, block_name: str) -> list[Path]:
    """Generate plot_<BlockName>.py in the benchmarks directory."""
    bench_dir = cfg.group_bench_dir(group)
    bench_dir.mkdir(parents=True, exist_ok=True)
    ctx = {"block_name": block_name}
    path = bench_dir / f"plot_{block_name}.py"
    write_text(path, render("plot_bench.py.j2", ctx, cfg.root))
    return [path]


def write_bench_file(
    cfg: ProjectConfig,
    group: str,
    block_name: str,
    wire_build: bool = False,
    write_plot: bool = False,
) -> list[Path]:
    """Generate bench_<BlockName>.cpp and optionally wire into build system.

    Raises FileNotFoundError if header missing.
    Raises FileExistsError if bench file already exists.
    """
    from gr4_modtool.commands.add_test import parse_header_info

    header = cfg.group_include_dir(group) / f"{block_name}.hpp"
    if not header.exists():
        raise FileNotFoundError(f"Header not found: {header}")

    bench_dir = cfg.group_bench_dir(group)
    bench_file = bench_dir / f"bench_{block_name}.cpp"
    if bench_file.exists():
        raise FileExistsError(f"Benchmark already exists: {bench_file}")

    info = parse_header_info(header)
    ctx = _build_bench_ctx(cfg, group, info)

    bench_dir.mkdir(parents=True, exist_ok=True)
    write_text(bench_file, render("bench_block.cpp.j2", ctx, cfg.root))
    written: list[Path] = [bench_file]

    if wire_build and cfg.build_cmake:
        target_libs = f"{cfg.cmake_prefix}::blocks_{group}_headers"

        bench_cmake = bench_dir / "CMakeLists.txt"
        if not bench_cmake.exists():
            write_text(
                bench_cmake,
                render("bench_CMakeLists.txt.j2", {"group_name": group}, cfg.root),
            )
            written.append(bench_cmake)
        cmake_mod.append_bench_entry(bench_cmake, block_name, target_libs)
        if bench_cmake not in written:
            written.append(bench_cmake)

        group_cmake = cfg.group_path(group) / "CMakeLists.txt"
        if group_cmake.exists():
            cmake_mod.add_bench_subdirectory(group_cmake)
            if group_cmake not in written:
                written.append(group_cmake)

    if write_plot:
        written.extend(write_plot_script(cfg, group, block_name))

    return written


@click.command("newbench")
@click.argument("block_name", required=False)
@click.option("--group", default=None)
@click.option(
    "--wire-build",
    is_flag=True,
    default=False,
    help="Wire into CMake build system (adds ENABLE_BENCHMARKING guard).",
)
@click.option(
    "--plot",
    "gen_plot",
    is_flag=True,
    default=False,
    help="Generate a Python matplotlib plotting companion script.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    block_name: str | None,
    group: str | None,
    wire_build: bool,
    gen_plot: bool,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Add a throughput benchmark for an existing block."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found.", err=True)
        sys.exit(1)

    if group is None:
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
        block_name = questionary.select("Block to benchmark:", choices=block_names).ask()
        if block_name is None:
            sys.exit(0)

    if not wire_build and not yes:
        wire_build = (
            questionary.confirm("Wire into build system (cmake)?", default=False).ask() or False
        )

    if not yes:
        confirm = questionary.confirm(f"Generate bench_{block_name}.cpp?", default=True).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = write_bench_file(
            cfg, group, block_name, wire_build=wire_build, write_plot=gen_plot
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Created:")
    for p in written:
        click.echo(f"  {p}")
