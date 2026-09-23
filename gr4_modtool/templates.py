"""Jinja2 template loader with user-override support."""

from __future__ import annotations

from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined

from gr4_modtool.log import get_logger, log_duration

log = get_logger(__name__)

_BUILTIN_TEMPLATES = Path(__file__).parent / "templates"


def make_env(project_root: Path | None = None, extra_dirs: list[Path] | None = None) -> Environment:
    """Build a Jinja2 Environment.

    Search order:
    1. <project_root>/.gr4modtool/templates/   (user overrides)
    2. extra_dirs (from plugins)
    3. built-in gr4_modtool/templates/
    """
    search_dirs: list[Path] = []

    if project_root is not None:
        override_dir = project_root / ".gr4modtool" / "templates"
        if override_dir.is_dir():
            search_dirs.append(override_dir)

    if extra_dirs:
        search_dirs.extend(extra_dirs)

    search_dirs.append(_BUILTIN_TEMPLATES)
    log.debug("template search path: %s", " : ".join(str(d) for d in search_dirs))

    loaders = [FileSystemLoader(str(d)) for d in search_dirs]
    loader = ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0]

    return Environment(
        loader=loader,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def builtin_templates_dir() -> Path:
    return _BUILTIN_TEMPLATES


def render(
    template_name: str,
    context: dict,
    project_root: Path | None = None,
    extra_dirs: list[Path] | None = None,
) -> str:
    env = make_env(project_root=project_root, extra_dirs=extra_dirs)
    tmpl = env.get_template(template_name)
    source = tmpl.filename or "<unknown>"
    if not source.startswith(str(_BUILTIN_TEMPLATES)):
        log.info("rendering %s from override %s", template_name, source)
    else:
        log.debug("rendering %s from %s", template_name, source)
    with log_duration(log, f"rendering {template_name}"):
        return tmpl.render(**context)
