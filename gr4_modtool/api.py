"""gr4_modtool public API.

Stable re-exports for use as a library.  Import from here rather than from
internal command modules — the paths below are the supported surface.

Every CLI command has a functional counterpart here (the ``rename`` and
``rename-block`` commands share :func:`rename_block`; ``info``/``ls``/``list``

Two layers are provided:

* **Functions** — take a :class:`ProjectConfig` (or paths) as arguments and
  return plain data or the list of paths they wrote.
* **:class:`Project`** — an object-oriented facade bundling a config with one
  method per command.

Example usage::

    from gr4_modtool.api import Project, load_config, write_block_files

    # functional
    cfg = load_config(Path("/path/to/mymod"))
    write_block_files(cfg, entry)

    # facade
    proj = Project.load("/path/to/mymod")
    proj.copy_block("basic", "Foo", "Bar")
    issues = proj.audit()

Nothing here prints to the terminal; to see what the tool is doing, turn on
logging once at start-up::

    from gr4_modtool.api import configure_logging

    configure_logging(verbose=1)          # every file written, every command run
    configure_logging(verbose=2, log_file="build.log")
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Dependencies (add-dep)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.add_dep import add_cmake_dep

# ---------------------------------------------------------------------------
# Tests for existing blocks (add-test) and header parsing
# ---------------------------------------------------------------------------
from gr4_modtool.commands.add_test import (
    parse_annotated_params,
    parse_header_info,
    write_test_for_block,
)

# ---------------------------------------------------------------------------
# Build / test / coverage (build, test, coverage)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.build import run_build

# ---------------------------------------------------------------------------
# Audit / check
# ---------------------------------------------------------------------------
from gr4_modtool.commands.check import (
    BlockIssue,
    audit_project,
)

# ---------------------------------------------------------------------------
# CI workflows (ci)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.ci import (
    write_ci_coverage,
    write_ci_matrix,
    write_ci_release,
)
from gr4_modtool.commands.coverage import (
    detect_coverage_tool,
    regenerate_coverage_report,
    run_coverage,
)

# ---------------------------------------------------------------------------
# Block lifecycle (cp, mv, rm, rename, rename-block, rename-group, newparam)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.cp import copy_block

# ---------------------------------------------------------------------------
# Tooling config writers (devcontainer, vscode, presets, pre-commit, tidy)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.devcontainer import write_devcontainer

# ---------------------------------------------------------------------------
# Docs (docs)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.docs import build_catalog, write_doxyfile

# ---------------------------------------------------------------------------
# Environment diagnosis (doctor)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.doctor import DoctorResult, run_doctor

# ---------------------------------------------------------------------------
# Header inspection (export-spec, lint-headers, show)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.export_spec import (
    export_spec,
    header_to_spec_entry,
    infer_archetype,
)

# ---------------------------------------------------------------------------
# Formatting (format)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.format import format_files

# ---------------------------------------------------------------------------
# Project bootstrap (init)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.init import scan_project_dir, write_init_config
from gr4_modtool.commands.lint_headers import (
    LintIssue,
    lint_header,
    lint_headers,
)

# ---------------------------------------------------------------------------
# Inventory (ls, list, info)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.ls import collect_inventory
from gr4_modtool.commands.mv import move_block

# ---------------------------------------------------------------------------
# Benchmarks (newbench)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newbench import write_bench_file, write_plot_script

# ---------------------------------------------------------------------------
# Block scaffolding (newblock)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newblock import (
    ARCHETYPES,
    load_spec,
    validate_spec_entry,
    write_block_files,
)

# ---------------------------------------------------------------------------
# Group scaffolding (newgroup)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newgroup import add_group, write_group_skeleton

# ---------------------------------------------------------------------------
# Project scaffolding (newmod)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newmod import (
    block_library_name,
    write_git_init,
    write_project,
)
from gr4_modtool.commands.newparam import add_param

# ---------------------------------------------------------------------------
# GNURadio 3 porting (port)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.port import parse_gr3_python, port_gr3_block
from gr4_modtool.commands.precommit import write_precommit

# ---------------------------------------------------------------------------
# Publishing (publish)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.publish import PreFlightResult, pre_flight
from gr4_modtool.commands.rename_block import rename_block
from gr4_modtool.commands.rename_group import rename_group
from gr4_modtool.commands.rm import remove_block
from gr4_modtool.commands.run_test import run_block_test
from gr4_modtool.commands.sanitizers import write_ci_sanitizers, write_cmake_presets

# ---------------------------------------------------------------------------
# OOT registry search (search)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.search import search_registry
from gr4_modtool.commands.show import show_block

# ---------------------------------------------------------------------------
# Project status (status)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.status import GroupSummary, ProjectStatus, gather_status

# ---------------------------------------------------------------------------
# Test synchronisation (sync)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.sync import SyncAction, apply_sync, plan_sync

# ---------------------------------------------------------------------------
# Template overrides (templates)
# ---------------------------------------------------------------------------
from gr4_modtool.commands.templates import (
    check_template_overrides,
    init_template_override,
    list_templates,
)
from gr4_modtool.commands.tidy import run_tidy, write_ci_clang, write_clang_config

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
from gr4_modtool.commands.validate import (
    ValidationIssue,
    validate_project,
)

# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------
from gr4_modtool.commands.version_bump import apply_version_bump
from gr4_modtool.commands.vscode import write_vscode

# ---------------------------------------------------------------------------
# Object-oriented facade
# ---------------------------------------------------------------------------
from gr4_modtool.facade import Project

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
from gr4_modtool.log import configure_logging, get_logger

# ---------------------------------------------------------------------------
# Project config
# ---------------------------------------------------------------------------
from gr4_modtool.project.discovery import (
    BlockInfo,
    GroupInfo,
    ProjectConfig,
    discover_groups,
    find_project_root,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# Public surface declaration
# ---------------------------------------------------------------------------
__all__ = [
    # facade
    "Project",
    # logging
    "configure_logging",
    "get_logger",
    # config
    "BlockInfo",
    "GroupInfo",
    "ProjectConfig",
    "discover_groups",
    "find_project_root",
    "load_config",
    "save_config",
    # project bootstrap / scaffolding
    "scan_project_dir",
    "write_init_config",
    "write_project",
    "write_git_init",
    "block_library_name",
    # block scaffolding
    "ARCHETYPES",
    "load_spec",
    "validate_spec_entry",
    "write_block_files",
    # group scaffolding
    "add_group",
    "write_group_skeleton",
    # block lifecycle
    "copy_block",
    "move_block",
    "remove_block",
    "rename_block",
    "rename_group",
    "add_param",
    # tests & benchmarks
    "write_test_for_block",
    "write_bench_file",
    "write_plot_script",
    # header parsing / inspection
    "parse_header_info",
    "parse_annotated_params",
    "export_spec",
    "header_to_spec_entry",
    "infer_archetype",
    "show_block",
    "LintIssue",
    "lint_header",
    "lint_headers",
    # audit
    "BlockIssue",
    "audit_project",
    # inventory
    "collect_inventory",
    # status
    "GroupSummary",
    "ProjectStatus",
    "gather_status",
    # validation
    "ValidationIssue",
    "validate_project",
    # sync
    "SyncAction",
    "plan_sync",
    "apply_sync",
    # build / test / coverage
    "run_build",
    "run_block_test",
    "run_coverage",
    "detect_coverage_tool",
    "regenerate_coverage_report",
    # quality tooling
    "format_files",
    "run_tidy",
    "write_clang_config",
    "write_ci_clang",
    "write_cmake_presets",
    "write_ci_sanitizers",
    "write_ci_coverage",
    "write_ci_release",
    "write_ci_matrix",
    "write_devcontainer",
    "write_vscode",
    "write_precommit",
    # docs
    "write_doxyfile",
    "build_catalog",
    # dependencies
    "add_cmake_dep",
    # porting
    "parse_gr3_python",
    "port_gr3_block",
    # environment
    "DoctorResult",
    "run_doctor",
    # publishing
    "PreFlightResult",
    "pre_flight",
    # registry search
    "search_registry",
    # templates
    "list_templates",
    "init_template_override",
    "check_template_overrides",
    # versioning
    "apply_version_bump",
]
