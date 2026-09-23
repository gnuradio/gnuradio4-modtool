"""version-bump command — increment or set the project version across all version-bearing files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import load_config, save_config


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse 'X.Y.Z' into (X, Y, Z). Raises ValueError if not valid semver."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if not m:
        raise ValueError(f"Version '{version}' is not in X.Y.Z format")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _bump_version(current: str, part: str) -> str:
    """Return the new version string given current version and part to bump."""
    major, minor, patch = _parse_semver(current)
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def _update_cmake(cmake_path: Path, old: str, new: str) -> bool:
    """Replace VERSION in project() call. Returns True if the file was changed."""
    if not cmake_path.exists():
        return False
    text = cmake_path.read_text()
    pattern = rf"(project\([^)]*\bVERSION\s+){re.escape(old)}"
    new_text = re.sub(pattern, rf"\g<1>{new}", text)
    if new_text == text:
        return False
    write_text(cmake_path, new_text)
    return True


def _update_doxyfile(doxy_path: Path, old: str, new: str) -> bool:
    """Replace PROJECT_NUMBER in Doxyfile. Returns True if the file was changed."""
    if not doxy_path.exists():
        return False
    text = doxy_path.read_text()
    pattern = rf'(PROJECT_NUMBER\s*=\s*"){re.escape(old)}"'
    new_text = re.sub(pattern, rf'\g<1>{new}"', text)
    if new_text == text:
        return False
    write_text(doxy_path, new_text)
    return True


def _would_change_cmake(cmake_path: Path, old: str) -> bool:
    if not cmake_path.exists():
        return False
    return bool(re.search(rf"project\([^)]*\bVERSION\s+{re.escape(old)}", cmake_path.read_text()))


def _would_change_doxyfile(doxy_path: Path, old: str) -> bool:
    if not doxy_path.exists():
        return False
    return bool(re.search(rf'PROJECT_NUMBER\s*=\s*"{re.escape(old)}"', doxy_path.read_text()))


def apply_version_bump(cfg, new_version: str) -> list[Path]:
    """Apply new_version to all version-bearing files. Returns list of modified paths."""
    old = cfg.version
    root = cfg.root
    modified: list[Path] = []

    cfg.version = new_version
    save_config(cfg)
    modified.append(root / ".gr4modtool.toml")

    if _update_cmake(root / "CMakeLists.txt", old, new_version):
        modified.append(root / "CMakeLists.txt")
    if _update_doxyfile(root / "Doxyfile", old, new_version):
        modified.append(root / "Doxyfile")

    return modified


@click.command("version-bump")
@click.option("--major", "part", flag_value="major", help="Bump major version (X+1.0.0).")
@click.option("--minor", "part", flag_value="minor", help="Bump minor version (X.Y+1.0).")
@click.option("--patch", "part", flag_value="patch", help="Bump patch version (X.Y.Z+1).")
@click.option(
    "--set", "set_version", default=None, metavar="VERSION", help="Set to an exact X.Y.Z value."
)
@click.option("--yes", "-y", is_flag=True, default=False, help="Apply without confirmation.")
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Show what would change without modifying any files.",
)
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def cmd(
    part: str | None,
    set_version: str | None,
    yes: bool,
    dry_run: bool,
    project_dir: str | None,
) -> None:
    """Bump or set the project version across all version-bearing files."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    current = cfg.version

    try:
        _parse_semver(current)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if set_version is not None and part is not None:
        click.echo("Error: --set cannot be combined with --major/--minor/--patch.", err=True)
        sys.exit(1)

    if set_version is not None:
        try:
            _parse_semver(set_version)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        new_version = set_version.strip()
    elif part is not None:
        new_version = _bump_version(current, part)
    else:
        choice = questionary.select(
            "Which part to bump?",
            choices=["patch", "minor", "major"],
        ).ask()
        if choice is None:
            sys.exit(0)
        new_version = _bump_version(current, choice)

    click.echo(f"  {current}  →  {new_version}")

    if dry_run:
        root = cfg.root
        would_change = [root / ".gr4modtool.toml"]
        if _would_change_cmake(root / "CMakeLists.txt", current):
            would_change.append(root / "CMakeLists.txt")
        if _would_change_doxyfile(root / "Doxyfile", current):
            would_change.append(root / "Doxyfile")
        click.echo("Would update:")
        for path in would_change:
            click.echo(f"  {path.relative_to(root)}")
        return

    if not yes:
        confirmed = questionary.confirm("Apply this version change?", default=True).ask()
        if not confirmed:
            sys.exit(0)

    modified = apply_version_bump(cfg, new_version)
    click.echo("Updated:")
    for path in modified:
        click.echo(f"  {path.relative_to(cfg.root)}")
