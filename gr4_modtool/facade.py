"""Object-oriented facade over the gr4_modtool command functions.

:class:`Project` bundles a :class:`ProjectConfig` with one method per CLI
command, so library consumers can drive a project without threading the
config through every call::

    from gr4_modtool.api import Project

    proj = Project.load("/path/to/mymod")
    proj.new_group("filters")
    proj.copy_block("basic", "Gain", "Gain2")
    issues = proj.audit()

Every method is a thin delegation to the functional layer in
:mod:`gr4_modtool.api`; the return values are identical.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from gr4_modtool.project.discovery import (
    ProjectConfig,
    default_cmake_prefix,
    default_namespace,
    discover_groups,
    load_config,
    save_config,
)

if TYPE_CHECKING:
    from gr4_modtool.commands.check import BlockIssue
    from gr4_modtool.commands.doctor import DoctorResult
    from gr4_modtool.commands.lint_headers import LintIssue
    from gr4_modtool.commands.publish import PreFlightResult
    from gr4_modtool.commands.status import ProjectStatus
    from gr4_modtool.commands.sync import SyncAction
    from gr4_modtool.commands.validate import ValidationIssue
    from gr4_modtool.project.discovery import GroupInfo


class Project:
    """A GNURadio 4 OOT project, wrapping a :class:`ProjectConfig`."""

    def __init__(self, cfg: ProjectConfig) -> None:
        self.cfg = cfg

    def __repr__(self) -> str:
        return f"Project(name={self.cfg.name!r}, root={str(self.cfg.root)!r})"

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: Path | str | None = None) -> Project:
        """Load an existing project by walking upward from *path* (or cwd)."""
        return cls(load_config(Path(path) if path is not None else None))

    @classmethod
    def create(
        cls,
        root: Path | str,
        name: str,
        *,
        version: str = "0.1.0",
        cpp_namespace: str | None = None,
        cmake_prefix: str | None = None,
        gr4_include_prefix: str = "gnuradio-4.0",
        first_group: str = "",
        build_cmake: bool = True,
        **gen_options: bool,
    ) -> Project:
        """Scaffold a new project at *root* (the ``newmod`` command).

        *gen_options* forwards ``gen_git``, ``gen_devcontainer``, ``gen_clang``,
        ``gen_ci_clang``, ``gen_presets``, ``gen_ci_sanitizers``,
        ``gen_ci_matrix``, ``gen_vscode``, ``gen_ci_coverage``,
        ``gen_ci_release``, ``gen_precommit``, and ``gen_doxyfile`` to
        :func:`gr4_modtool.api.write_project`.
        """
        from gr4_modtool.commands.newmod import write_project

        root = Path(root)
        groups = {first_group: f"blocks/{first_group}"} if first_group else {}
        cfg = ProjectConfig(
            root=root,
            name=name,
            version=version,
            cpp_namespace=cpp_namespace or default_namespace(name),
            cmake_prefix=cmake_prefix or default_cmake_prefix(name),
            gr4_include_prefix=gr4_include_prefix,
            build_cmake=build_cmake,
            groups=groups,
            flat=not first_group,
        )
        write_project(cfg, first_group, **gen_options)
        return cls(cfg)

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #

    @property
    def root(self) -> Path:
        return self.cfg.root

    @property
    def name(self) -> str:
        return self.cfg.name

    @property
    def version(self) -> str:
        return self.cfg.version

    def save(self) -> None:
        """Write the (possibly modified) config back to .gr4modtool.toml."""
        save_config(self.cfg)

    # ------------------------------------------------------------------ #
    # Inspection
    # ------------------------------------------------------------------ #

    def groups(self) -> list[GroupInfo]:
        """Scan the filesystem for groups and their blocks (``ls``)."""
        return discover_groups(self.cfg)

    def inventory(self, **kwargs: Any) -> dict:
        """Full project inventory as plain data (``ls``/``info``)."""
        from gr4_modtool.commands.ls import collect_inventory

        return collect_inventory(self.cfg, **kwargs)

    def status(self) -> ProjectStatus:
        """Snapshot of groups, test coverage, and tooling files (``status``)."""
        from gr4_modtool.commands.status import gather_status

        return gather_status(self.cfg)

    def audit(self, groups: list[str] | None = None) -> list[BlockIssue]:
        """Check blocks for missing macros/tests/build entries (``check``)."""
        from gr4_modtool.commands.check import audit_project

        return audit_project(self.cfg, groups)

    def validate(self, **kwargs: Any) -> list[ValidationIssue]:
        """Deep structure/header/build validation (``validate``)."""
        from gr4_modtool.commands.validate import validate_project

        return validate_project(self.cfg, **kwargs)

    def lint_headers(self, groups: list[str] | None = None) -> list[LintIssue]:
        """Style-lint block headers (``lint-headers``)."""
        from gr4_modtool.commands.lint_headers import lint_headers

        return lint_headers(self.cfg, groups)

    def doctor(self) -> list[DoctorResult]:
        """Diagnose the development environment (``doctor``)."""
        from gr4_modtool.commands.doctor import run_doctor

        return run_doctor(self.cfg)

    def pre_flight(self) -> list[PreFlightResult]:
        """Run publish pre-flight checks (``publish``)."""
        from gr4_modtool.commands.publish import pre_flight

        return pre_flight(self.cfg)

    def catalog(self) -> str:
        """Markdown catalog of all blocks (``docs --catalog``)."""
        from gr4_modtool.commands.docs import build_catalog

        return build_catalog(self.cfg)

    def export_spec(
        self,
        group: str | None = None,
        *,
        output: str = "per-block",
        out_dir: Path | None = None,
    ) -> list[Path]:
        """Export block YAML specs (``export-spec``)."""
        from gr4_modtool.commands.export_spec import export_spec

        return export_spec(self.cfg, group, output, out_dir or self.cfg.root / "specs")

    # ------------------------------------------------------------------ #
    # Scaffolding
    # ------------------------------------------------------------------ #

    def new_group(self, name: str) -> None:
        """Add a block group: skeleton, config entry, build wiring (``newgroup``)."""
        from gr4_modtool.commands.newgroup import add_group

        add_group(self.cfg, name)

    def new_block(
        self,
        *,
        block_name: str,
        group_name: str = "",
        description: str = "",
        archetype: str = "sync",
        template_params: list[str] | None = None,
        in_ports: list[dict] | None = None,
        out_ports: list[dict] | None = None,
        processing_style: str | None = None,
        type_list: str = "float, double",
        gen_test: bool = True,
        simd: bool = False,
    ) -> list[Path]:
        """Generate a block (``newblock``).

        Only *block_name* is required (plus *group_name* for grouped
        projects). Ports and processing style default from *archetype* (one
        of :data:`gr4_modtool.api.ARCHETYPES`); explicitly passed values win.
        The keywords match the spec-entry shape, so a spec dict applies
        directly: ``proj.new_block(**entry)``.
        """
        from gr4_modtool.commands.newblock import (
            ARCHETYPES,
            validate_spec_entry,
            write_block_files,
        )

        if archetype not in ARCHETYPES:
            raise ValueError(
                f"Unknown archetype {archetype!r} — expected one of {sorted(ARCHETYPES)}."
            )
        arch = ARCHETYPES[archetype]
        entry = {
            "group_name": group_name,
            "block_name": block_name,
            "description": description,
            "template_params": template_params if template_params is not None else ["T"],
            "in_ports": in_ports if in_ports is not None else [dict(p) for p in arch["in_ports"]],
            "out_ports": out_ports
            if out_ports is not None
            else [dict(p) for p in arch["out_ports"]],
            "processing_style": processing_style or arch["processing_style"],
            "type_list": type_list,
            "gen_test": gen_test,
            "simd": simd,
        }
        validate_spec_entry(entry, flat=self.cfg.flat)
        return write_block_files(self.cfg, entry)

    def new_blocks_from_spec(self, spec_path: Path | str) -> list[Path]:
        """Generate all blocks defined in a YAML spec file (``newblock --spec``)."""
        from gr4_modtool.commands.newblock import load_spec, validate_spec_entry, write_block_files

        written: list[Path] = []
        for entry in load_spec(Path(spec_path)):
            validate_spec_entry(entry, flat=self.cfg.flat)
            written.extend(write_block_files(self.cfg, entry))
        return written

    def add_test(self, group: str, block_name: str) -> list[Path]:
        """Generate a test for an existing block (``add-test``)."""
        from gr4_modtool.commands.add_test import write_test_for_block

        return write_test_for_block(self.cfg, group, block_name)

    def new_bench(
        self, group: str, block_name: str, *, wire_build: bool = False, plot: bool = False
    ) -> list[Path]:
        """Generate a benchmark for an existing block (``newbench``)."""
        from gr4_modtool.commands.newbench import write_bench_file

        return write_bench_file(self.cfg, group, block_name, wire_build=wire_build, write_plot=plot)

    def add_param(
        self,
        group: str,
        block_name: str,
        param_name: str,
        param_type: str,
        description: str,
        default_value: str = "{}",
    ) -> list[Path]:
        """Insert an Annotated<> parameter into a block header (``newparam``)."""
        from gr4_modtool.commands.newparam import add_param

        return add_param(
            self.cfg, group, block_name, param_name, param_type, description, default_value
        )

    def port_gr3(self, group: str, source_path: Path | str) -> list[Path]:
        """Port a GNURadio 3 Python block to a gr4 header (``port``)."""
        from gr4_modtool.commands.port import port_gr3_block

        return port_gr3_block(self.cfg, group, Path(source_path))

    # ------------------------------------------------------------------ #
    # Block lifecycle
    # ------------------------------------------------------------------ #

    def copy_block(
        self,
        src_group: str,
        src_name: str,
        dst_name: str,
        *,
        dst_group: str | None = None,
        gen_test: bool = False,
    ) -> list[Path]:
        """Copy a block, optionally into another group (``cp``)."""
        from gr4_modtool.commands.cp import copy_block

        return copy_block(self.cfg, src_group, src_name, dst_name, dst_group, gen_test)

    def move_block(self, src_group: str, block_name: str, dst_group: str) -> list[Path]:
        """Move a block between groups (``mv``)."""
        from gr4_modtool.commands.mv import move_block

        return move_block(self.cfg, src_group, block_name, dst_group)

    def remove_block(self, group: str, block_name: str) -> list[Path]:
        """Delete a block and its test/build entries (``rm``)."""
        from gr4_modtool.commands.rm import remove_block

        return remove_block(self.cfg, group, block_name)

    def rename_block(self, group: str, old_name: str, new_name: str) -> list[Path]:
        """Rename a block within a group (``rename``/``rename-block``)."""
        from gr4_modtool.commands.rename_block import rename_block

        return rename_block(self.cfg, group, old_name, new_name)

    def rename_group(self, old_name: str, new_name: str) -> list[Path]:
        """Rename a group and update all references (``rename-group``)."""
        from gr4_modtool.commands.rename_group import rename_group

        return rename_group(self.cfg, old_name, new_name)

    def show_block(self, group: str, block_name: str, *, show_test: bool = False) -> None:
        """Print a block header (or test) with highlighting (``show``)."""
        from gr4_modtool.commands.show import show_block

        show_block(self.cfg, group, block_name, show_test)

    # ------------------------------------------------------------------ #
    # Build, test, quality
    # ------------------------------------------------------------------ #

    def build(self, build_dir: Path | str = "build", **kwargs: Any) -> int:
        """Configure and build the project; returns the exit code (``build``)."""
        from gr4_modtool.commands.build import run_build

        return run_build(self.cfg.root, self.cfg.root / build_dir, **kwargs)

    def run_test(
        self, block_name: str, *, build_dir: Path | str = "build", verbose: bool = False
    ) -> int:
        """Run one block's qa test via ctest; returns the exit code (``test``)."""
        from gr4_modtool.commands.run_test import run_block_test

        return run_block_test(self.cfg.root, self.cfg.root / build_dir, block_name, verbose=verbose)

    def coverage(self, build_dir: Path | str = "build-coverage", **kwargs: Any) -> int:
        """Build, test, and report coverage; returns the exit code (``coverage``)."""
        from gr4_modtool.commands.coverage import run_coverage

        kwargs.setdefault("open_browser", False)
        return run_coverage(self.cfg.root, self.cfg.root / build_dir, **kwargs)

    def format(
        self,
        groups: list[str] | None = None,
        *,
        check_only: bool = False,
        style: str | None = None,
    ) -> int:
        """clang-format headers and tests; returns the exit code (``format``)."""
        from gr4_modtool.commands.format import format_files

        return format_files(self.cfg, groups, check_only=check_only, style=style)

    def tidy(
        self,
        build_dir: Path | str = "build",
        groups: list[str] | None = None,
        *,
        fix: bool = False,
    ) -> int:
        """clang-tidy block headers; returns the exit code (``tidy``)."""
        from gr4_modtool.commands.tidy import run_tidy

        return run_tidy(self.cfg, self.cfg.root / build_dir, groups, fix=fix)

    # ------------------------------------------------------------------ #
    # Sync
    # ------------------------------------------------------------------ #

    def sync_plan(self, *, prune: bool = False) -> list[SyncAction]:
        """Plan test/build reconciliation actions (``sync``)."""
        from gr4_modtool.commands.sync import plan_sync

        return plan_sync(self.cfg, prune)

    def sync_apply(self, actions: list[SyncAction]) -> list[str]:
        """Apply previously planned sync actions; returns warnings (``sync``)."""
        from gr4_modtool.commands.sync import apply_sync

        return apply_sync(self.cfg, actions)

    # ------------------------------------------------------------------ #
    # Tooling writers
    # ------------------------------------------------------------------ #

    def write_devcontainer(self) -> list[Path]:
        """Write .devcontainer/ (``devcontainer``)."""
        from gr4_modtool.commands.devcontainer import write_devcontainer

        return write_devcontainer(self.cfg)

    def write_vscode(self) -> list[Path]:
        """Write .vscode/ settings (``vscode``)."""
        from gr4_modtool.commands.vscode import write_vscode

        return write_vscode(self.cfg)

    def write_precommit(self) -> list[Path]:
        """Write .pre-commit-config.yaml (``pre-commit``)."""
        from gr4_modtool.commands.precommit import write_precommit

        return write_precommit(self.cfg)

    def write_clang_config(self) -> list[Path]:
        """Write .clang-format and .clang-tidy (``tidy --init``)."""
        from gr4_modtool.commands.tidy import write_clang_config

        return write_clang_config(self.cfg)

    def write_cmake_presets(self) -> list[Path]:
        """Write CMakePresets.json (``presets``)."""
        from gr4_modtool.commands.sanitizers import write_cmake_presets

        return write_cmake_presets(self.cfg)

    def write_ci(
        self,
        *,
        clang: bool = False,
        sanitizers: bool = False,
        coverage: bool = False,
        release: bool = False,
        matrix: bool = False,
    ) -> list[Path]:
        """Write the selected GitHub Actions workflows (``ci``)."""
        from gr4_modtool.commands.ci import write_ci_coverage, write_ci_matrix, write_ci_release
        from gr4_modtool.commands.sanitizers import write_ci_sanitizers
        from gr4_modtool.commands.tidy import write_ci_clang

        written: list[Path] = []
        if clang:
            written.extend(write_ci_clang(self.cfg))
        if sanitizers:
            written.extend(write_ci_sanitizers(self.cfg))
        if coverage:
            written.extend(write_ci_coverage(self.cfg))
        if release:
            written.extend(write_ci_release(self.cfg))
        if matrix:
            written.extend(write_ci_matrix(self.cfg))
        return written

    def write_doxyfile(self) -> list[Path]:
        """Write a Doxyfile (``docs --init``)."""
        from gr4_modtool.commands.docs import write_doxyfile

        return write_doxyfile(self.cfg)

    # ------------------------------------------------------------------ #
    # Dependencies, templates, versioning
    # ------------------------------------------------------------------ #

    def add_dependency(
        self, var_name: str, *, pkg_config: str | None = None, cmake_package: str | None = None
    ) -> list[Path]:
        """Add a dependency to cmake/Dependencies.cmake (``add-dep``)."""
        from gr4_modtool.commands.add_dep import add_cmake_dep

        if not pkg_config and not cmake_package:
            raise ValueError("Provide pkg_config or cmake_package.")
        deps_cmake = self.cfg.root / "cmake" / "Dependencies.cmake"
        add_cmake_dep(deps_cmake, var_name, pkg_config, cmake_package)
        return [deps_cmake]

    def list_templates(self) -> dict[str, str]:
        """Template name → 'built-in' / 'overridden' / 'custom' (``templates list``)."""
        from gr4_modtool.commands.templates import list_templates

        return list_templates(self.cfg.root)

    def init_template_override(self, template_name: str, *, force: bool = False) -> Path:
        """Copy a built-in template into the project for editing (``templates init``)."""
        from gr4_modtool.commands.templates import init_template_override

        return init_template_override(self.cfg.root, template_name, force=force)

    def check_templates(self) -> dict[str, str | None]:
        """Render overrides with dummy context; name → error or None (``templates check``)."""
        from gr4_modtool.commands.templates import check_template_overrides

        return check_template_overrides(self.cfg.root)

    def bump_version(self, new_version: str) -> list[Path]:
        """Update the version everywhere it appears (``version-bump``)."""
        from gr4_modtool.commands.version_bump import apply_version_bump

        return apply_version_bump(self.cfg, new_version)
