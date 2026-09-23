"""Unit tests for gr4_modtool.plugins — entry-point discovery and loading."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import click
import pytest

from gr4_modtool import plugins

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ep(name: str, obj=None, *, raises=None) -> MagicMock:
    """Build a MagicMock that behaves like an importlib.metadata EntryPoint."""
    ep = MagicMock()
    ep.name = name
    if raises is not None:
        ep.load.side_effect = raises
    else:
        ep.load.return_value = obj
    return ep


@click.command("dummy-cmd")
def _dummy_cmd() -> None:
    """A minimal Click command used as a test fixture."""
    click.echo("hello from dummy")


@click.group("dummy-grp")
def _dummy_grp() -> None:
    """A minimal Click group used as a test fixture."""


# ---------------------------------------------------------------------------
# load_extra_commands
# ---------------------------------------------------------------------------


def test_load_commands_no_entry_points() -> None:
    with patch("gr4_modtool.plugins.entry_points", return_value=[]):
        result = plugins.load_extra_commands()
    assert result == []


def test_load_commands_returns_valid_command() -> None:
    ep = _make_ep("myplugin", _dummy_cmd)
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_commands()
    assert result == [_dummy_cmd]


def test_load_commands_returns_group() -> None:
    ep = _make_ep("grpplugin", _dummy_grp)
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_commands()
    assert result == [_dummy_grp]


def test_load_commands_skips_non_basecommand() -> None:
    ep = _make_ep("badtype", lambda: None)
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_commands()
    assert result == []


def test_load_commands_load_raises_warns(caplog) -> None:
    ep = _make_ep("broken", raises=ImportError("no module named 'missing'"))
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            result = plugins.load_extra_commands()
    assert result == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_load_commands_bad_ep_does_not_block_good() -> None:
    bad_ep = _make_ep("bad", raises=ImportError("boom"))
    good_ep = _make_ep("good", _dummy_cmd)
    with patch("gr4_modtool.plugins.entry_points", return_value=[bad_ep, good_ep]):
        result = plugins.load_extra_commands()
    assert result == [_dummy_cmd]


def test_load_commands_warning_contains_ep_name(caplog) -> None:
    ep = _make_ep("my-special-plugin", raises=ImportError("boom"))
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            plugins.load_extra_commands()
    assert "my-special-plugin" in caplog.text


def test_load_commands_warning_contains_error_text(caplog) -> None:
    ep = _make_ep("plug", raises=ImportError("very specific error text"))
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            plugins.load_extra_commands()
    assert "very specific error text" in caplog.text


def test_load_commands_multiple_valid() -> None:
    @click.command("cmd-a")
    def cmd_a() -> None: ...

    @click.command("cmd-b")
    def cmd_b() -> None: ...

    eps = [_make_ep("a", cmd_a), _make_ep("b", cmd_b)]
    with patch("gr4_modtool.plugins.entry_points", return_value=eps):
        result = plugins.load_extra_commands()
    assert result == [cmd_a, cmd_b]


# ---------------------------------------------------------------------------
# load_extra_template_dirs
# ---------------------------------------------------------------------------


def test_load_template_dirs_no_entry_points() -> None:
    with patch("gr4_modtool.plugins.entry_points", return_value=[]):
        result = plugins.load_extra_template_dirs()
    assert result == []


def test_load_template_dirs_existing_dir(tmp_path) -> None:
    ep = _make_ep("tmpl", lambda: str(tmp_path))
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_template_dirs()
    assert len(result) == 1
    assert result[0] == tmp_path


def test_load_template_dirs_nonexistent_dir_silently_skipped(tmp_path) -> None:
    missing = tmp_path / "does_not_exist"
    ep = _make_ep("tmpl", lambda: str(missing))
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_template_dirs()
    assert result == []


def test_load_template_dirs_callable_raises_warns(caplog) -> None:
    def bad_callable():
        raise RuntimeError("template dir discovery failed")

    ep = _make_ep("tmpl", bad_callable)
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            result = plugins.load_extra_template_dirs()
    assert result == []
    assert "template dir discovery failed" in caplog.text


def test_load_template_dirs_load_raises_warns(caplog) -> None:
    ep = _make_ep("tmpl", raises=ModuleNotFoundError("missing dep"))
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            result = plugins.load_extra_template_dirs()
    assert result == []
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_load_template_dirs_string_path_accepted(tmp_path) -> None:
    ep = _make_ep("tmpl", lambda: str(tmp_path))
    with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
        result = plugins.load_extra_template_dirs()
    assert len(result) == 1
    assert isinstance(result[0], __import__("pathlib").Path)


def test_load_template_dirs_warning_contains_ep_name(caplog) -> None:
    ep = _make_ep("very-unique-plugin-name", raises=RuntimeError("boom"))
    with caplog.at_level(logging.WARNING, logger="gr4_modtool.plugins"):
        with patch("gr4_modtool.plugins.entry_points", return_value=[ep]):
            plugins.load_extra_template_dirs()
    assert "very-unique-plugin-name" in caplog.text


def test_load_template_dirs_multiple_valid(tmp_path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    eps = [
        _make_ep("plugin-a", lambda d=dir_a: str(d)),
        _make_ep("plugin-b", lambda d=dir_b: str(d)),
    ]
    with patch("gr4_modtool.plugins.entry_points", return_value=eps):
        result = plugins.load_extra_template_dirs()
    assert result == [dir_a, dir_b]


# ---------------------------------------------------------------------------
# CLI integration — only runs when the example plugin is installed
# ---------------------------------------------------------------------------


def _example_plugin_installed() -> bool:
    try:
        import importlib.metadata

        importlib.metadata.distribution("gr4-modtool-example-plugin")
        return True
    except Exception:
        return False


_skip_no_example_plugin = pytest.mark.skipif(
    not _example_plugin_installed(), reason="gr4-modtool-example-plugin not installed"
)


@_skip_no_example_plugin
def test_example_plugin_command_registered() -> None:
    from gr4_modtool.cli import cli

    assert "report" in cli.commands


@_skip_no_example_plugin
def test_example_plugin_command_appears_in_help() -> None:
    from click.testing import CliRunner

    from gr4_modtool.cli import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "report" in result.output


@_skip_no_example_plugin
def test_example_plugin_report_command_runs(project) -> None:
    from click.testing import CliRunner

    from gr4_modtool.cli import cli

    result = CliRunner().invoke(cli, ["report", "--project-dir", str(project.root)])
    assert result.exit_code == 0
    assert "basic" in result.output
