"""Template directory registration for gr4_modtool_example_plugin.

The entry point in pyproject.toml points at get_templates_dir:

    [project.entry-points."gr4_modtool.templates"]
    example_plugin = "gr4_modtool_example_plugin.templates:get_templates_dir"

gr4_modtool calls get_templates_dir() at startup and adds the returned path
to the Jinja2 search order *after* per-project overrides but *before* the
built-in templates.  Any .j2 file here whose name matches a built-in template
will replace the built-in for all projects that have this plugin installed.
"""

from __future__ import annotations

from pathlib import Path


def get_templates_dir() -> str:
    """Return the path to this plugin's template directory."""
    return str(Path(__file__).parent)
