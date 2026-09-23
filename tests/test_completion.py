"""Tests for the completion command."""

from __future__ import annotations

from click.testing import CliRunner

from gr4_modtool.cli import cli


def test_bash_eval_line() -> None:
    result = CliRunner().invoke(cli, ["completion", "--shell", "bash"])
    assert result.exit_code == 0
    assert "_GR4_MODTOOL_COMPLETE=bash_source" in result.output


def test_zsh_eval_line() -> None:
    result = CliRunner().invoke(cli, ["completion", "--shell", "zsh"])
    assert result.exit_code == 0
    assert "_GR4_MODTOOL_COMPLETE=zsh_source" in result.output


def test_fish_eval_line() -> None:
    result = CliRunner().invoke(cli, ["completion", "--shell", "fish"])
    assert result.exit_code == 0
    assert "_GR4_MODTOOL_COMPLETE=fish_source" in result.output
