"""init command — bootstrap .gr4modtool.toml for an existing project."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.project.discovery import (
    CONFIG_FILE,
    ProjectConfig,
    default_cmake_prefix,
    default_namespace,
    save_config,
)

_GR4_BLOCK_MARKERS = ("GR_REGISTER_BLOCK", "Block<", ": public Block")


def _is_gr4_block(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
        return any(marker in text for marker in _GR4_BLOCK_MARKERS)
    except OSError:
        return False


def _scan_group_include(include_dir: Path) -> list[str]:
    """Return stem names of .hpp files under include_dir."""
    if not include_dir.is_dir():
        return []
    return sorted(p.stem for p in include_dir.glob("*.hpp"))


def _detect_include_prefix(include_dir: Path) -> str | None:
    """Return the first non-empty child directory name of include_dir."""
    if not include_dir.is_dir():
        return None
    for child in sorted(include_dir.iterdir()):
        if child.is_dir() and any(child.iterdir()):
            return child.name
    return None


def _scan_blocks_root(
    project_dir: Path, blocks_root: Path, groups: dict, group_blocks: dict, prefix_ref: list
) -> None:
    """Scan a blocks/ directory, populating groups and group_blocks in-place."""
    rel_base = blocks_root.relative_to(project_dir)
    for group_dir in sorted(blocks_root.iterdir()):
        if not group_dir.is_dir():
            continue
        include_dir = group_dir / "include"
        if not include_dir.is_dir():
            continue
        group_name = group_dir.name
        groups[group_name] = str(rel_base / group_name)

        if not prefix_ref[0] or prefix_ref[0] == "gnuradio-4.0":
            detected = _detect_include_prefix(include_dir)
            if detected:
                prefix_ref[0] = detected

        prefix = prefix_ref[0] or "gnuradio-4.0"
        block_include = include_dir / prefix / group_name
        group_blocks[group_name] = _scan_group_include(block_include)


def scan_project_dir(project_dir: Path) -> dict:
    """Auto-detect project metadata from directory structure.

    Returns dict with keys:
      name, version, groups, group_blocks, gr4_include_prefix, has_cmake.
    groups maps group_name -> relative path string.
    group_blocks maps group_name -> list of block stem names.
    """
    result: dict = {
        "name": None,
        "version": "0.1.0",
        "groups": {},
        "group_blocks": {},
        "gr4_include_prefix": "gnuradio-4.0",
        "has_cmake": False,
    }

    cmake_path = project_dir / "CMakeLists.txt"
    result["has_cmake"] = cmake_path.exists()

    if cmake_path.exists():
        text = cmake_path.read_text()
        m = re.search(r"project\s*\(\s*([^\s)\n]+)", text)
        if m:
            result["name"] = m.group(1).strip('"').strip("'")
        v = re.search(r"project\s*\([^)]*\bVERSION\s+([\d.]+)", text, re.IGNORECASE)
        if v:
            result["version"] = v.group(1)

    prefix_ref = [result["gr4_include_prefix"]]

    # Layout 1: blocks/ at project root (standard)
    blocks_dir = project_dir / "blocks"
    if blocks_dir.is_dir():
        _scan_blocks_root(
            project_dir, blocks_dir, result["groups"], result["group_blocks"], prefix_ref
        )

    # Layout 2: src/blocks/
    if not result["groups"]:
        src_blocks = project_dir / "src" / "blocks"
        if src_blocks.is_dir():
            _scan_blocks_root(
                project_dir, src_blocks, result["groups"], result["group_blocks"], prefix_ref
            )

    # Layout 3: flat include/<prefix>/<group>/ at root
    if not result["groups"]:
        root_include = project_dir / "include"
        if root_include.is_dir():
            for prefix_dir in sorted(root_include.iterdir()):
                if not prefix_dir.is_dir():
                    continue
                for group_dir in sorted(prefix_dir.iterdir()):
                    if not group_dir.is_dir():
                        continue
                    result["groups"][group_dir.name] = f"include/{prefix_dir.name}/{group_dir.name}"
                    result["group_blocks"][group_dir.name] = _scan_group_include(group_dir)
                    if prefix_ref[0] == "gnuradio-4.0":
                        prefix_ref[0] = prefix_dir.name

    result["gr4_include_prefix"] = prefix_ref[0]
    return result


def write_init_config(
    project_dir: Path,
    name: str,
    version: str,
    cpp_namespace: str,
    cmake_prefix: str,
    gr4_include_prefix: str,
    build_cmake: bool,
    groups: dict[str, str],
    *,
    force: bool = False,
) -> Path:
    """Write .gr4modtool.toml. Raises FileExistsError if it already exists (unless force=True)."""
    config_path = project_dir / CONFIG_FILE
    if config_path.exists() and not force:
        raise FileExistsError(f"{config_path} already exists.")

    cfg = ProjectConfig(
        root=project_dir,
        name=name,
        version=version,
        cpp_namespace=cpp_namespace,
        cmake_prefix=cmake_prefix,
        gr4_include_prefix=gr4_include_prefix,
        build_cmake=build_cmake,
        groups=groups,
    )
    save_config(cfg)
    return config_path


def _format_scan_report(root: Path, detected: dict) -> str:
    lines = [f"\nDetected project at: {root}"]
    lines.append(f"  Name:    {detected['name'] or root.name}")
    lines.append(f"  Version: {detected['version']}")
    lines.append(f"  Prefix:  {detected['gr4_include_prefix']}")
    build_tags = []
    if detected["has_cmake"]:
        build_tags.append("cmake")
    lines.append(f"  Build:   {', '.join(build_tags) or '(none detected)'}")
    lines.append("")
    if detected["groups"]:
        lines.append("  Groups and blocks found:")
        for g, blocks in sorted(detected["group_blocks"].items()):
            block_list = ", ".join(blocks[:6]) + ("…" if len(blocks) > 6 else "")
            lines.append(
                f"    {g:<12} ({len(blocks)} block{'s' if len(blocks) != 1 else ''}): {block_list}"
            )
    else:
        lines.append("  No groups detected.")
    return "\n".join(lines)


@click.command("init")
@click.option(
    "--project-dir", default=None, type=click.Path(exists=True), help="Project root (default: cwd)."
)
@click.option("--yes", "-y", is_flag=True, help="Accept all detected values without prompting.")
@click.option("--dry-run", is_flag=True, help="Print detected structure without writing config.")
@click.option("--force", is_flag=True, help="Overwrite existing .gr4modtool.toml.")
def cmd(project_dir: str | None, yes: bool, dry_run: bool, force: bool) -> None:
    """Bootstrap .gr4modtool.toml for an existing project by scanning its layout."""
    root = Path(project_dir).resolve() if project_dir else Path.cwd()

    config_path = root / CONFIG_FILE
    if config_path.exists() and not force and not dry_run:
        click.echo(
            f"Error: {config_path} already exists. Use --force to overwrite or 'gr4_modtool info' to inspect.",
            err=True,
        )
        sys.exit(1)

    detected = scan_project_dir(root)
    click.echo(_format_scan_report(root, detected))

    if dry_run:
        click.echo("\n(dry-run: no files written)")
        return

    if yes:
        name = detected["name"] or root.name
        version = detected["version"]
        cpp_namespace = default_namespace(name)
        cmake_prefix = default_cmake_prefix(name)
        gr4_include_prefix = detected["gr4_include_prefix"]
        build_cmake = detected["has_cmake"]
        groups = detected["groups"]
    else:
        click.echo()
        name = questionary.text("Project name:", default=detected["name"] or root.name).ask()
        if name is None:
            sys.exit(0)

        version = (
            questionary.text("Version:", default=detected["version"]).ask() or detected["version"]
        )

        default_ns = default_namespace(name)
        cpp_namespace = questionary.text("C++ namespace:", default=default_ns).ask() or default_ns

        default_pfx = default_cmake_prefix(name)
        cmake_prefix = questionary.text("CMake prefix:", default=default_pfx).ask() or default_pfx

        gr4_include_prefix = (
            questionary.text(
                "GNURadio4 include prefix:", default=detected["gr4_include_prefix"]
            ).ask()
            or detected["gr4_include_prefix"]
        )

        build_cmake = questionary.confirm("CMake build files?", default=detected["has_cmake"]).ask()
        groups = detected["groups"]

    try:
        path = write_init_config(
            root,
            name,
            version,
            cpp_namespace,
            cmake_prefix,
            gr4_include_prefix,
            build_cmake,
            groups,
            force=force,
        )
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    total_blocks = sum(len(b) for b in detected["group_blocks"].values())
    click.echo(f"\nCreated {path}")
    click.echo(f"  {len(groups)} group(s) registered: {', '.join(sorted(groups)) or '(none)'}")
    click.echo(f"  {total_blocks} block(s) found total")
    click.echo("  Run 'gr4_modtool info' to verify.")
