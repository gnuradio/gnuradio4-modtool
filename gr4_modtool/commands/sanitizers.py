"""sanitizers / presets command — write CMakePresets.json and sanitizer CI workflow."""

from __future__ import annotations

from pathlib import Path

import click

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config
from gr4_modtool.templates import render


def write_cmake_presets(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name, "cmake_prefix": cfg.cmake_prefix}
    path = cfg.root / "CMakePresets.json"
    write_text(path, render("cmake_presets.json.j2", ctx, cfg.root))
    return [path]


def write_ci_sanitizers(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name}
    ci_dir = cfg.root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    path = ci_dir / "sanitizers.yml"
    write_text(path, render("ci_sanitizers.yml.j2", ctx, cfg.root))
    return [path]


@click.command("presets")
@click.option(
    "--init",
    "do_init",
    is_flag=True,
    default=False,
    help="Write CMakePresets.json and sanitizer CI workflow.",
)
@click.option(
    "--presets-only",
    is_flag=True,
    default=False,
    help="Write only CMakePresets.json (no CI workflow).",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(do_init: bool, presets_only: bool, project_dir: str | None) -> None:
    """Write CMakePresets.json (asan/ubsan/tsan) and optional CI workflow."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if not do_init and not presets_only:
        click.echo(
            "Use --init to write both CMakePresets.json and sanitizer CI, or --presets-only for presets only."
        )
        return

    written: list[Path] = []
    written.extend(write_cmake_presets(cfg))
    if do_init and not presets_only:
        written.extend(write_ci_sanitizers(cfg))

    click.echo("Written:")
    for p in written:
        click.echo(f"  {p}")
