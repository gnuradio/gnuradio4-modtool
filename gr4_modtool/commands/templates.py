"""templates command group — list, init, and validate project template overrides."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.fileops import write_text
from gr4_modtool.project.discovery import load_config

CONTEXT_FREE_TEMPLATES: frozenset[str] = frozenset()

_BLOCK_CONTEXT: list[dict] = [
    {"name": "block_name", "type": "str", "dummy": "MyBlock", "desc": "CamelCase struct name"},
    {"name": "namespace", "type": "str", "dummy": "gr::mymod", "desc": "Full C++ namespace"},
    {"name": "description", "type": "str", "dummy": "A block.", "desc": "Doc<> string"},
    {
        "name": "template_params",
        "type": "list",
        "dummy": ["T"],
        "desc": "Template type parameter names",
    },
    {
        "name": "template_decl",
        "type": "str",
        "dummy": "typename T",
        "desc": "template<> declaration string",
    },
    {
        "name": "template_args",
        "type": "str",
        "dummy": "T",
        "desc": "Template argument list for Block<Foo<T>>",
    },
    {
        "name": "template_param_macro",
        "type": "str",
        "dummy": "T",
        "desc": "Comma-separated params for GR_REGISTER_BLOCK",
    },
    {
        "name": "in_ports",
        "type": "list",
        "dummy": [{"name": "in", "type": "T"}],
        "desc": "Input port dicts",
    },
    {
        "name": "out_ports",
        "type": "list",
        "dummy": [{"name": "out", "type": "T"}],
        "desc": "Output port dicts",
    },
    {
        "name": "process_in_ports",
        "type": "list",
        "dummy": [{"name": "in", "type": "T", "arg_name": "input_in"}],
        "desc": "Input port dicts with generated process argument names",
    },
    {
        "name": "process_out_ports",
        "type": "list",
        "dummy": [{"name": "out", "type": "T", "arg_name": "output_out"}],
        "desc": "Output port dicts with generated process argument names",
    },
    {
        "name": "all_port_names",
        "type": "list",
        "dummy": ["in", "out"],
        "desc": "All port names (in + out)",
    },
    {
        "name": "type_list",
        "type": "str",
        "dummy": "float, double",
        "desc": "GR_REGISTER_BLOCK instantiation types",
    },
    {
        "name": "processing_style",
        "type": "str",
        "dummy": "processOne",
        "desc": "processOne or processBulk",
    },
    {
        "name": "uses_complex",
        "type": "bool",
        "dummy": False,
        "desc": "True when type_list includes complex<>",
    },
    {
        "name": "multi_output",
        "type": "bool",
        "dummy": False,
        "desc": "True when block has >1 output port",
    },
    {
        "name": "has_return_value",
        "type": "bool",
        "dummy": True,
        "desc": "True when processOne has output data to return",
    },
    {"name": "return_type", "type": "str", "dummy": "T", "desc": "processOne return type"},
    {"name": "params_str", "type": "str", "dummy": "T x", "desc": "processOne parameter signature"},
    {
        "name": "bulk_params_str",
        "type": "str",
        "dummy": "",
        "desc": "processBulk parameter signature",
    },
    {
        "name": "gr4_include_prefix",
        "type": "str",
        "dummy": "gnuradio-4.0",
        "desc": "Header include prefix",
    },
    {
        "name": "group",
        "type": "str",
        "dummy": "basic",
        "desc": "Group name; empty string in flat mode",
    },
    {"name": "first_type", "type": "str", "dummy": "float", "desc": "First type from type_list"},
    {
        "name": "first_port_type",
        "type": "str",
        "dummy": "float",
        "desc": "Type of first input port",
    },
    {
        "name": "first_out_type",
        "type": "str",
        "dummy": "float",
        "desc": "Type of first output port",
    },
    {
        "name": "needs_graph_test",
        "type": "bool",
        "dummy": False,
        "desc": "True when graph integration test should be generated",
    },
    {"name": "simd", "type": "bool", "dummy": False, "desc": "True when SIMD archetype is used"},
]

TEMPLATE_CONTEXT: dict[str, list[dict] | str] = {
    "block.hpp.j2": _BLOCK_CONTEXT,
    "qa_block.cpp.j2": "block.hpp.j2",
    "bench_block.cpp.j2": "block.hpp.j2",
    "group_CMakeLists.txt.j2": [
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {
            "name": "block_library_name",
            "type": "str",
            "dummy": "GrMyModBasicBlocks",
            "desc": "GNU Radio shared block-library target name",
        },
    ],
    "test_CMakeLists.txt.j2": [
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
    ],
    "toplevel_CMakeLists.txt.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {"name": "version", "type": "str", "dummy": "0.1.0", "desc": "Project version"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {
            "name": "block_library_name",
            "type": "str",
            "dummy": "GrMyModBlocks",
            "desc": "GNU Radio shared block-library target name",
        },
        {"name": "cpp_namespace", "type": "str", "dummy": "gr::mymod", "desc": "C++ namespace"},
    ],
    "package_config.cmake.in.j2": [
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake package and target prefix",
        },
    ],
    "flat_blocks_CMakeLists.txt.j2": [
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
    "gitignore.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
    ],
    "pre_commit_config.yaml.j2": "gitignore.j2",
    "ci_clang.yml.j2": "gitignore.j2",
    "ci_sanitizers.yml.j2": "gitignore.j2",
    "ci_coverage.yml.j2": "gitignore.j2",
    "ci_release.yml.j2": "gitignore.j2",
    "ci_matrix.yml.j2": "gitignore.j2",
    "plot_bench.py.j2": [
        {"name": "block_name", "type": "str", "dummy": "MyBlock", "desc": "CamelCase block name"},
    ],
    "bench_CMakeLists.txt.j2": [
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
    ],
    "devcontainer.json.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {"name": "build_cmake", "type": "bool", "dummy": True, "desc": "Whether CMake is enabled"},
    ],
    "Dockerfile.devcontainer.j2": "devcontainer.json.j2",
    "clang-format.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
    "clang-tidy.j2": "clang-format.j2",
    "cmake_presets.json.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
    ],
    "vscode_settings.json.j2": "cmake_presets.json.j2",
    "vscode_launch.json.j2": "cmake_presets.json.j2",
    "Doxyfile.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {"name": "version", "type": "str", "dummy": "0.1.0", "desc": "Project version"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
}


def _override_dir(project_root: Path) -> Path:
    return project_root / ".gr4modtool" / "templates"


def _resolve(name: str) -> list[dict]:
    """Dereference alias strings in TEMPLATE_CONTEXT."""
    entry = TEMPLATE_CONTEXT.get(name, [])
    if isinstance(entry, str):
        entry = TEMPLATE_CONTEXT.get(entry, [])
    return entry  # type: ignore[return-value]


def list_templates(project_root: Path | None = None) -> dict[str, str]:
    """Map each template filename to its status.

    Status is one of 'built-in', 'overridden' (built-in shadowed by a
    project-local copy), or 'custom' (project-local only). Pass the project
    root to include overrides; without it only built-ins are listed.
    """
    from gr4_modtool.templates import builtin_templates_dir

    builtin_names = sorted(p.name for p in builtin_templates_dir().glob("*.j2"))

    override_names: set[str] = set()
    if project_root is not None:
        od = _override_dir(project_root)
        if od.is_dir():
            override_names = {p.name for p in od.glob("*.j2")}

    statuses = {
        name: ("overridden" if name in override_names else "built-in") for name in builtin_names
    }
    for name in sorted(override_names - set(builtin_names)):
        statuses[name] = "custom"
    return statuses


def init_template_override(project_root: Path, template_name: str, *, force: bool = False) -> Path:
    """Copy a built-in template into <project_root>/.gr4modtool/templates/.

    Returns the destination path.
    Raises ValueError for an unknown template and FileExistsError if the
    override already exists (unless force=True).
    """
    from gr4_modtool.templates import builtin_templates_dir

    builtin_path = builtin_templates_dir() / template_name
    if not builtin_path.exists():
        raise ValueError(f"Unknown template: {template_name}")

    dest_dir = _override_dir(project_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / template_name

    if dest.exists() and not force:
        raise FileExistsError(f"{dest} already exists.")

    write_text(dest, builtin_path.read_text())
    return dest


def check_template_overrides(project_root: Path) -> dict[str, str | None]:
    """Render each override template with dummy context to catch errors early.

    Returns a mapping of template name to error message, or None if it
    rendered cleanly. An empty mapping means no overrides exist.
    """
    from jinja2 import TemplateError

    from gr4_modtool.templates import make_env

    od = _override_dir(project_root)
    if not od.is_dir():
        return {}

    results: dict[str, str | None] = {}
    for path in sorted(od.glob("*.j2")):
        name = path.name
        dummy_ctx = {v["name"]: v["dummy"] for v in _resolve(name)}
        try:
            env = make_env(project_root=project_root)
            env.get_template(name).render(**dummy_ctx)
            results[name] = None
        except TemplateError as exc:
            results[name] = str(exc)
    return results


@click.group("templates")
def cmd() -> None:
    """Manage project-local template overrides."""


@cmd.command("list")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def list_cmd(project_dir: str | None) -> None:
    """List built-in templates and mark any project-local overrides."""
    root: Path | None = None
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
        root = cfg.root
    except FileNotFoundError:
        pass

    styles = {
        "built-in": "[dim]built-in[/dim]",
        "overridden": "[yellow]overridden[/yellow]",
        "custom": "[green]custom[/green]",
    }
    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Template")
    table.add_column("Status")
    for name, status in list_templates(root).items():
        table.add_row(name, styles[status])
    console.print(table)


@cmd.command("init")
@click.argument("template_name")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing override.")
def init_cmd(template_name: str, project_dir: str | None, force: bool) -> None:
    """Copy a built-in template into .gr4modtool/templates/ for editing."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    try:
        dest = init_template_override(cfg.root, template_name, force=force)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        click.echo("Run 'gr4_modtool templates list' to see available templates.", err=True)
        sys.exit(1)
    except FileExistsError as exc:
        click.echo(f"{exc} Use --force to overwrite.", err=True)
        sys.exit(1)

    click.echo(f"Copied {template_name} → {dest.relative_to(cfg.root)}")

    vars_ = _resolve(template_name)
    if vars_:
        click.echo("\nContext variables:")
        for v in vars_:
            click.echo(f"  {v['name']:<22} {v['type']:<6}  {v['desc']}")
    elif template_name in CONTEXT_FREE_TEMPLATES:
        click.echo("\n(No context variables — this template uses no Jinja2 substitutions.)")


@cmd.command("check")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def check_cmd(project_dir: str | None) -> None:
    """Render all override templates with dummy context to catch errors early."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    results = check_template_overrides(cfg.root)
    if not results:
        click.echo("No override templates found.")
        return

    click.echo(f"Checking {len(results)} override template(s)...")
    errors = 0
    for name, error in results.items():
        if error is None:
            click.echo(f"  {name:<40} OK")
        else:
            click.echo(f"  {name:<40} ERROR: {error}")
            errors += 1

    if errors:
        click.echo(f"\n{errors} error(s) found.")
        sys.exit(1)
