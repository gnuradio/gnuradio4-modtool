"""newmod command — scaffold a new GNURadio 4 OOT project."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.log import get_logger, log_exit, log_run
from gr4_modtool.project.discovery import (
    ProjectConfig,
    default_cmake_prefix,
    default_namespace,
    save_config,
)
from gr4_modtool.templates import render

log = get_logger(__name__)


def write_git_init(cfg: ProjectConfig) -> list[Path]:
    """Run git init and write .gitignore. Returns list of created paths."""
    gitignore = cfg.root / ".gitignore"
    write_text(gitignore, render("gitignore.j2", {"project_name": cfg.name}, cfg.root))
    written = [gitignore]

    if shutil.which("git"):
        cmd = ["git", "init", str(cfg.root)]
        log_run(log, cmd)
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
        )
        log_exit(log, cmd, result.returncode)
    else:
        log.warning("git not found on PATH; skipping 'git init'")

    return written


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def _cmake_prefix(name: str) -> str:
    return f"gr4_{_slug(name)}"


def block_library_name(project_name: str, group_name: str = "") -> str:
    """Return the GNU Radio-style block-library target name for an OOT group."""

    def pascal_case(value: str) -> str:
        return "".join(
            part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", value) if part
        )

    return f"Gr{pascal_case(project_name)}{pascal_case(group_name)}Blocks"


def _blocks_cmake(cfg: ProjectConfig) -> str:
    lines = []
    for name in cfg.groups:
        lines.append(f"add_subdirectory({name})")
    lines += [
        "",
        f"add_library({cfg.cmake_prefix}_blocks_headers INTERFACE)",
        f"add_library({cfg.cmake_prefix}::blocks_headers ALIAS {cfg.cmake_prefix}_blocks_headers)",
        "",
        f"target_link_libraries({cfg.cmake_prefix}_blocks_headers INTERFACE",
    ]
    for name in cfg.groups:
        lines.append(f"  {cfg.cmake_prefix}::blocks_{name}_headers")
    lines.append(")")
    lines.append(
        f"install(TARGETS {cfg.cmake_prefix}_blocks_headers EXPORT {cfg.cmake_prefix}Targets)"
    )
    return "\n".join(lines) + "\n"


def _deps_cmake(cmake_prefix: str) -> str:
    return f"""\
include_guard(GLOBAL)

function({cmake_prefix}_resolve_dependencies)
  find_package(gnuradio4 CONFIG REQUIRED)
  find_package(GnuRadioBlockLib CONFIG REQUIRED)
  # GnuRadioBlockLibConfig.cmake sets PARSER_EXECUTABLE (path to the installed
  # gnuradio_4_0_parse_registrations); it must escape this function's scope or
  # the blocklib macros fall back to a gnuradio4 build-tree path.
  set(PARSER_EXECUTABLE "${{PARSER_EXECUTABLE}}" PARENT_SCOPE)
  set(
    GR4_OOT_GNURADIO4_TARGET
    "gnuradio4::gnuradio-core;gnuradio4::gnuradio-blocklib-core"
    PARENT_SCOPE
  )

  if(ENABLE_TESTING)
    find_package(boost_ut CONFIG QUIET)
    if(TARGET boost_ut::ut)
      set(GR4_OOT_BOOST_UT_TARGET boost_ut::ut PARENT_SCOPE)
    else()
      find_path(_boost_ut_include boost/ut.hpp PATH_SUFFIXES boost-ut/include include)
      if(NOT _boost_ut_include)
        message(FATAL_ERROR "boost-ut headers not found (boost/ut.hpp). Install system boost-ut.")
      endif()
      add_library({cmake_prefix}_boost_ut INTERFACE)
      target_include_directories({cmake_prefix}_boost_ut INTERFACE "${{_boost_ut_include}}")
      add_library({cmake_prefix}::boost_ut ALIAS {cmake_prefix}_boost_ut)
      set(GR4_OOT_BOOST_UT_TARGET {cmake_prefix}::boost_ut PARENT_SCOPE)
    endif()
  endif()
endfunction()

function(gr4_modtool_add_ut_test target_name source_file)
  add_executable(${{target_name}} ${{source_file}})
  target_link_libraries(${{target_name}} PRIVATE ${{GR4_OOT_GNURADIO4_TARGET}} ${{GR4_OOT_BOOST_UT_TARGET}})
  add_test(NAME ${{target_name}} COMMAND ${{target_name}})
