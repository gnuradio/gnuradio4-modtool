"""Shared helpers for end-to-end tests.

All E2E tests invoke gr4_modtool through the real CLI entry point (Click's
CliRunner against ``gr4_modtool.cli.cli``) rather than calling internal
functions directly.  Project fixtures are inherited from the parent conftest.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from gr4_modtool.cli import cli

# ---------------------------------------------------------------------------
# Core invoke helper
# ---------------------------------------------------------------------------


def invoke(root: Path, *cmd_and_args: str, expect_ok: bool = True, input: str | None = None):
    """Run a gr4_modtool subcommand via the CLI entry point against *root*.

    Inserts ``--project-dir <root>`` immediately after the subcommand name so
    every call exercises the real CLI dispatch path.  Asserts exit code 0
    unless ``expect_ok=False``.
    """
    runner = CliRunner()
    subcommand = cmd_and_args[0]
    rest = list(cmd_and_args[1:])
    args = [subcommand, "--project-dir", str(root), *rest]
    result = runner.invoke(cli, args, input=input)
    if expect_ok:
        assert result.exit_code == 0, (
            f"Command {args!r} exited {result.exit_code}:\n{result.output}"
        )
    return result


# ---------------------------------------------------------------------------
# Block spec helper
# ---------------------------------------------------------------------------


def write_spec(
    path: Path,
    block_name: str,
    *,
    group: str = "basic",
    archetype: str = "sync",
    type_list: str = "float, double",
    gen_test: bool = True,
) -> Path:
    """Write a minimal newblock YAML spec to *path* and return it."""
    flat_group = group == ""
    lines = [f"block_name: {block_name}"]
    if not flat_group:
        lines.append(f"group: {group}")
    lines += [
        f"archetype: {archetype}",
        f'type_list: "{type_list}"',
        f"gen_test: {'true' if gen_test else 'false'}",
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------
# pytest skip markers (re-usable in test modules)
# ---------------------------------------------------------------------------

skip_no_cmake = pytest.mark.skipif(not shutil.which("cmake"), reason="cmake not installed")
skip_no_clang_format = pytest.mark.skipif(
    not shutil.which("clang-format"), reason="clang-format not installed"
)
skip_no_clang_tidy = pytest.mark.skipif(
    not shutil.which("clang-tidy"), reason="clang-tidy not installed"
)
