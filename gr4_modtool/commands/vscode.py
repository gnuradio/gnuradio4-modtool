"""vscode command — scaffold .vscode/settings.json and launch.json."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config
from gr4_modtool.templates import render


def write_vscode(cfg: ProjectConfig) -> list[Path]:
    vscode_dir = cfg.root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    ctx = {"project_name": cfg.name, "cmake_prefix": cfg.cmake_prefix}
    settings = vscode_dir / "settings.json"
    launch = vscode_dir / "launch.json"
    write_text(settings, render("vscode_settings.json.j2", ctx, cfg.root))
    write_text(launch, render("vscode_launch.json.j2", ctx, cfg.root))
    return [settings, launch]


@click.command("vscode")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def cmd(project_dir: str | None, yes: bool) -> None:
    """Generate .vscode/settings.json and .vscode/launch.json."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if not yes:
        confirm = questionary.confirm(
            "Write .vscode/settings.json and .vscode/launch.json?", default=True
        ).ask()
        if not confirm:
            sys.exit(0)

    written = write_vscode(cfg)
    click.echo("Written:")
    for p in written:
        click.echo(f"  {p}")
