"""Tests for gr4_modtool.log and the logging-aware file helpers."""

from __future__ import annotations

import logging

import pytest
from click.testing import CliRunner

from gr4_modtool import fileops
from gr4_modtool.cli import cli
from gr4_modtool.log import (
    ENV_FILE,
    ENV_LEVEL,
    ROOT_NAME,
    configure_logging,
    console_level,
    format_command,
    get_logger,
    log_duration,
    log_exit,
    log_run,
    parse_level,
)

# ---------------------------------------------------------------------------
# get_logger / parse_level / console_level
# ---------------------------------------------------------------------------


def test_get_logger_returns_package_logger() -> None:
    assert get_logger("gr4_modtool.commands.newblock").name == "gr4_modtool.commands.newblock"


def test_get_logger_reparents_foreign_names() -> None:
    """A plugin logging under its own module name still lands under our root."""
    assert get_logger("some_plugin.report").name == "gr4_modtool.some_plugin.report"


def test_get_logger_root_name_unchanged() -> None:
    assert get_logger(ROOT_NAME).name == ROOT_NAME


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("DEBUG", logging.DEBUG),
        ("info", logging.INFO),
        ("10", 10),
        (logging.ERROR, logging.ERROR),
        ("nonsense", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_level(value, expected) -> None:
    assert parse_level(value) == expected


def test_console_level_defaults_to_warning(monkeypatch) -> None:
    monkeypatch.delenv(ENV_LEVEL, raising=False)
    assert console_level() == logging.WARNING


def test_console_level_verbosity_steps(monkeypatch) -> None:
    monkeypatch.delenv(ENV_LEVEL, raising=False)
    assert console_level(verbose=1) == logging.INFO
    assert console_level(verbose=2) == logging.DEBUG
    assert console_level(verbose=5) == logging.DEBUG


def test_console_level_quiet_beats_verbose() -> None:
    assert console_level(verbose=2, quiet=True) == logging.ERROR


def test_console_level_reads_env(monkeypatch) -> None:
    monkeypatch.setenv(ENV_LEVEL, "DEBUG")
    assert console_level() == logging.DEBUG


def test_console_level_flag_beats_env(monkeypatch) -> None:
    monkeypatch.setenv(ENV_LEVEL, "ERROR")
    assert console_level(verbose=1) == logging.INFO


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_logging_installs_stderr_handler(monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    logger = configure_logging(verbose=1)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.INFO
    assert logger.propagate is False


def test_configure_logging_is_idempotent(monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    configure_logging(verbose=1)
    logger = configure_logging(verbose=2)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG


def test_configure_logging_leaves_foreign_handlers_alone(monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    logger = logging.getLogger(ROOT_NAME)
    theirs = logging.NullHandler()
    logger.addHandler(theirs)
    configure_logging(verbose=1)
    configure_logging(verbose=1)
    assert theirs in logger.handlers
    assert len(logger.handlers) == 2


def test_configure_logging_console_can_be_disabled(monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    logger = configure_logging(verbose=2, console=False)
    assert logger.handlers == []


def test_log_file_records_at_debug(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    path = tmp_path / "logs" / "run.log"
    configure_logging(quiet=True, log_file=path)
    get_logger("gr4_modtool.test").debug("a debug detail")
    logging.getLogger(ROOT_NAME).handlers[-1].flush()
    assert "a debug detail" in path.read_text()


def test_log_file_from_env(tmp_path, monkeypatch) -> None:
    path = tmp_path / "env.log"
    monkeypatch.setenv(ENV_FILE, str(path))
    configure_logging()
    get_logger("gr4_modtool.test").warning("via env")
    logging.getLogger(ROOT_NAME).handlers[-1].flush()
    assert "via env" in path.read_text()


def test_stderr_stays_quiet_at_default_level(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    configure_logging()
    log = get_logger("gr4_modtool.test")
    log.info("progress detail")
    log.warning("something odd")
    err = capsys.readouterr().err
    assert "progress detail" not in err
    assert "something odd" in err


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_format_command_quotes_arguments() -> None:
    assert format_command(["cmake", "--build", "my build"]) == "cmake --build 'my build'"


def test_log_run_reports_command_and_cwd(caplog) -> None:
    log = get_logger("gr4_modtool.test")
    with caplog.at_level(logging.INFO, logger="gr4_modtool.test"):
        log_run(log, ["ctest", "--test-dir", "build"], cwd="/tmp/proj")
    assert "ctest --test-dir build" in caplog.text
    assert "/tmp/proj" in caplog.text


def test_log_exit_warns_on_failure(caplog) -> None:
    log = get_logger("gr4_modtool.test")
    with caplog.at_level(logging.INFO, logger="gr4_modtool.test"):
        log_exit(log, ["cmake"], 0)
        log_exit(log, ["cmake"], 2)
    levels = [r.levelno for r in caplog.records]
    assert levels == [logging.INFO, logging.WARNING]


def test_log_duration_emits_debug(caplog) -> None:
    log = get_logger("gr4_modtool.test")
    with caplog.at_level(logging.DEBUG, logger="gr4_modtool.test"):
        with log_duration(log, "rendering block.hpp.j2"):
            pass
    assert "rendering block.hpp.j2 took" in caplog.text


# ---------------------------------------------------------------------------
# fileops
# ---------------------------------------------------------------------------


def test_write_text_logs_creation(tmp_path, caplog) -> None:
    target = tmp_path / "a.txt"
    with caplog.at_level(logging.INFO, logger="gr4_modtool.fileops"):
        fileops.write_text(target, "hello")
    assert target.read_text() == "hello"
    assert "created" in caplog.text and str(target) in caplog.text


def test_write_text_logs_update(tmp_path, caplog) -> None:
    target = tmp_path / "a.txt"
    target.write_text("old")
    with caplog.at_level(logging.INFO, logger="gr4_modtool.fileops"):
        fileops.write_text(target, "new")
    assert "updated" in caplog.text


def test_write_text_returns_path(tmp_path) -> None:
    target = tmp_path / "a.txt"
    assert fileops.write_text(target, "x") == target


def test_ensure_dir_creates_parents(tmp_path) -> None:
    target = tmp_path / "a" / "b"
    assert fileops.ensure_dir(target).is_dir()
    fileops.ensure_dir(target)  # idempotent


def test_remove_file(tmp_path, caplog) -> None:
    target = tmp_path / "a.txt"
    target.write_text("x")
    with caplog.at_level(logging.INFO, logger="gr4_modtool.fileops"):
        assert fileops.remove_file(target) is True
    assert not target.exists()
    assert fileops.remove_file(target) is False
    with pytest.raises(FileNotFoundError):
        fileops.remove_file(target, missing_ok=False)


def test_remove_tree(tmp_path) -> None:
    target = tmp_path / "tree"
    (target / "nested").mkdir(parents=True)
    assert fileops.remove_tree(target) is True
    assert not target.exists()
    assert fileops.remove_tree(target) is False


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_cli_verbose_logs_written_files(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["-v", "newmod", "--project-dir", str(tmp_path), "--name", "gr4_logged", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "created" in result.output
    assert "CMakeLists.txt" in result.output


def test_cli_quiet_suppresses_progress(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--quiet", "newmod", "--project-dir", str(tmp_path), "--name", "gr4_quiet", "--yes"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "INFO" not in result.output


def test_cli_rejects_quiet_with_verbose(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["-v", "--quiet", "status"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_cli_log_file_captures_debug(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(ENV_FILE, raising=False)
    log_path = tmp_path / "run.log"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--log-file",
            str(log_path),
            "newmod",
            "--project-dir",
            str(tmp_path),
            "--name",
            "gr4_filelog",
            "--yes",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    for handler in logging.getLogger(ROOT_NAME).handlers:
        handler.flush()
    text = log_path.read_text()
    assert "rendering toplevel_CMakeLists.txt.j2" in text
    assert "created" in text
