"""Entry-point loader for third-party gr4_modtool extensions."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

import click

from gr4_modtool.log import get_logger

log = get_logger(__name__)


def load_extra_commands() -> list[click.Command]:
    """Return Click commands registered under 'gr4_modtool.commands'."""
    cmds: list[click.Command] = []
    for ep in entry_points(group="gr4_modtool.commands"):
        try:
            cmd = ep.load()
            if isinstance(cmd, click.Command):
                cmds.append(cmd)
                log.debug("loaded command plugin '%s' from %s", ep.name, ep.value)
            else:
                log.warning(
                    "command plugin '%s' is not a click command (got %r); ignoring",
                    ep.name,
                    type(cmd).__name__,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("could not load command plugin '%s': %s", ep.name, exc)
            log.debug("command plugin '%s' traceback", ep.name, exc_info=True)
    return cmds


def load_extra_template_dirs() -> list[Path]:
    """Return template directories registered under 'gr4_modtool.templates'."""
    dirs: list[Path] = []
    for ep in entry_points(group="gr4_modtool.templates"):
        try:
            get_dir = ep.load()
            path = Path(get_dir())
            if path.is_dir():
                dirs.append(path)
                log.debug("loaded template plugin '%s' -> %s", ep.name, path)
            else:
                log.warning("template plugin '%s' points at a missing directory: %s", ep.name, path)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not load template plugin '%s': %s", ep.name, exc)
            log.debug("template plugin '%s' traceback", ep.name, exc_info=True)
    return dirs
