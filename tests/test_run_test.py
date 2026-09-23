"""Tests for run_test (gr4_modtool test) command."""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gr4_modtool.commands.lint_headers import LintIssue
from gr4_modtool.commands.run_test import (
    _find_block_info,
    _find_watch_dir,
    _incremental_build,
    cmd,
    run_block_test,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _mock_popen(returncode: int = 0) -> MagicMock:
    mock = MagicMock()
    mock.wait.return_value = returncode
    return mock


class _FakeObserver:
    def schedule(self, *a, **kw):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def join(self):
        pass


class _FireEventObserver:
    """Fires provided events synchronously inside start() so handler code is exercised."""

    def __init__(self, events: list) -> None:
        self._events = events
        self._handler = None

    def schedule(self, handler, *a, **kw) -> None:
        self._handler = handler

    def start(self) -> None:
        for ev in self._events:
            if self._handler:
                self._handler.on_modified(ev)

    def stop(self) -> None:
        pass

    def join(self) -> None:
        pass


@pytest.fixture()
def cmake_root(tmp_path: Path) -> Path:
    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.22)\n")
    (tmp_path / "build").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# run_block_test
# ---------------------------------------------------------------------------


def test_run_block_test_cmake_uses_ctest(cmake_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        run_block_test(cmake_root, cmake_root / "build", "MyFilter")
    args = mock_popen.call_args[0][0]
    assert args[0] == "ctest"
    assert "-R" in args
    assert "qa_MyFilter" in args


def test_run_block_test_verbose_flag(cmake_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        run_block_test(cmake_root, cmake_root / "build", "MyFilter", verbose=True)
    args = mock_popen.call_args[0][0]
    assert "--verbose" in args


def test_run_block_test_extra_env_merged(cmake_root: Path) -> None:
    """extra_env values are present in the env passed to Popen."""
    env_seen: dict = {}

    def fake_popen(cmd, *, env=None, **kwargs):
        if env:
            env_seen.update(env)
        return _mock_popen()

    with patch("subprocess.Popen", side_effect=fake_popen):
        run_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            extra_env={"LLVM_PROFILE_FILE": "/tmp/cov.profraw"},
        )

    assert env_seen.get("LLVM_PROFILE_FILE") == "/tmp/cov.profraw"


def test_run_block_test_no_extra_env_passes_none(cmake_root: Path) -> None:
    """Without extra_env the env kwarg to Popen is None (inherits process env)."""
    env_seen = []

    def fake_popen(cmd, *, env=None, **kwargs):
        env_seen.append(env)
        return _mock_popen()

    with patch("subprocess.Popen", side_effect=fake_popen):
        run_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert env_seen[0] is None


# ---------------------------------------------------------------------------
# _incremental_build
# ---------------------------------------------------------------------------


def test_incremental_build_cmake(cmake_root: Path) -> None:
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        _incremental_build(cmake_root, cmake_root / "build", "MyFilter")
    args = mock_popen.call_args[0][0]
    assert args[:2] == ["cmake", "--build"]
    assert "--target" in args
    assert "qa_MyFilter" in args


# ---------------------------------------------------------------------------
# --watch flag and handler tests
# ---------------------------------------------------------------------------


def test_watch_flag_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(cmd, ["--help"])
    assert "--watch" in result.output
    assert "-w" in result.output


def test_watch_coverage_flag_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cmd, ["--help"])
    assert "--coverage" in result.output
    assert "--coverage-dir" in result.output
    assert "--coverage-output" in result.output
    assert "--coverage-tool" in result.output


