"""list / ls command — machine-readable project inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rel(root: Path, path: Path) -> str:
    """Return path relative to root, or str(path) if path is not under root."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Core collector
# ---------------------------------------------------------------------------


def collect_inventory(
    cfg: ProjectConfig,
    *,
    group_filter: str | None = None,
    include_blocks: bool = True,
    include_tests: bool = True,
    include_benchmarks: bool = True,
    verbose: bool = False,
) -> dict:
    """Return the full project inventory as a plain dict.

    All paths are relative to cfg.root.  Headers that cannot be parsed are
    skipped with a warning on stderr.
    """
    root = cfg.root
    groups_raw = discover_groups(cfg)
    if group_filter:
        groups_raw = [g for g in groups_raw if g.name == group_filter]

    groups_out: list[dict] = []

    for grp in groups_raw:
        test_dir = cfg.group_test_dir(grp.name)
        bench_dir = cfg.group_bench_dir(grp.name)

        test_files = sorted(test_dir.glob("qa_*.cpp")) if test_dir.exists() else []
        bench_files = sorted(bench_dir.glob("bench_*.cpp")) if bench_dir.exists() else []

        # lower-case block name → path (O(1) has_test / has_bench lookup)
        tested: dict[str, Path] = {tf.stem[3:].lower(): tf for tf in test_files}
        benched: dict[str, Path] = {bf.stem[6:].lower(): bf for bf in bench_files}
        # lower-case → canonical block name (for test/bench → block association)
        block_names: dict[str, str] = {b.name.lower(): b.name for b in grp.blocks}

        g_entry: dict = {
            "name": grp.name,
            "path": _rel(root, grp.path),
            "blocks": [],
            "tests": [],
            "benchmarks": [],
        }

        # ------------------------------------------------------------------ #
        # Blocks
        # ------------------------------------------------------------------ #
        if include_blocks:
            for block in grp.blocks:
                key = block.name.lower()
                b_entry: dict = {
                    "name": block.name,
                    "header": _rel(root, block.path),
                    "has_test": key in tested,
                    "test_path": _rel(root, tested[key]) if key in tested else None,
                    "has_bench": key in benched,
                    "bench_path": _rel(root, benched[key]) if key in benched else None,
                }
                if verbose:
                    try:
                        from gr4_modtool.commands.add_test import parse_header_info

                        info = parse_header_info(block.path)
                        b_entry["namespace"] = info["namespace"]
                        b_entry["template_params"] = info["template_params"]
                        b_entry["type_list"] = info["type_list"]
                        b_entry["in_ports"] = info["in_ports"]
                        b_entry["out_ports"] = info["out_ports"]
                        b_entry["processing_style"] = info["processing_style"]
                    except Exception as exc:  # noqa: BLE001
                        click.echo(f"Warning: cannot parse {block.path.name}: {exc}", err=True)
                g_entry["blocks"].append(b_entry)

        # ------------------------------------------------------------------ #
        # Tests
        # ------------------------------------------------------------------ #
        if include_tests:
            for tf in test_files:
                stem_lower = tf.stem[3:].lower()
                g_entry["tests"].append(
                    {
                        "name": tf.stem,
                        "path": _rel(root, tf),
                        "block": block_names.get(stem_lower, ""),
                    }
                )

        # ------------------------------------------------------------------ #
        # Benchmarks
        # ------------------------------------------------------------------ #
        if include_benchmarks:
            for bf in bench_files:
                stem_lower = bf.stem[6:].lower()
                g_entry["benchmarks"].append(
                    {
                        "name": bf.stem,
                        "path": _rel(root, bf),
                        "block": block_names.get(stem_lower, ""),
                    }
                )

        groups_out.append(g_entry)

    return {
        "project": {
            "name": cfg.name,
            "version": cfg.version,
            "namespace": cfg.cpp_namespace,
            "cmake_prefix": cfg.cmake_prefix,
            "build_cmake": cfg.build_cmake,
            "flat_mode": cfg.flat,
        },
        "groups": groups_out,
    }


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _render_json(data: dict) -> str:
    return json.dumps(data, indent=2)


