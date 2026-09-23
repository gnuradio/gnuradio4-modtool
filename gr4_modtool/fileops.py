"""File mutations that announce themselves to the log.

Command modules write through these helpers instead of calling
:class:`~pathlib.Path` directly, so a single ``-v`` shows every file the tool
touched — including from library callers, which never see the CLI's output.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from gr4_modtool.log import get_logger

log = get_logger(__name__)


def write_text(path: Path, text: str, *, encoding: str | None = None) -> Path:
    """Write ``text`` to ``path`` and log it. Returns the path."""
    action = "updated" if path.exists() else "created"
    if encoding is None:
        path.write_text(text)
    else:
        path.write_text(text, encoding=encoding)
    log.info("%s %s (%d bytes)", action, path, len(text))
    return path


def ensure_dir(path: Path) -> Path:
    """``mkdir -p`` for ``path``, logging directories that did not exist yet."""
    if not path.exists():
        log.debug("creating directory %s", path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def move_path(src: Path, dst: Path) -> Path:
    """Rename a file or directory, logging it. Returns the destination."""
    src.rename(dst)
    log.info("moved %s -> %s", src, dst)
    return dst


def remove_file(path: Path, *, missing_ok: bool = True) -> bool:
    """Delete a file, logging it. Returns True if something was removed."""
    if not path.exists():
        if not missing_ok:
            raise FileNotFoundError(path)
        log.debug("not removing %s (does not exist)", path)
        return False
    path.unlink()
    log.info("removed %s", path)
    return True


def remove_tree(path: Path) -> bool:
    """Recursively delete a directory, logging it. Returns True if it existed."""
    if not path.is_dir():
        log.debug("not removing %s (not a directory)", path)
        return False
    shutil.rmtree(path)
    log.info("removed directory %s", path)
    return True
