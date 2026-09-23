"""pre-commit command — generate .pre-commit-config.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config
from gr4_modtool.templates import render


def write_precommit(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name}
    path = cfg.root / ".pre-commit-config.yaml"
    write_text(path, render("pre_commit_config.yaml.j2", ctx, cfg.root))
    return [path]


@click.command("pre-commit")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def cmd(project_dir: str | None, yes: bool) -> None:
    """Generate .pre-commit-config.yaml with clang-format and tidy hooks."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if not yes:
        confirm = questionary.confirm("Write .pre-commit-config.yaml?", default=True).ask()
        if not confirm:
            sys.exit(0)

    written = write_precommit(cfg)
    click.echo("Written:")
    for p in written:
        click.echo(f"  {p}")