def _render_yaml(data: dict) -> str:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("PyYAML is required for YAML output.  pip install PyYAML") from exc
    return yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _toml_str(v: str) -> str:
    """Escape backslashes and double-quotes for a TOML quoted string value."""
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _render_toml(data: dict) -> str:
    """Render inventory as flat TOML with top-level [[blocks]], [[tests]], [[benchmarks]]."""
    lines: list[str] = []

    proj = data["project"]
    lines += [
        "[project]",
        f'name = "{_toml_str(proj["name"])}"',
        f'version = "{_toml_str(proj["version"])}"',
        f'namespace = "{_toml_str(proj["namespace"])}"',
        f'cmake_prefix = "{_toml_str(proj["cmake_prefix"])}"',
        f"build_cmake = {'true' if proj['build_cmake'] else 'false'}",
        f"flat_mode = {'true' if proj['flat_mode'] else 'false'}",
        "",
    ]

    for g in data["groups"]:
        lines += [
            "[[groups]]",
            f'name = "{_toml_str(g["name"])}"',
            f'path = "{_toml_str(g["path"])}"',
            "",
        ]

    for g in data["groups"]:
        for b in g.get("blocks", []):
            lines.append("[[blocks]]")
            lines.append(f'group = "{_toml_str(g["name"])}"')
            lines.append(f'name = "{_toml_str(b["name"])}"')
            lines.append(f'header = "{_toml_str(b["header"])}"')
            lines.append(f"has_test = {'true' if b['has_test'] else 'false'}")
            if b["test_path"] is not None:
                lines.append(f'test_path = "{_toml_str(b["test_path"])}"')
            lines.append(f"has_bench = {'true' if b['has_bench'] else 'false'}")
            if b["bench_path"] is not None:
                lines.append(f'bench_path = "{_toml_str(b["bench_path"])}"')
            if "namespace" in b:
                lines.append(f'namespace = "{_toml_str(b["namespace"])}"')
            if "template_params" in b:
                params = ", ".join(f'"{_toml_str(p)}"' for p in b["template_params"])
                lines.append(f"template_params = [{params}]")
            if "type_list" in b:
                lines.append(f'type_list = "{_toml_str(b["type_list"])}"')
            if "processing_style" in b:
                lines.append(f'processing_style = "{_toml_str(b["processing_style"])}"')
            if "in_ports" in b:
                inline = ", ".join(
                    "{" + f'name = "{_toml_str(p["name"])}", type = "{_toml_str(p["type"])}"' + "}"
                    for p in b["in_ports"]
                )
                lines.append(f"in_ports = [{inline}]")
            if "out_ports" in b:
                inline = ", ".join(
                    "{" + f'name = "{_toml_str(p["name"])}", type = "{_toml_str(p["type"])}"' + "}"
                    for p in b["out_ports"]
                )
                lines.append(f"out_ports = [{inline}]")
            lines.append("")

    for g in data["groups"]:
        for t in g.get("tests", []):
            lines += [
                "[[tests]]",
                f'group = "{_toml_str(g["name"])}"',
                f'name = "{_toml_str(t["name"])}"',
                f'path = "{_toml_str(t["path"])}"',
                f'block = "{_toml_str(t["block"])}"',
                "",
            ]

    for g in data["groups"]:
        for bm in g.get("benchmarks", []):
            lines += [
                "[[benchmarks]]",
                f'group = "{_toml_str(g["name"])}"',
                f'name = "{_toml_str(bm["name"])}"',
                f'path = "{_toml_str(bm["path"])}"',
                f'block = "{_toml_str(bm["block"])}"',
                "",
            ]

    return "\n".join(lines)


def _tick(v: bool) -> str:
    return "[green]✓[/green]" if v else "[dim]–[/dim]"