endfunction()
"""


@click.command("newmod")
@click.option(
    "--project-dir",
    default=None,
    type=click.Path(),
    help="Where to create the project (default: current dir).",
)
@click.option("--name", default=None, help="Project name (skips prompt).")
@click.option(
    "--first-group",
    "first_group_cli",
    default=None,
    help="Name of first block group (overrides prompt).",
)
@click.option("--yes", "-y", is_flag=True, help="Accept all defaults without prompting.")
def cmd(project_dir: str | None, name: str | None, first_group_cli: str | None, yes: bool) -> None:
    """Scaffold a new GNURadio 4 OOT project."""
    dest = Path(project_dir).resolve() if project_dir else Path.cwd()

    def _ask_text(question, *, default: str) -> str:
        if yes:
            return default
        return questionary.text(question, default=default).ask() or default

    def _ask_confirm(question, *, default: bool) -> bool:
        if yes:
            return default
        return questionary.confirm(question, default=default).ask() or False

    if name is None:
        if yes:
            click.echo("--yes requires --name to be specified.", err=True)
            sys.exit(1)
        name = questionary.text(
            "Project name (e.g. myblocks):",
            validate=lambda v: bool(v.strip()) or "Name cannot be empty",
        ).ask()
        if name is None:
            sys.exit(1)

    name = name.strip()
    if not yes and not name.startswith("gr4_"):
        if _ask_confirm(f"Prepend 'gr4_' to name? (→ gr4_{name})", default=True):
            name = f"gr4_{name}"
    version = _ask_text("Version:", default="0.1.0")
    cpp_ns = _ask_text("C++ namespace:", default=default_namespace(name))
    cmake_pfx = _ask_text("CMake prefix:", default=default_cmake_prefix(name))
    gr4_prefix = _ask_text("GNURadio4 include prefix:", default="gnuradio-4.0")

    build_cmake = _ask_confirm("Generate CMake build files?", default=True)
    gen_git = _ask_confirm("Initialize git repository?", default=True)
    gen_devcontainer = _ask_confirm("Generate devcontainer?", default=False)
    gen_clang = _ask_confirm("Generate .clang-format and .clang-tidy config?", default=True)
    gen_ci_clang = _ask_confirm("Generate GitHub Actions CI for clang checks?", default=False)
    gen_presets = _ask_confirm(
        "Generate CMakePresets.json (compiler, asan/ubsan/tsan)?", default=True
    )
    gen_ci_sanitizers = _ask_confirm("Generate GitHub Actions CI for sanitizers?", default=False)
    gen_ci_matrix = _ask_confirm("Generate CI build matrix workflow (gcc×clang)?", default=False)
    gen_vscode = _ask_confirm("Generate VS Code settings (.vscode/)?", default=True)
    gen_ci_coverage = _ask_confirm("Generate CI coverage workflow?", default=False)
    gen_ci_release = _ask_confirm("Generate CI release workflow?", default=False)
    gen_precommit = _ask_confirm("Generate .pre-commit-config.yaml?", default=False)
    gen_doxyfile = _ask_confirm("Generate Doxyfile for Doxygen?", default=False)

    if first_group_cli is not None:
        first_group = first_group_cli
    else:
        first_group = _ask_text("Name of first block group (leave blank to skip):", default="")

    project_root = dest / _slug(name)
    if project_root.exists() and not yes:
        if not questionary.confirm(
            f"Directory {project_root} already exists. Continue?", default=False
        ).ask():
            sys.exit(1)

    # Build config
    groups: dict[str, str] = {}
    flat = not bool(first_group)
    if first_group:
        groups[first_group] = f"blocks/{first_group}"

    cfg = ProjectConfig(
        root=project_root,
        name=name,
        version=version,
        cpp_namespace=cpp_ns,
        cmake_prefix=cmake_pfx,
        gr4_include_prefix=gr4_prefix,
        build_cmake=build_cmake,
        groups=groups,
        flat=flat,
    )

    write_project(
        cfg,
        first_group,
        gen_git=gen_git or False,
        gen_devcontainer=gen_devcontainer or False,
        gen_clang=gen_clang or False,
        gen_ci_clang=gen_ci_clang or False,
        gen_presets=gen_presets or False,
        gen_ci_sanitizers=gen_ci_sanitizers or False,
        gen_ci_matrix=gen_ci_matrix or False,
        gen_vscode=gen_vscode or False,
        gen_ci_coverage=gen_ci_coverage or False,
        gen_ci_release=gen_ci_release or False,
        gen_precommit=gen_precommit or False,
        gen_doxyfile=gen_doxyfile or False,
    )
    click.echo(f"\nCreated project '{name}' at {project_root}")
    click.echo(f"  cd {project_root}")
    if build_cmake:
        if gen_presets:
            click.echo("  cmake --preset default && cmake --build --preset default")
        else:
            click.echo("  cmake -B build && cmake --build build")


def write_project(
    cfg: ProjectConfig,
    first_group: str,
    *,
    gen_git: bool = False,
    gen_devcontainer: bool = False,
    gen_clang: bool = False,
    gen_ci_clang: bool = False,
    gen_presets: bool = False,
    gen_ci_sanitizers: bool = False,
    gen_ci_matrix: bool = False,
    gen_vscode: bool = False,
    gen_ci_coverage: bool = False,
    gen_ci_release: bool = False,
    gen_precommit: bool = False,
    gen_doxyfile: bool = False,
) -> None:
    """Write a complete project skeleton at cfg.root from an already-built config.

    Creates .gr4modtool.toml, build files, the blocks/ tree (with *first_group*
    when given), and any optional tooling selected via the gen_* flags.
    """
    root = cfg.root
    root.mkdir(parents=True, exist_ok=True)

    # .gr4modtool.toml
    save_config(cfg)

    ctx = {
        "project_name": cfg.name,
        "version": cfg.version,
        "cmake_prefix": cfg.cmake_prefix,
        "gr4_include_prefix": cfg.gr4_include_prefix,
        "cpp_namespace": cfg.cpp_namespace,
    }

    # Top-level build files
    if cfg.build_cmake:
        write_text(root / "CMakeLists.txt", render("toplevel_CMakeLists.txt.j2", ctx, root))
        cmake_dir = root / "cmake"
        cmake_dir.mkdir(exist_ok=True)
        write_text(cmake_dir / "Dependencies.cmake", _deps_cmake(cfg.cmake_prefix))
        write_text(
            cmake_dir / f"{cfg.cmake_prefix}Config.cmake.in",
            render("package_config.cmake.in.j2", ctx, root),
        )

    # blocks/ directory
    blocks_dir = root / "blocks"
    blocks_dir.mkdir(exist_ok=True)

    if cfg.flat:
        if cfg.build_cmake:
            write_text(blocks_dir / "CMakeLists.txt", _flat_blocks_cmake(cfg))
        cfg.block_include_dir().mkdir(parents=True, exist_ok=True)
        test_dir = cfg.block_test_dir()
        test_dir.mkdir(parents=True, exist_ok=True)
        if cfg.build_cmake:
            write_text(test_dir / "CMakeLists.txt", f"# Tests for {cfg.name} blocks\n")
    else:
        if cfg.build_cmake:
            write_text(blocks_dir / "CMakeLists.txt", _blocks_cmake(cfg))
        if first_group:
            _create_group_skeleton(cfg, first_group)

    # Git init (done last so all files are present for initial state)
    if gen_git:
        write_git_init(cfg)

    # Devcontainer
    if gen_devcontainer:
        from gr4_modtool.commands.devcontainer import write_devcontainer

        write_devcontainer(cfg)

    # Clang config
    if gen_clang:
        from gr4_modtool.commands.tidy import write_clang_config

        write_clang_config(cfg)

    # CI workflow for clang checks
    if gen_ci_clang:
        from gr4_modtool.commands.tidy import write_ci_clang

        write_ci_clang(cfg)

    # CMakePresets.json
    if gen_presets:
        from gr4_modtool.commands.sanitizers import write_cmake_presets

        write_cmake_presets(cfg)

    # CI workflow for sanitizers
    if gen_ci_sanitizers:
        from gr4_modtool.commands.sanitizers import write_ci_sanitizers

        write_ci_sanitizers(cfg)

    # VS Code settings
    if gen_vscode:
        from gr4_modtool.commands.vscode import write_vscode

        write_vscode(cfg)

    # CI quality workflows
    if gen_ci_coverage:
        from gr4_modtool.commands.ci import write_ci_coverage

        write_ci_coverage(cfg)

    if gen_ci_release:
        from gr4_modtool.commands.ci import write_ci_release

        write_ci_release(cfg)

    if gen_ci_matrix:
        from gr4_modtool.commands.ci import write_ci_matrix

        write_ci_matrix(cfg)

    if gen_precommit:
        from gr4_modtool.commands.precommit import write_precommit

        write_precommit(cfg)

    if gen_doxyfile:
        from gr4_modtool.commands.docs import write_doxyfile

        write_doxyfile(cfg)


def _flat_blocks_cmake(cfg: ProjectConfig) -> str:
    return render(
        "flat_blocks_CMakeLists.txt.j2",
        {
            "cmake_prefix": cfg.cmake_prefix,
            "gr4_include_prefix": cfg.gr4_include_prefix,
            "block_library_name": block_library_name(cfg.name),
        },
        cfg.root,
    )


def _create_group_skeleton(cfg: ProjectConfig, group_name: str) -> None:
    from gr4_modtool.commands.newgroup import write_group_skeleton

    write_group_skeleton(cfg, group_name)
