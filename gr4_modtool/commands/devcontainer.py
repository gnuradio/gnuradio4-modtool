"""devcontainer command — add a .devcontainer/ to a project."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config
from gr4_modtool.templates import render


def write_devcontainer(cfg: ProjectConfig) -> list[Path]:
    """Write .devcontainer/devcontainer.json and Dockerfile. Returns created paths."""
    dc_dir = cfg.root / ".devcontainer"
    dc_dir.mkdir(exist_ok=True)

    ctx = {
        "project_name": cfg.name,
        "cmake_prefix": cfg.cmake_prefix,
        "gr4_include_prefix": cfg.gr4_include_prefix,
        "build_cmake": cfg.build_cmake,
    }

    json_path = dc_dir / "devcontainer.json"
    dockerfile_path = dc_dir / "Dockerfile"

    write_text(json_path, render("devcontainer.json.j2", ctx, cfg.root))
    write_text(dockerfile_path, render("Dockerfile.devcontainer.j2", ctx, cfg.root))

    return [json_path, dockerfile_path]


@click.command("devcontainer")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option(
    "--yes", "-y", is_flag=True, help="Skip confirmation if .devcontainer/ already exists."
)
def cmd(project_dir: str | None, yes: bool) -> None:
    """Add a .devcontainer/ (devcontainer.json + Dockerfile) to an existing project."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    dc_dir = cfg.root / ".devcontainer"

    if dc_dir.exists() and not yes:
        if not questionary.confirm(f"{dc_dir} already exists. Overwrite?", default=False).ask():
            sys.exit(0)

    written = write_devcontainer(cfg)
    click.echo("Created:")
    for p in written:
        click.echo(f"  {p}")
