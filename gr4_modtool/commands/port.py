"""port command — import a GNURadio 3.x Python block and scaffold a gr4 header."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.commands.newblock import ARCHETYPES, write_block_files
from gr4_modtool.project.discovery import ProjectConfig, discover_groups, load_config

_GR3_BASE_MAP: dict[str, str | None] = {
    "sync_block": "filter",
    "decim_block": "decimator",
    "interp_block": "interpolator",
    "basic_block": None,
}

_NUMPY_TYPE_MAP: dict[str, str] = {
    "np.float32": "float",
    "numpy.float32": "float",
    "np.float64": "double",
    "numpy.float64": "double",
    "np.complex64": "std::complex<float>",
    "numpy.complex64": "std::complex<float>",
    "np.complex128": "std::complex<double>",
    "numpy.complex128": "std::complex<double>",
    "np.int32": "int32_t",
    "numpy.int32": "int32_t",
    "np.int64": "int64_t",
    "numpy.int64": "int64_t",
    "np.uint8": "uint8_t",
    "numpy.uint8": "uint8_t",
    "np.uint32": "uint32_t",
    "numpy.uint32": "uint32_t",
}


def _node_to_str(node: ast.expr) -> str:
    """Convert an AST node to a readable string for type resolution."""
    return ast.unparse(node)


def _to_camel(name: str) -> str:
    """Convert snake_case or any_name to CamelCase."""
    return "".join(part.capitalize() for part in re.split(r"[_\-\s]+", name) if part)


def _extract_sigs(call_node: ast.Call) -> tuple[list[str], list[str]]:
    """Extract in_sig and out_sig lists from a gr3 __init__ super-call."""
    in_sigs: list[str] = []
    out_sigs: list[str] = []

    for kw in call_node.keywords:
        if kw.arg == "in_sig":
            if isinstance(kw.value, ast.List):
                in_sigs = [_node_to_str(elt) for elt in kw.value.elts]
        elif kw.arg == "out_sig":
            if isinstance(kw.value, ast.List):
                out_sigs = [_node_to_str(elt) for elt in kw.value.elts]

    return in_sigs, out_sigs


def _extract_params(init_func: ast.FunctionDef) -> list[tuple[str, str]]:
    """Extract (name, default_str) for non-self, non-special __init__ parameters."""
    args = init_func.args
    params: list[tuple[str, str]] = []

    # defaults align to the end of args.args
    n_args = len(args.args)
    n_defaults = len(args.defaults)
    offset = n_args - n_defaults

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        default_idx = i - offset
        if default_idx >= 0:
            default_str = _node_to_str(args.defaults[default_idx])
        else:
            default_str = "{}"
        params.append((arg.arg, default_str))

    return params


def parse_gr3_python(source: str) -> dict:
    """Parse a GNURadio 3.x Python block source.

    Returns:
        block_name: CamelCase name
        gr3_base:   "sync_block" | "decim_block" | "interp_block" | "basic_block" | None
        in_sigs:    list of numpy type strings (e.g. ["np.float32"])
        out_sigs:   list of numpy type strings
        params:     list of (name, default_str) from __init__ (excluding self)
        docstring:  class-level docstring or ""

    Raises ValueError if no gr3 block class is found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Could not parse Python source: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Detect gr3 base class
        gr3_base: str | None = None
        for base in node.bases:
            base_str = _node_to_str(base)
            for key in _GR3_BASE_MAP:
                if key in base_str:
                    gr3_base = key
                    break
            if gr3_base:
                break

        if gr3_base is None:
            continue

        block_name = _to_camel(node.name)
        docstring = ast.get_docstring(node) or ""

        in_sigs: list[str] = []
        out_sigs: list[str] = []
        params: list[tuple[str, str]] = []

        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "__init__":
                continue
            params = _extract_params(item)
            # Find the super().__init__ call with in_sig / out_sig
            for stmt in ast.walk(item):
                if not isinstance(stmt, ast.Call):
                    continue
                call_str = _node_to_str(stmt.func)
                if any(key in call_str for key in _GR3_BASE_MAP):
                    in_sigs, out_sigs = _extract_sigs(stmt)
                    break
            break

        return {
            "block_name": block_name,
            "gr3_base": gr3_base,
            "in_sigs": in_sigs,
            "out_sigs": out_sigs,
            "params": params,
            "docstring": docstring,
        }

    raise ValueError(
        "No GNURadio 3 block class found in source (expected gr.sync_block / decim_block / interp_block / basic_block)"
    )


def port_gr3_block(
    cfg: ProjectConfig,
    group: str,
    source_path: Path,
) -> list[Path]:
    """Parse a gr3 Python block and write a gr4 header + test."""
    source = source_path.read_text()
    info = parse_gr3_python(source)

    archetype_name = _GR3_BASE_MAP.get(info["gr3_base"])
    arch = ARCHETYPES.get(archetype_name, {}) if archetype_name else {}

    all_sigs = info["in_sigs"] + info["out_sigs"]
    cpp_types: list[str] = []
    for sig in all_sigs:
        cpp = _NUMPY_TYPE_MAP.get(sig)
        if cpp and cpp not in cpp_types:
            cpp_types.append(cpp)
    type_list = ", ".join(cpp_types) if cpp_types else "float, double"

    answers = {
        "group_name": group,
        "block_name": info["block_name"],
        "description": info["docstring"] or f"Ported from GNURadio 3 {info['block_name']}",
        "template_params": ["T"],
        "in_ports": arch.get("in_ports", [{"name": "in", "type": "T"}]),
        "out_ports": arch.get("out_ports", [{"name": "out", "type": "T"}]),
        "processing_style": arch.get("processing_style", "processOne"),
        "type_list": type_list,
        "gen_test": True,
    }
    written = write_block_files(cfg, answers)

    # Inject Annotated<> parameters from gr3 __init__ args
    if info["params"]:
        from gr4_modtool.commands.newparam import add_param

        for pname, pdefault in info["params"]:
            try:
                add_param(
                    cfg,
                    group,
                    info["block_name"],
                    pname,
                    "float",
                    f"Ported from gr3 parameter '{pname}'",
                    pdefault,
                )
            except (ValueError, FileNotFoundError):
                pass

    return written


@click.command("port")
@click.argument("source_file", type=click.Path(exists=True))
@click.option("--group", default=None, help="Target group.")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True)
def cmd(
    source_file: str,
    group: str | None,
    project_dir: str | None,
    yes: bool,
) -> None:
    """Import a GNURadio 3.x Python block and scaffold a gr4 header."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    groups = discover_groups(cfg)

    if not groups:
        click.echo("No groups found. Run 'gr4_modtool newgroup' first.", err=True)
        sys.exit(1)

    if group is None:
        group = questionary.select("Target group:", choices=[g.name for g in groups]).ask()
        if group is None:
            sys.exit(0)

    source_path = Path(source_file)
    try:
        info = parse_gr3_python(source_path.read_text())
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Detected: {info['gr3_base']} → {info['block_name']}")
    click.echo(f"  in_sig:  {info['in_sigs']}")
    click.echo(f"  out_sig: {info['out_sigs']}")
    if info["params"]:
        click.echo(f"  params:  {[p[0] for p in info['params']]}")

    if not yes:
        confirm = questionary.confirm(
            f"Port '{info['block_name']}' into group '{group}'?", default=True
        ).ask()
        if not confirm:
            sys.exit(0)

    try:
        written = port_gr3_block(cfg, group, source_path)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo("Created:")
    for p in written:
        click.echo(f"  {p}")