def _render_table(data: dict, console: Console | None = None) -> None:
    if console is None:
        console = Console()

    proj = data["project"]
    console.print(
        f"\n[bold]Project:[/bold] {proj['name']}  [dim]v{proj['version']}[/dim]"
        f"  [dim]{proj['namespace']}[/dim]"
    )
    console.print()

    groups = data["groups"]

    all_blocks = [(g["name"], b) for g in groups for b in g.get("blocks", [])]
    if all_blocks:
        tbl = Table(title="Blocks", box=box.SIMPLE, show_header=True, header_style="bold cyan")
        tbl.add_column("Group", style="green")
        tbl.add_column("Block", style="white")
        tbl.add_column("Test", justify="center")
        tbl.add_column("Bench", justify="center")
        prev_group = None
        for gname, b in all_blocks:
            tbl.add_row(
                gname if gname != prev_group else "",
                b["name"],
                _tick(b["has_test"]),
                _tick(b["has_bench"]),
            )
            prev_group = gname
        console.print(tbl)

    all_tests = [(g["name"], t) for g in groups for t in g.get("tests", [])]
    if all_tests:
        tbl = Table(title="Tests", box=box.SIMPLE, show_header=True, header_style="bold cyan")
        tbl.add_column("Group", style="green")
        tbl.add_column("Test", style="white")
        tbl.add_column("Block", style="dim")
        prev_group = None
        for gname, t in all_tests:
            tbl.add_row(
                gname if gname != prev_group else "",
                t["name"],
                t["block"] or "(unmatched)",
            )
            prev_group = gname
        console.print(tbl)

    all_benches = [(g["name"], bm) for g in groups for bm in g.get("benchmarks", [])]
    if all_benches:
        tbl = Table(title="Benchmarks", box=box.SIMPLE, show_header=True, header_style="bold cyan")
        tbl.add_column("Group", style="green")
        tbl.add_column("Benchmark", style="white")
        tbl.add_column("Block", style="dim")
        prev_group = None
        for gname, bm in all_benches:
            tbl.add_row(
                gname if gname != prev_group else "",
                bm["name"],
                bm["block"] or "(unmatched)",
            )
            prev_group = gname
        console.print(tbl)

    if not all_blocks and not all_tests and not all_benches:
        console.print("[dim](no items)[/dim]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("list")
@click.option(
    "--format",
    "fmt",
    default=None,
    type=click.Choice(["table", "json", "yaml", "toml"], case_sensitive=False),
    help="Output format (default: table).",
)
@click.option(
    "--json", "use_json", is_flag=True, default=False, help="Shorthand for --format json."
)
@click.option(
    "--yaml", "use_yaml", is_flag=True, default=False, help="Shorthand for --format yaml."
)
@click.option(
    "--toml", "use_toml", is_flag=True, default=False, help="Shorthand for --format toml."
)
@click.option("--group", "group_filter", default=None, help="Restrict output to one group.")
@click.option("--blocks/--no-blocks", default=True, help="Include blocks (default: on).")
@click.option("--tests/--no-tests", default=True, help="Include tests (default: on).")
@click.option(
    "--benchmarks/--no-benchmarks", default=True, help="Include benchmarks (default: on)."
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Include ports, types, and namespace in block records.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    fmt: str | None,
    use_json: bool,
    use_yaml: bool,
    use_toml: bool,
    group_filter: str | None,
    blocks: bool,
    tests: bool,
    benchmarks: bool,
    verbose: bool,
    project_dir: str | None,
) -> None:
    """List all groups, blocks, tests, and benchmarks in the project."""
    shorthand_count = sum([use_json, use_yaml, use_toml])
    if shorthand_count > 1:
        raise click.UsageError("Only one of --json, --yaml, --toml may be specified.")
    if shorthand_count == 1 and fmt is not None:
        raise click.UsageError("--format cannot be combined with --json / --yaml / --toml.")

    if use_json:
        fmt = "json"
    elif use_yaml:
        fmt = "yaml"
    elif use_toml:
        fmt = "toml"
    elif fmt is None:
        fmt = "table"

    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    data = collect_inventory(
        cfg,
        group_filter=group_filter,
        include_blocks=blocks,
        include_tests=tests,
        include_benchmarks=benchmarks,
        verbose=verbose,
    )

    try:
        if fmt == "json":
            click.echo(_render_json(data))
        elif fmt == "yaml":
            click.echo(_render_yaml(data))
        elif fmt == "toml":
            click.echo(_render_toml(data))
        else:
            _render_table(data)
    except ImportError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
