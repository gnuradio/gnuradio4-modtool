"""Logging for gr4_modtool.

Every module logs through ``get_logger(__name__)``.  Nothing is emitted until a
front end calls :func:`configure_logging` — the CLI does that from its group
callback, and library can call it themselves::

    from gr4_modtool.log import configure_logging
    configure_logging(verbose=2, log_file="/tmp/gr4.log")

Loggers live under the ``gr4_modtool`` root logger, which does not propagate to
the stdlib root logger, so importing gr4_modtool never disturbs an application's
own logging setup.
"""

from __future__ import annotations

import logging
import os
import shlex
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

ROOT_NAME = "gr4_modtool"

#: Sets the default console level when neither ``-v`` nor ``--quiet`` is given.
#: Accepts a level name (``DEBUG``, ``info``, …) or a number.
ENV_LEVEL = "GR4_MODTOOL_LOG_LEVEL"
#: Sets the default debug log file when ``--log-file`` is not given.
ENV_FILE = "GR4_MODTOOL_LOG_FILE"

_VERBOSITY_LEVELS = (logging.WARNING, logging.INFO, logging.DEBUG)
_CONSOLE_FORMAT = "%(levelname)s: %(message)s"
_CONSOLE_FORMAT_DEBUG = "%(levelname)s %(name)s: %(message)s"
_FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# Marks the handlers this module owns, so reconfiguring replaces only those.
_OWNED = "_gr4_modtool_handler"


def get_logger(name: str) -> logging.Logger:
    """Return the logger for a module — pass ``__name__``.

    Names outside the package (a plugin's, say) are re-parented under
    ``gr4_modtool`` so one switch controls every gr4_modtool log record.
    """
    if name != ROOT_NAME and not name.startswith(ROOT_NAME + "."):
        name = f"{ROOT_NAME}.{name}"
    return logging.getLogger(name)


def parse_level(value: str | int | None) -> int | None:
    """Coerce a level name or number to a logging level; None if unrecognised."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    level = logging.getLevelName(text.upper())
    return level if isinstance(level, int) else None


def console_level(verbose: int = 0, quiet: bool = False) -> int:
    """Resolve the console level from the flags, falling back to ``$GR4_MODTOOL_LOG_LEVEL``."""
    if quiet:
        return logging.ERROR
    if verbose > 0:
        return _VERBOSITY_LEVELS[min(verbose, len(_VERBOSITY_LEVELS) - 1)]
    from_env = parse_level(os.environ.get(ENV_LEVEL))
    return from_env if from_env is not None else logging.WARNING


def configure_logging(
    verbose: int = 0,
    quiet: bool = False,
    log_file: str | Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """Install gr4_modtool's log handlers and return the package logger.

    :param verbose: 0 → warnings only, 1 → info, 2+ → debug.
    :param quiet: errors only; overrides ``verbose``.
    :param log_file: also write everything at DEBUG to this file (appending).
        Defaults to ``$GR4_MODTOOL_LOG_FILE``.
    :param console: set False to suppress the stderr handler.

    Calling it again replaces the handlers it installed previously; handlers
    added by the host application are left alone.
    """
    logger = logging.getLogger(ROOT_NAME)
    for handler in [h for h in logger.handlers if getattr(h, _OWNED, False)]:
        logger.removeHandler(handler)
        handler.close()

    levels = []

    if console:
        level = console_level(verbose, quiet)
        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(
            logging.Formatter(_CONSOLE_FORMAT_DEBUG if level <= logging.DEBUG else _CONSOLE_FORMAT)
        )
        setattr(stream, _OWNED, True)
        logger.addHandler(stream)
        levels.append(level)

    target = log_file if log_file is not None else os.environ.get(ENV_FILE)
    if target:
        path = Path(target).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
        setattr(file_handler, _OWNED, True)
        logger.addHandler(file_handler)
        levels.append(logging.DEBUG)

    logger.setLevel(min(levels) if levels else logging.WARNING)
    # Keep gr4_modtool records out of the host application's root handlers.
    logger.propagate = False
    return logger


def format_command(cmd: Sequence[str]) -> str:
    """Render an argv list as a copy-pasteable shell command."""
    return shlex.join(str(part) for part in cmd)


def log_run(logger: logging.Logger, cmd: Sequence[str], cwd: Path | str | None = None) -> None:
    """Log a subprocess about to be launched."""
    suffix = f" (cwd={cwd})" if cwd else ""
    logger.info("running: %s%s", format_command(cmd), suffix)


def log_exit(logger: logging.Logger, cmd: Sequence[str], returncode: int) -> None:
    """Log how a subprocess finished, at WARNING when it failed."""
    level = logging.INFO if returncode == 0 else logging.WARNING
    logger.log(level, "%s exited with %d", format_command(cmd[:1] or cmd), returncode)


@contextmanager
def log_duration(logger: logging.Logger, what: str) -> Iterator[None]:
    """Time a block of work and log the elapsed milliseconds at DEBUG."""
    start = time.perf_counter()
    try:
        yield
    finally:
        logger.debug("%s took %.1f ms", what, (time.perf_counter() - start) * 1000)
