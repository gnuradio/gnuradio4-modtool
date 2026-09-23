"""Tests for gr4_modtool.templates — Jinja2 search-order priority."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from gr4_modtool.templates import make_env, render

# Use block.hpp.j2 as the canonical test template name — it exists in built-ins,
# so it doubles as the "falls through to built-in" sentinel.
_BUILTIN_TMPL = "block.hpp.j2"


def _write(directory: Path, name: str, content: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content)


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def test_builtin_reachable() -> None:
    env = make_env()
    tmpl = env.get_template(_BUILTIN_TMPL)
    assert tmpl is not None


def test_no_project_root_uses_builtin() -> None:
    env = make_env(project_root=None, extra_dirs=None)
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    assert source is not None


def test_missing_template_raises() -> None:
    env = make_env()
    with pytest.raises(TemplateNotFound):
        env.get_template("_does_not_exist_anywhere.j2")


# ---------------------------------------------------------------------------
# extra_dirs layer
# ---------------------------------------------------------------------------


def test_extra_dirs_override_builtin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    _write(plugin_dir, _BUILTIN_TMPL, "plugin-override")

    env = make_env(extra_dirs=[plugin_dir])
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    assert source == "plugin-override"


def test_extra_dirs_first_wins(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    _write(dir_a, _BUILTIN_TMPL, "from-a")
    _write(dir_b, _BUILTIN_TMPL, "from-b")

    env = make_env(extra_dirs=[dir_a, dir_b])
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    assert source == "from-a"


def test_extra_dirs_template_not_in_builtin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    _write(plugin_dir, "_unique_plugin_only.j2", "plugin-only-content")

    env = make_env(extra_dirs=[plugin_dir])
    source, _, _ = env.loader.get_source(env, "_unique_plugin_only.j2")
    assert source == "plugin-only-content"


# ---------------------------------------------------------------------------
# project_root override layer
# ---------------------------------------------------------------------------


def test_project_root_override_beats_builtin(tmp_path: Path) -> None:
    override_dir = tmp_path / ".gr4modtool" / "templates"
    _write(override_dir, _BUILTIN_TMPL, "project-override")

    env = make_env(project_root=tmp_path)
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    assert source == "project-override"


def test_project_root_without_override_dir_uses_builtin(tmp_path: Path) -> None:
    # project_root exists but .gr4modtool/templates/ does not
    env = make_env(project_root=tmp_path)
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    # Should fall through to the built-in (not "project-override")
    assert "project-override" not in source


def test_project_root_beats_extra_dirs(tmp_path: Path) -> None:
    override_dir = tmp_path / ".gr4modtool" / "templates"
    _write(override_dir, _BUILTIN_TMPL, "project-override")

    plugin_dir = tmp_path / "plugin"
    _write(plugin_dir, _BUILTIN_TMPL, "plugin-override")

    env = make_env(project_root=tmp_path, extra_dirs=[plugin_dir])
    source, _, _ = env.loader.get_source(env, _BUILTIN_TMPL)
    assert source == "project-override"


# ---------------------------------------------------------------------------
# render() integration
# ---------------------------------------------------------------------------


def test_render_with_extra_dirs(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    _write(plugin_dir, "greeting.j2", "Hello {{ name }}!")

    result = render("greeting.j2", {"name": "world"}, extra_dirs=[plugin_dir])
    assert result == "Hello world!"
