"""completion command — print shell completion setup instructions."""

from __future__ import annotations

import click

_SHELLS: dict[str, tuple[str, str]] = {
    "bash": (
        'eval "$(_GR4_MODTOOL_COMPLETE=bash_source gr4_modtool)"',
        "Add to ~/.bashrc",
    ),
    "zsh": (
        'eval "$(_GR4_MODTOOL_COMPLETE=zsh_source gr4_modtool)"',
        "Add to ~/.zshrc",
    ),
    "fish": (
        "_GR4_MODTOOL_COMPLETE=fish_source gr4_modtool | source",
        "Add to ~/.config/fish/config.fish",
    ),
}


@click.command("completion")
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    required=True,
    help="Shell to generate completion for.",
)
@click.option(
    "--print-script",
    is_flag=True,
    default=False,
    help="Emit the raw completion script (pipe to a file or source it).",
)
def cmd(shell: str, print_script: bool) -> None:
    """Print shell completion setup for gr4_modtool."""
    if print_script:
        import os
        import subprocess

        env = {**os.environ, "_GR4_MODTOOL_COMPLETE": f"{shell}_source"}
        subprocess.run(["gr4_modtool"], env=env, check=False)
        return

    line, hint = _SHELLS[shell]
    click.echo(f"# {hint}:")
    click.echo(line)
