"""export-spec command — emit YAML spec files from existing block headers."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from gr4_modtool.commands.add_test import parse_header_info
from gr4_modtool.commands.newblock import ARCHETYPES
from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import discover_groups, load_config

try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
    _yaml = None  # type: ignore[assignment]


def infer_archetype(
    in_ports: list[dict],
    out_ports: list[dict],
    processing_style: str,
) -> str | None:
    """Return the archetype name if ports+style exactly match a known archetype."""
    for name, spec in ARCHETYPES.items():
        if (
            spec["in_ports"] == in_ports
            and spec["out_ports"] == out_ports
            and spec["processing_style"] == processing_style
        ):
            return name
    return None


def header_to_spec_entry(header_path: Path, group_name: str) -> dict:
    """Parse a block header and return a spec-compatible dict.

    Raises ValueError (propagated from parse_header_info) if the file is not a
    recognisable block header.
    """
    info = parse_header_info(header_path)

    archetype = infer_archetype(info["in_ports"], info["out_ports"], info["processing_style"])

    entry: dict = {
        "group": group_name,
        "block_name": info["block_name"],
        "description": info["description"],
        "template_params": info["template_params"],
        "type_list": info["type_list"],
        "gen_test": True,
    }

    if archetype is not None:
        entry["archetype"] = archetype
    else:
        entry["in_ports"] = info["in_ports"]
        entry["out_ports"] = info["out_ports"]
        entry["processing_style"] = info["processing_style"]

    return entry


def export_spec(
    cfg,
    group_filter: str | None,
    output: str,
    out_dir: Path,
) -> list[Path]:
    """Export block specs from cfg to YAML files.

    output: 'per-block', 'per-group', or 'project'
    Returns list of written file paths.
    """
    if not _YAML_AVAILABLE:
        raise RuntimeError(
            "PyYAML is required for export-spec. Install it with: pip install PyYAML"
        )

    groups = discover_groups(cfg)
    if group_filter:
        groups = [g for g in groups if g.name == group_filter]

    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    if output == "project":
        all_entries: list[dict] = []
        for group in groups:
            include_dir = cfg.group_include_dir(group.name)
            for hpp in sorted(include_dir.glob("*.hpp")):
                try:
                    all_entries.append(header_to_spec_entry(hpp, group.name))
                except ValueError as exc:
                    click.echo(f"Warning: skipping {hpp.name}: {exc}", err=True)
        if all_entries:
            dest = out_dir / "blocks.yaml"
            write_text(dest, _yaml.dump(all_entries, sort_keys=False, allow_unicode=True))
            written.append(dest)

    elif output == "per-group":
        for group in groups:
            include_dir = cfg.group_include_dir(group.name)
            entries: list[dict] = []
            for hpp in sorted(include_dir.glob("*.hpp")):
                try:
                    entries.append(header_to_spec_entry(hpp, group.name))
                except ValueError as exc:
                    click.echo(f"Warning: skipping {hpp.name}: {exc}", err=True)
            if entries:
                dest = out_dir / f"{group.name}_blocks.yaml"
                write_text(dest, _yaml.dump(entries, sort_keys=False, allow_unicode=True))
                written.append(dest)

    elif output == "per-block":
        for group in groups:
            include_dir = cfg.group_include_dir(group.name)
            group_out = out_dir / group.name
            group_out.mkdir(parents=True, exist_ok=True)
            for hpp in sorted(include_dir.glob("*.hpp")):
                try:
                    entry = header_to_spec_entry(hpp, group.name)
                except ValueError as exc:
                    click.echo(f"Warning: skipping {hpp.name}: {exc}", err=True)
                    continue
                dest = group_out / f"{entry['block_name']}.yaml"
                write_text(dest, _yaml.dump(entry, sort_keys=False, allow_unicode=True))
                written.append(dest)

    return written


@click.command("export-spec")
@click.option("--group", "group_filter", default=None, help="Export only blocks from this group.")
@click.option(
    "--output",
    "output_mode",
    default="per-group",
    type=click.Choice(["per-block", "per-group", "project"]),
    show_default=True,
    help="Granularity of output files.",
)
@click.option(
    "--out-dir",
    default="specs",
    show_default=True,
    type=click.Path(),
    help="Directory to write spec files.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    group_filter: str | None,
    output_mode: str,
    out_dir: str,
    project_dir: str | None,
) -> None:
    """Export block headers as YAML spec files (inverse of newblock --spec)."""
    if not _YAML_AVAILABLE:
        click.echo("Error: PyYAML is required. Install it with: pip install PyYAML", err=True)
        sys.exit(1)

    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        written = export_spec(cfg, group_filter, output_mode, Path(out_dir))
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not written:
        click.echo("No blocks found to export.")
        return

    block_count = 0
    for p in written:
        import yaml as _y

        data = _y.safe_load(p.read_text())
        if isinstance(data, list):
            block_count += len(data)
        else:
            block_count += 1

    paths_str = ", ".join(str(p) for p in written)
    click.echo(f"Exported {block_count} block(s) → {paths_str}")
