"""ci command — write CI quality workflows (coverage and release)."""

from __future__ import annotations

from pathlib import Path

import click

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import ProjectConfig, load_config
from gr4_modtool.templates import render


def write_ci_coverage(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name}
    ci_dir = cfg.root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    path = ci_dir / "coverage.yml"
    write_text(path, render("ci_coverage.yml.j2", ctx, cfg.root))
    return [path]


def write_ci_release(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name}
    ci_dir = cfg.root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    path = ci_dir / "release.yml"
    write_text(path, render("ci_release.yml.j2", ctx, cfg.root))
    return [path]


def write_ci_matrix(cfg: ProjectConfig) -> list[Path]:
    ctx = {"project_name": cfg.name}
    ci_dir = cfg.root / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    path = ci_dir / "matrix.yml"
    write_text(path, render("ci_matrix.yml.j2", ctx, cfg.root))
    return [path]


@click.command("ci")
@click.option("--coverage/--no-coverage", default=False, help="Write coverage CI workflow.")
@click.option("--release/--no-release", default=False, help="Write release CI workflow.")
@click.option(
    "--matrix/--no-matrix", default=False, help="Write compiler×build-type matrix CI workflow."
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(coverage: bool, release: bool, matrix: bool, project_dir: str | None) -> None:
    """Write GitHub Actions CI quality workflows."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if not coverage and not release and not matrix:
        click.echo("Specify --coverage, --release, and/or --matrix to generate CI workflows.")
        return

    written: list[Path] = []
    if coverage:
        written.extend(write_ci_coverage(cfg))
    if release:
        written.extend(write_ci_release(cfg))
    if matrix:
        written.extend(write_ci_matrix(cfg))

    click.echo("Written:")
    for p in written:
        click.echo(f"  {p}")