def test_watch_handler_triggers_rebuild(cmake_root: Path) -> None:
    """On a .hpp modified event, _run_once calls incremental build then test."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_dir = cmake_root / "build"
    calls = []

    def fake_incremental(root, bd, name):
        calls.append(("build", name))
        return 0

    def fake_test(root, bd, name, *, verbose=False, extra_env=None):
        calls.append(("test", name))
        return 0

    with (
        patch("gr4_modtool.commands.run_test._incremental_build", side_effect=fake_incremental),
        patch("gr4_modtool.commands.run_test.run_block_test", side_effect=fake_test),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, build_dir, "MyFilter")

    assert ("build", "MyFilter") in calls
    assert ("test", "MyFilter") in calls


def test_watch_debounce(cmake_root: Path) -> None:
    """Two on_modified calls within the debounce window produce only one build."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_calls = []

    def fake_incremental(root, bd, name):
        build_calls.append(name)
        return 0

    class DebounceObserver:
        _handler = None

        def schedule(self, handler, *a, **kw):
            DebounceObserver._handler = handler

        def start(self):
            ev = types.SimpleNamespace(is_directory=False, src_path=str(cmake_root / "foo.hpp"))
            DebounceObserver._handler.on_modified(ev)
            DebounceObserver._handler.on_modified(ev)

        def stop(self):
            pass

        def join(self):
            pass

    times = iter([0.0, 2.0, 2.0])

    def fake_monotonic():
        return next(times)

    with (
        patch("gr4_modtool.commands.run_test._incremental_build", side_effect=fake_incremental),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=DebounceObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = fake_monotonic
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(build_calls) == 2


# ---------------------------------------------------------------------------
# lint integration tests
# ---------------------------------------------------------------------------


def test_watch_runs_lint_each_cycle(cmake_root: Path) -> None:
    """lint_header is called once per watch cycle when block info is found."""
    from gr4_modtool.commands.run_test import watch_block_test

    lint_calls: list = []

    with (
        patch(
            "gr4_modtool.commands.run_test._find_block_info",
            return_value=(cmake_root / "MyFilter.hpp", "basic"),
        ),
        patch(
            "gr4_modtool.commands.run_test._lint_header",
            side_effect=lambda hpp, grp: lint_calls.append(hpp) or [],
        ),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(lint_calls) >= 1


def test_watch_lint_issues_do_not_block_build(cmake_root: Path) -> None:
    """Build proceeds even when lint reports errors."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_calls: list = []
    lint_error = LintIssue("basic", "MyFilter", "missing GR_REGISTER_BLOCK macro", "error")

    with (
        patch(
            "gr4_modtool.commands.run_test._find_block_info",
            return_value=(cmake_root / "MyFilter.hpp", "basic"),
        ),
        patch("gr4_modtool.commands.run_test._lint_header", return_value=[lint_error]),
        patch(
            "gr4_modtool.commands.run_test._incremental_build",
            side_effect=lambda *a: build_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(build_calls) >= 1


# ---------------------------------------------------------------------------
# --watch --coverage integration
# ---------------------------------------------------------------------------


def test_watch_coverage_regenerates_report_after_success(cmake_root: Path) -> None:
    """After a passing test run, regenerate_coverage_report is called."""
    from gr4_modtool.commands.run_test import watch_block_test

    report_calls: list = []
    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.run_test.coverage_test_env", return_value={}),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch(
            "gr4_modtool.commands.run_test.regenerate_coverage_report",
            side_effect=lambda *a, **kw: report_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_output=cmake_root / "coverage",
            coverage_tool="gcovr",
        )

    assert len(report_calls) >= 1


def test_watch_coverage_skips_report_on_build_fail(cmake_root: Path) -> None:
    """Coverage report is not regenerated when the build fails."""
    from gr4_modtool.commands.run_test import watch_block_test

    report_calls: list = []
    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.run_test.coverage_test_env", return_value={}),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=1),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch(
            "gr4_modtool.commands.run_test.regenerate_coverage_report",
            side_effect=lambda *a, **kw: report_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_output=cmake_root / "coverage",
            coverage_tool="gcovr",
        )

    assert report_calls == []


def test_watch_coverage_skips_report_on_test_fail(cmake_root: Path) -> None:
    """Coverage report is not regenerated when tests fail."""
    from gr4_modtool.commands.run_test import watch_block_test

    report_calls: list = []
    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.run_test.coverage_test_env", return_value={}),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=1),
        patch(
            "gr4_modtool.commands.run_test.regenerate_coverage_report",
            side_effect=lambda *a, **kw: report_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_output=cmake_root / "coverage",
            coverage_tool="gcovr",
        )

    assert report_calls == []


def test_watch_coverage_missing_dir_exits(cmake_root: Path) -> None:
    """SystemExit if coverage_dir does not exist."""
    from gr4_modtool.commands.run_test import watch_block_test

    with pytest.raises(SystemExit):
        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=cmake_root / "nonexistent-build",
        )


def test_watch_coverage_llvm_cov_passes_env(cmake_root: Path) -> None:
    """For llvm-cov, run_block_test is called with LLVM_PROFILE_FILE in extra_env."""
    from gr4_modtool.commands.run_test import watch_block_test

    test_env_seen: list = []
    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()

    def fake_test(root, bd, name, *, verbose=False, extra_env=None):
        test_env_seen.append(extra_env)
        return 0

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value="llvm-cov"),
        patch(
            "gr4_modtool.commands.run_test.coverage_test_env",
            return_value={"LLVM_PROFILE_FILE": "/tmp/cov.profraw"},
        ),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", side_effect=fake_test),
        patch("gr4_modtool.commands.run_test.regenerate_coverage_report", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_output=cmake_root / "coverage",
            coverage_tool="llvm-cov",
        )

    assert test_env_seen and test_env_seen[0] == {"LLVM_PROFILE_FILE": "/tmp/cov.profraw"}


# ---------------------------------------------------------------------------
# _find_block_info
# ---------------------------------------------------------------------------


def test_find_block_info_found(cmake_root: Path) -> None:
    """Returns (path, group_name) when block is present in config."""
    mock_block = MagicMock()
    mock_block.name = "MyFilter"
    mock_block.path = cmake_root / "MyFilter.hpp"
    mock_group = MagicMock()
    mock_group.name = "dsp"
    mock_group.blocks = [mock_block]

    with (
        patch("gr4_modtool.project.discovery.load_config", return_value=MagicMock()),
        patch("gr4_modtool.project.discovery.discover_groups", return_value=[mock_group]),
    ):
        result = _find_block_info(cmake_root, "MyFilter")

    assert result == (cmake_root / "MyFilter.hpp", "dsp")


def test_find_block_info_not_found(cmake_root: Path) -> None:
    """Returns None when the block name is not in any group."""
    mock_group = MagicMock()
    mock_group.blocks = []

    with (
        patch("gr4_modtool.project.discovery.load_config", return_value=MagicMock()),
        patch("gr4_modtool.project.discovery.discover_groups", return_value=[mock_group]),
    ):
        result = _find_block_info(cmake_root, "MyFilter")

    assert result is None


def test_find_block_info_exception_returns_none(cmake_root: Path) -> None:
    """Returns None when load_config raises (no .gr4modtool.toml)."""
    with patch("gr4_modtool.project.discovery.load_config", side_effect=RuntimeError("no config")):
        result = _find_block_info(cmake_root, "MyFilter")

    assert result is None


# ---------------------------------------------------------------------------
# _find_watch_dir
# ---------------------------------------------------------------------------


def test_find_watch_dir_returns_include_dir(cmake_root: Path) -> None:
    """Returns the group include dir from config when the block is found."""
    include_dir = cmake_root / "include" / "mymod" / "dsp"
    mock_block = MagicMock()
    mock_block.name = "MyFilter"
    mock_group = MagicMock()
    mock_group.name = "dsp"
    mock_group.blocks = [mock_block]
    mock_cfg = MagicMock()
    mock_cfg.group_include_dir.return_value = include_dir

    with (
        patch("gr4_modtool.project.discovery.load_config", return_value=mock_cfg),
        patch("gr4_modtool.project.discovery.discover_groups", return_value=[mock_group]),
    ):
        result = _find_watch_dir(cmake_root, "MyFilter")

    assert result == include_dir


def test_find_watch_dir_falls_back_to_blocks(cmake_root: Path) -> None:
    """Falls back to blocks/ when the block is not found and that directory exists."""
    blocks_dir = cmake_root / "blocks"
    blocks_dir.mkdir()

    with patch("gr4_modtool.project.discovery.load_config", side_effect=RuntimeError):
        result = _find_watch_dir(cmake_root, "MyFilter")

    assert result == blocks_dir


def test_find_watch_dir_falls_back_to_project_root(cmake_root: Path) -> None:
    """Falls back to project_root when blocks/ also does not exist."""
    with patch("gr4_modtool.project.discovery.load_config", side_effect=RuntimeError):
        result = _find_watch_dir(cmake_root, "MyFilter")

    assert result == cmake_root


# ---------------------------------------------------------------------------
# Handler event filtering
# ---------------------------------------------------------------------------


def test_handler_ignores_non_hpp_events(cmake_root: Path) -> None:
    """on_modified with a .cpp path does not trigger a rebuild cycle."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_calls: list = []
    ev = types.SimpleNamespace(is_directory=False, src_path=str(cmake_root / "foo.cpp"))

    with (
        patch(
            "gr4_modtool.commands.run_test._incremental_build",
            side_effect=lambda *a: build_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch(
            "gr4_modtool.commands.run_test._Observer",
            return_value=_FireEventObserver([ev]),
        ),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 0.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(build_calls) == 1  # only the startup cycle; event was ignored


def test_handler_ignores_directory_events(cmake_root: Path) -> None:
    """on_modified with is_directory=True does not trigger a rebuild cycle."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_calls: list = []
    ev = types.SimpleNamespace(is_directory=True, src_path=str(cmake_root / "subdir.hpp"))

    with (
        patch(
            "gr4_modtool.commands.run_test._incremental_build",
            side_effect=lambda *a: build_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch(
            "gr4_modtool.commands.run_test._Observer",
            return_value=_FireEventObserver([ev]),
        ),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 0.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(build_calls) == 1  # only the startup cycle; directory event ignored


def test_handler_triggers_build_on_hpp_event(cmake_root: Path) -> None:
    """on_modified with a .hpp path triggers an additional rebuild cycle."""
    from gr4_modtool.commands.run_test import watch_block_test

    build_calls: list = []
    ev = types.SimpleNamespace(is_directory=False, src_path=str(cmake_root / "MyFilter.hpp"))
    times = iter([0.0, 999.0])

    with (
        patch(
            "gr4_modtool.commands.run_test._incremental_build",
            side_effect=lambda *a: build_calls.append(True) or 0,
        ),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch(
            "gr4_modtool.commands.run_test._Observer",
            return_value=_FireEventObserver([ev]),
        ),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = lambda: next(times)
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert len(build_calls) == 2  # startup + event-triggered cycle


# ---------------------------------------------------------------------------
# Miscellaneous watch-mode tests
# ---------------------------------------------------------------------------


def test_watch_watchdog_unavailable_exits(cmake_root: Path) -> None:
    """watch_block_test raises SystemExit when watchdog is not installed."""
    from gr4_modtool.commands import run_test

    orig = run_test._WATCHDOG_AVAILABLE
    run_test._WATCHDOG_AVAILABLE = False
    try:
        with pytest.raises(SystemExit):
            run_test.watch_block_test(cmake_root, cmake_root / "build", "MyFilter")
    finally:
        run_test._WATCHDOG_AVAILABLE = orig


def test_watch_block_info_not_found_skips_lint(cmake_root: Path) -> None:
    """No lint call and no crash when _find_block_info returns None."""
    from gr4_modtool.commands.run_test import watch_block_test

    lint_calls: list = []

    with (
        patch("gr4_modtool.commands.run_test._find_block_info", return_value=None),
        patch(
            "gr4_modtool.commands.run_test._lint_header",
            side_effect=lambda *a: lint_calls.append(True),
        ),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert lint_calls == []


def test_watch_verbose_propagated(cmake_root: Path) -> None:
    """verbose=True is forwarded to run_block_test."""
    from gr4_modtool.commands.run_test import watch_block_test

    verbose_seen: list = []

    def fake_test(root, bd, name, *, verbose=False, extra_env=None):
        verbose_seen.append(verbose)
        return 0

    with (
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", side_effect=fake_test),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter", verbose=True)

    assert verbose_seen and verbose_seen[0] is True


def test_watch_coverage_tool_not_found_exits(cmake_root: Path) -> None:
    """SystemExit when the coverage tool cannot be detected."""
    from gr4_modtool.commands.run_test import watch_block_test

    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value=None),
        pytest.raises(SystemExit),
    ):
        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_tool="gcovr",
        )


def test_watch_coverage_uses_coverage_dir_as_build(cmake_root: Path) -> None:
    """Incremental builds use coverage_dir, not the default build_dir."""
    from gr4_modtool.commands.run_test import watch_block_test

    coverage_dir = cmake_root / "build-coverage"
    coverage_dir.mkdir()
    build_dirs_seen: list = []

    def fake_incremental(root, bd, name):
        build_dirs_seen.append(bd)
        return 0

    with (
        patch("gr4_modtool.commands.run_test.detect_coverage_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.run_test.coverage_test_env", return_value={}),
        patch("gr4_modtool.commands.run_test._incremental_build", side_effect=fake_incremental),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test.regenerate_coverage_report", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=_FakeObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(
            cmake_root,
            cmake_root / "build",
            "MyFilter",
            coverage_dir=coverage_dir,
            coverage_output=cmake_root / "coverage",
            coverage_tool="gcovr",
        )

    assert build_dirs_seen and all(bd == coverage_dir for bd in build_dirs_seen)


def test_watch_observer_scheduled_on_watch_dir(cmake_root: Path) -> None:
    """Observer.schedule receives the path returned by _find_watch_dir."""
    from gr4_modtool.commands.run_test import watch_block_test

    watch_dir = cmake_root / "include" / "mymod" / "dsp"
    scheduled_dirs: list = []

    class CapturingObserver(_FakeObserver):
        def schedule(self, handler, path, **kw) -> None:
            scheduled_dirs.append(path)

    with (
        patch("gr4_modtool.commands.run_test._find_watch_dir", return_value=watch_dir),
        patch("gr4_modtool.commands.run_test._incremental_build", return_value=0),
        patch("gr4_modtool.commands.run_test.run_block_test", return_value=0),
        patch("gr4_modtool.commands.run_test._Observer", return_value=CapturingObserver()),
        patch("gr4_modtool.commands.run_test.time") as mock_time,
    ):
        mock_time.monotonic.return_value = 999.0
        mock_time.strftime.return_value = "00:00:00"
        mock_time.sleep.side_effect = KeyboardInterrupt

        watch_block_test(cmake_root, cmake_root / "build", "MyFilter")

    assert scheduled_dirs and scheduled_dirs[0] == str(watch_dir)


# ---------------------------------------------------------------------------
# CLI-layer tests
# ---------------------------------------------------------------------------


def test_cli_coverage_requires_watch(cmake_root: Path) -> None:
    """--coverage without --watch exits non-zero."""
    runner = CliRunner()
    result = runner.invoke(cmd, ["MyFilter", "--coverage", "--project-dir", str(cmake_root)])
    assert result.exit_code != 0


def test_cli_missing_build_dir_non_watch(cmake_root: Path) -> None:
    """Non-watch mode exits non-zero when the build directory doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        ["MyFilter", "--build-dir", "nonexistent", "--project-dir", str(cmake_root)],
    )
    assert result.exit_code != 0


def test_cli_missing_build_dir_watch_no_coverage(cmake_root: Path) -> None:
    """Watch mode without coverage exits non-zero when the build directory doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "MyFilter",
            "--watch",
            "--build-dir",
            "nonexistent",
            "--project-dir",
            str(cmake_root),
        ],
    )
    assert result.exit_code != 0


def test_cli_exit_code_propagated(cmake_root: Path) -> None:
    """The exit code returned by run_block_test is forwarded through the CLI."""
    runner = CliRunner()
    with patch("gr4_modtool.commands.run_test.run_block_test", return_value=5):
        result = runner.invoke(
            cmd,
            ["MyFilter", "--project-dir", str(cmake_root), "--build-dir", "build"],
        )
    assert result.exit_code == 5
