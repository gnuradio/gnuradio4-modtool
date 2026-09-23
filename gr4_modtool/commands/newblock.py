"""newblock command — add a block to an existing group."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.fileops import write_text
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project.discovery import discover_groups, load_config
from gr4_modtool.templates import render

try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
    _yaml = None  # type: ignore[assignment]

# --------------------------------------------------------------------------- #
# Archetypes
# --------------------------------------------------------------------------- #

ARCHETYPES: dict[str, dict] = {
    "source": {
        "in_ports": [],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
    "sink": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [],
        "processing_style": "processBulk",
    },
    "sync": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
    },
    "sync_bulk": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
    "decimator": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
    "interpolator": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
}

_ARCHETYPE_NAMES = list(ARCHETYPES.keys())

# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_VALID_STYLES = {"processOne", "processBulk"}


def _is_camel(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def _resolve_port_type(raw: str, template_params: list[str]) -> str:
    """Turn short shorthands like 'T', 'complex<T>', 'TIN' into proper C++ types."""
    raw = raw.strip()
    if raw in template_params:
        return raw
    if raw.startswith("complex<") and raw.endswith(">"):
        inner = raw[8:-1].strip()
        return f"std::complex<{inner}>"
    # Allow 'std::complex<T>' as-is
    return raw


def _build_template_ctx(
    block_name: str,
    namespace: str,
    group: str,
    description: str,
    template_params: list[str],
    in_ports: list[dict],
    out_ports: list[dict],
    type_list: str,
    processing_style: str,
    gr4_include_prefix: str,
    simd: bool = False,
) -> dict:
    multi_output = len(out_ports) > 1
    uses_complex = any("complex" in p["type"] for p in in_ports + out_ports)

    template_decl = ", ".join(f"typename {p}" for p in template_params)
    template_args = ", ".join(template_params)

    if len(template_params) == 1:
        template_param_macro = f"([{template_params[0]}])"
    else:
        template_param_macro = f"([ {', '.join(template_params)} ])"

    if multi_output:
        return_type = "std::tuple<" + ", ".join(p["type"] for p in out_ports) + ">"
    else:
        return_type = out_ports[0]["type"] if out_ports else "void"

    process_in_ports = [{**port, "arg_name": f"input_{port['name']}"} for port in in_ports]
    process_out_ports = [{**port, "arg_name": f"output_{port['name']}"} for port in out_ports]

    if processing_style == "processOne":
        params_str = ", ".join(f"{p['type']} {p['arg_name']}" for p in process_in_ports)
        bulk_params_str = ""
    else:
        in_spans = ", ".join(
            f"std::span<const {p['type']}> {p['arg_name']}" for p in process_in_ports
        )
        out_spans = ", ".join(f"std::span<{p['type']}> {p['arg_name']}" for p in process_out_ports)
        bulk_params_str = ", ".join(filter(None, [in_spans, out_spans]))
        params_str = ""

    all_port_names = [p["name"] for p in in_ports + out_ports]

    # Determine first_type for graph test (first element of type_list)
    first_type = type_list.split(",")[0].strip()
    # Resolve graph test port types
    first_port_type = (
        in_ports[0]["type"].replace(template_params[0], first_type) if in_ports else first_type
    )
    first_out_type = (
        out_ports[0]["type"].replace(template_params[0], first_type) if out_ports else first_type
    )

    return {
        "block_name": block_name,
        "namespace": namespace,
        "group": group,
        "description": description,
        "template_params": template_params,
        "template_decl": template_decl,
        "template_args": template_args,
        "template_param_macro": template_param_macro,
        "in_ports": in_ports,
        "out_ports": out_ports,
        "process_in_ports": process_in_ports,
        "process_out_ports": process_out_ports,
        "all_port_names": all_port_names,
        "type_list": type_list,
        "processing_style": processing_style,
        "uses_complex": uses_complex,
        "multi_output": multi_output,
        "return_type": return_type,
        "has_return_value": bool(out_ports),
        "params_str": params_str,
        "bulk_params_str": bulk_params_str,
        "gr4_include_prefix": gr4_include_prefix,
        "first_type": first_type,
        "first_port_type": first_port_type,
        "first_out_type": first_out_type,
        # Source blocks (no inputs) get no graph-run test: the generated
        # skeleton produces samples forever, so runAndWait() would never
        # return. Bounded ConstantSource feeders give every other shape EOS.
        "needs_graph_test": bool(in_ports),
        "simd": simd,
    }


# --------------------------------------------------------------------------- #
# Prompt flow CLI
# --------------------------------------------------------------------------- #


def prompt_newblock(
    cfg,
    group_name: str | None = None,
    archetype: str | None = None,
) -> dict | None:
    """Run the interactive prompt flow. Returns context dict or None if aborted."""
    if cfg.flat:
        group_name = ""
    else:
        groups = discover_groups(cfg)
        group_names = [g.name for g in groups]

        if not group_names:
            click.echo("No groups found. Run 'gr4_modtool newgroup' first.", err=True)
            return None

        if group_name is None:
            group_name = questionary.select("Group to add block to:", choices=group_names).ask()
            if group_name is None:
                return None

    block_name = questionary.text(
        "Block name (CamelCase, e.g. MyFilter):",
        validate=lambda v: _is_camel(v) or "Must be CamelCase starting with uppercase letter",
    ).ask()
    if block_name is None:
        return None

    description = questionary.text("One-line description:").ask()
    if description is None:
        return None

    # Template params
    multi_type = questionary.confirm(
        "Multiple template type parameters? (e.g. TIN, TOUT)", default=False
    ).ask()
    if multi_type:
        raw = questionary.text("Template parameter names (comma-separated, e.g. TIN,TOUT):").ask()
        if raw is None:
            return None
        template_params = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        template_params = ["T"]

    # If archetype given, skip port/style prompts
    if archetype and archetype in ARCHETYPES:
        arch = ARCHETYPES[archetype]
        in_ports = arch["in_ports"]
        out_ports = arch["out_ports"]
        style = arch["processing_style"]
    else:
        # Input ports
        n_in = questionary.text(
            "Number of input ports:",
            default="1",
            validate=lambda v: v.isdigit() or "Enter a number",
        ).ask()
        if n_in is None:
            return None

        type_choices = [p for p in template_params] + [
            f"std::complex<{template_params[0]}>",
            "custom",
        ]
        in_ports = []
        for i in range(int(n_in)):
            pname = questionary.text(
                f"  Input port {i + 1} name:", default=f"in{i + 1}" if int(n_in) > 1 else "in"
            ).ask()
            if pname is None:
                return None
            ptype_raw = questionary.select(
                f"  Input port {i + 1} data type:", choices=type_choices
            ).ask()
            if ptype_raw is None:
                return None
            if ptype_raw == "custom":
                ptype_raw = questionary.text("    Custom type:").ask() or "T"
            ptype = _resolve_port_type(ptype_raw, template_params)
            in_ports.append({"name": pname, "type": ptype})

        # Output ports
        n_out = questionary.text(
            "Number of output ports:",
            default="1",
            validate=lambda v: v.isdigit() or "Enter a number",
        ).ask()
        if n_out is None:
            return None

        out_ports = []
        for i in range(int(n_out)):
            pname = questionary.text(
                f"  Output port {i + 1} name:", default=f"out{i + 1}" if int(n_out) > 1 else "out"
            ).ask()
            if pname is None:
                return None
            ptype_raw = questionary.select(
                f"  Output port {i + 1} data type:", choices=type_choices
            ).ask()
            if ptype_raw is None:
                return None
            if ptype_raw == "custom":
                ptype_raw = questionary.text("    Custom type:").ask() or "T"
            ptype = _resolve_port_type(ptype_raw, template_params)
            out_ports.append({"name": pname, "type": ptype})

        # Processing style
        style = questionary.select(
            "Processing style:",
            choices=["processOne", "processBulk"],
        ).ask()
        if style is None:
            return None

    # Type list
    uses_complex = any("complex" in p["type"] for p in in_ports + out_ports)
    default_types = (
        "float, double" if uses_complex or template_params == ["T"] else ", ".join(template_params)
    )
    type_list = questionary.text(
        "GR_REGISTER_BLOCK type list (comma-separated C++ types):",
        default=default_types,
    ).ask()
    if type_list is None:
        return None

    gen_test = questionary.confirm("Generate test file?", default=True).ask()

    return {
        "group_name": group_name,
        "block_name": block_name,
        "description": description,
        "template_params": template_params,
        "in_ports": in_ports,
        "out_ports": out_ports,
        "processing_style": style,
        "type_list": type_list,
        "gen_test": gen_test,
    }


# --------------------------------------------------------------------------- #
# Spec file loading and validation
# --------------------------------------------------------------------------- #


def validate_spec_entry(entry: dict, *, flat: bool = False) -> None:
    """Raise ValueError if a normalised spec entry is invalid."""
    name = entry.get("block_name", "")
    if not name:
        raise ValueError("block_name is required in every spec entry")
    if not _NAME_RE.match(str(name)):
        raise ValueError(f"block_name {name!r} must be CamelCase (e.g. MyFilter)")
    if not flat and not entry.get("group_name"):
        raise ValueError(
            f"group is required for block {name!r} — set it in the spec or pass --group"
        )
    style = entry.get("processing_style")
    if style and style not in _VALID_STYLES:
        raise ValueError(f"processing_style {style!r} must be one of {sorted(_VALID_STYLES)}")
    for port in entry.get("in_ports", []) + entry.get("out_ports", []):
        if "name" not in port or "type" not in port:
            raise ValueError(f"Each port must have 'name' and 'type'. Got: {port}")


def load_spec(path: Path, group_override: str | None = None) -> list[dict]:
    """Parse a YAML block spec file and return a list of normalised answers dicts.

    The YAML may be a single block mapping or a list of mappings. Each entry
    is normalised to the shape expected by write_block_files().
    ``group_override`` replaces the ``group`` field in every entry when provided.
    """
    if not _YAML_AVAILABLE:
        raise RuntimeError("PyYAML is required for --spec: pip install PyYAML")
    raw = _yaml.safe_load(path.read_text())
    if raw is None:
        raise ValueError(f"Spec file {path} is empty")
    entries: list[dict] = raw if isinstance(raw, list) else [raw]

    result = []
    for raw_entry in entries:
        e = dict(raw_entry)

        # Expand archetype shorthand before applying explicit overrides
        arch_name = e.pop("archetype", None)
        if arch_name is not None:
            if arch_name not in ARCHETYPES:
                raise ValueError(f"Unknown archetype {arch_name!r}. Valid: {list(ARCHETYPES)}")
            arch = dict(ARCHETYPES[arch_name])
            # Explicit port/style keys in the YAML override the archetype
            for key in ("in_ports", "out_ports", "processing_style"):
                if key in e:
                    arch[key] = e.pop(key)
            e = {**e, **arch}

        # Rename 'group' → 'group_name' for write_block_files()
        if "group" in e and "group_name" not in e:
            e["group_name"] = e.pop("group")

        # CLI group override wins
        if group_override:
            e["group_name"] = group_override

        # Apply defaults
        e.setdefault("template_params", ["T"])
        e.setdefault("type_list", "float, double")
        e.setdefault("gen_test", True)
        e.setdefault("simd", False)
        e.setdefault("description", "")

        result.append(e)
    return result


# --------------------------------------------------------------------------- #
# File writing CLI
# --------------------------------------------------------------------------- #


def write_block_files(cfg, answers: dict) -> list[Path]:
    """Write all files for a new block. Returns list of created/modified paths."""
    block_name = answers["block_name"]
    gen_test = answers.get("gen_test", True)
    simd = answers.get("simd", False)
    processing_style = "processBulk" if simd else answers["processing_style"]

    if cfg.flat:
        group_name = ""
        namespace = cfg.cpp_namespace
        header_dir = cfg.block_include_dir()
        test_dir = cfg.block_test_dir()
        target_libs = f"{cfg.cmake_prefix}::blocks_headers"
    else:
        group_name = answers["group_name"]
        namespace = cfg.cpp_namespace + f"::{group_name}"
        header_dir = cfg.group_include_dir(group_name)
        test_dir = cfg.group_test_dir(group_name)
        target_libs = f"{cfg.cmake_prefix}::blocks_{group_name}_headers"

    ctx = _build_template_ctx(
        block_name=block_name,
        namespace=namespace,
        group=group_name,
        description=answers["description"],
        template_params=answers["template_params"],
        in_ports=answers["in_ports"],
        out_ports=answers["out_ports"],
        type_list=answers["type_list"],
        processing_style=processing_style,
        gr4_include_prefix=cfg.gr4_include_prefix,
        simd=simd,
    )

    written: list[Path] = []

    # Block header
    header_dir.mkdir(parents=True, exist_ok=True)
    header_path = header_dir / f"{block_name}.hpp"
    write_text(header_path, render("block.hpp.j2", ctx, cfg.root))
    written.append(header_path)

    if gen_test:
        test_dir.mkdir(parents=True, exist_ok=True)

        # Test source
        test_path = test_dir / f"qa_{block_name}.cpp"
        write_text(test_path, render("qa_block.cpp.j2", ctx, cfg.root))
        written.append(test_path)

        # Update CMakeLists.txt
        cmake_test = test_dir / "CMakeLists.txt"
        if cfg.build_cmake and cmake_test.exists():
            cmake_mod.append_test_entry(cmake_test, block_name, target_libs)
            written.append(cmake_test)

    return written


# --------------------------------------------------------------------------- #
# Click command
# --------------------------------------------------------------------------- #


@click.command("newblock")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Target group name.")
@click.option(
    "--template",
    "-T",
    type=click.Choice(_ARCHETYPE_NAMES + ["custom"]),
    default=None,
    help="Block archetype to use (pre-fills ports and processing style).",
)
@click.option(
    "--simd",
    is_flag=True,
    default=False,
    help="Generate a SIMD-vectorization-friendly processBulk skeleton.",
)
@click.option(
    "--spec",
    "spec_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="YAML spec file defining one or more blocks (skips interactive prompts).",
)
def cmd(
    project_dir: str | None,
    group: str | None,
    template: str | None,
    simd: bool,
    spec_file: str | None,
) -> None:
    """Add a new block to an existing group."""
    cfg = load_config(Path(project_dir) if project_dir else None)

    if spec_file:
        try:
            entries = load_spec(Path(spec_file), group_override=group)
            for entry in entries:
                validate_spec_entry(entry, flat=cfg.flat)
        except (ValueError, RuntimeError) as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

        if simd:
            for entry in entries:
                entry["simd"] = True

        names = []
        for entry in entries:
            write_block_files(cfg, entry)
            names.append(entry["block_name"])
        click.echo(f"Generated {len(names)} block(s): {', '.join(names)}")
        return

    # Interactive flow
    archetype = template if template and template != "custom" else None
    answers = prompt_newblock(cfg, group_name=group, archetype=archetype)
    if answers is None:
        sys.exit(0)

    answers["simd"] = simd

    click.echo("\nFiles to be written:")
    header = cfg.group_include_dir(answers["group_name"]) / f"{answers['block_name']}.hpp"
    click.echo(f"  {header}")
    if answers.get("gen_test"):
        test_dir = cfg.group_test_dir(answers["group_name"])
        click.echo(f"  {test_dir / ('qa_' + answers['block_name'] + '.cpp')}")
        click.echo(f"  (update) {test_dir / 'CMakeLists.txt'}")

    confirm = questionary.confirm("\nProceed?", default=True).ask()
    if not confirm:
        sys.exit(0)

    written = write_block_files(cfg, answers)
    click.echo("\nCreated:")
    for p in written:
        click.echo(f"  {p}")
