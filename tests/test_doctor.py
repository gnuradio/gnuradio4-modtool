"""Tests for gr4_modtool doctor command (all unit tests — no real tools invoked)."""

from __future__ import annotations

import json
import sys
from collections import namedtuple
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from gr4_modtool.commands.doctor import (
    _check_cmake,
    _check_cxx_compiler,
    _check_gnuradio4,
    _check_optional_tools,
    _check_python,
    cmd,
    run_doctor,
)

_VersionInfo = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])

# ---------------------------------------------------------------------------
# Python check
# ---------------------------------------------------------------------------


def test_python_ok(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", _VersionInfo(3, 11, 0, "final", 0))
    results = _check_python()
    assert results[0].status == "ok"


def test_python_too_old(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", _VersionInfo(3, 10, 5, "final", 0))
    results = _check_python()
    assert results[0].status == "error"
    assert "3.10" in results[0].detail


# ---------------------------------------------------------------------------
# cmake check
# ---------------------------------------------------------------------------


def test_cmake_skipped() -> None:
    results = _check_cmake(need_cmake=False)
    assert results[0].status == "skip"


def test_cmake_missing() -> None:
    with patch("shutil.which", return_value=None):
        results = _check_cmake(need_cmake=True)
    assert results[0].status == "error"
    assert "not found" in results[0].detail


def test_cmake_ok() -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/cmake"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(stdout="cmake version 3.29.0\n", stderr="")
        results = _check_cmake(need_cmake=True)
    assert results[0].status == "ok"
    assert "3.29" in results[0].detail


def test_cmake_too_old() -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/cmake"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(stdout="cmake version 3.18.4\n", stderr="")
        results = _check_cmake(need_cmake=True)
    assert results[0].status == "error"
    assert "3.18" in results[0].detail


# ---------------------------------------------------------------------------
# C++ compiler check
# ---------------------------------------------------------------------------


def test_cxx_compiler_gcc() -> None:
    def fake_which(tool):
        return "/usr/bin/g++" if tool == "g++" else None

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(stdout="g++ (Ubuntu 13.2.0)\n", stderr="")
        results = _check_cxx_compiler()
    assert results[0].status == "ok"
    assert "g++" in results[0].detail


def test_cxx_compiler_clang() -> None:
    def fake_which(tool):
        return "/usr/bin/clang++" if tool == "clang++" else None

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(stdout="clang version 17.0.0\n", stderr="")
        results = _check_cxx_compiler()
    assert results[0].status == "ok"
    assert "clang++" in results[0].detail


def test_cxx_compiler_missing() -> None:
    with patch("shutil.which", return_value=None):
        results = _check_cxx_compiler()
    assert results[0].status == "error"


# ---------------------------------------------------------------------------
# gnuradio4 check
# ---------------------------------------------------------------------------


def test_gnuradio4_skip_no_pkgconfig() -> None:
    with patch("shutil.which", return_value=None):
        result = _check_gnuradio4()
    assert result.status == "skip"


def test_gnuradio4_ok() -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/pkg-config"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="4.1.0\n")
        result = _check_gnuradio4()
    assert result.status == "ok"
    assert "4.1.0" in result.detail


def test_gnuradio4_missing() -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/pkg-config"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = _check_gnuradio4()
    assert result.status == "error"


# ---------------------------------------------------------------------------
# Optional tools check
# ---------------------------------------------------------------------------


def test_optional_tools_all_present() -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/tool"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(stdout="1.0.0\n", stderr="")
        results = _check_optional_tools()
    assert all(r.status == "info" for r in results)
    assert not any(r.status == "error" for r in results)


def test_optional_tools_all_missing() -> None:
    with patch("shutil.which", return_value=None):
        results = _check_optional_tools()
    assert all(r.status == "info" for r in results)
    assert not any(r.status == "error" for r in results)


# ---------------------------------------------------------------------------
# run_doctor — project-awareness
# ---------------------------------------------------------------------------


def test_project_aware_skips_cmake(monkeypatch) -> None:
    """Project with build_cmake=False → cmake is skipped."""
    cfg = SimpleNamespace(build_cmake=False)
    with (
        patch("shutil.which", return_value="/usr/bin/tool"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0\n", stderr="")
        results = run_doctor(cfg)
    cmake_results = [r for r in results if r.name == "cmake"]
    assert cmake_results[0].status == "skip"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _all_ok_run(*args, **kwargs):
    """subprocess.run mock that returns a successful version response."""
    return MagicMock(returncode=0, stdout="3.29.0\n", stderr="")


def test_cli_exits_0_when_ok() -> None:
    runner = CliRunner()
    with (
        patch("shutil.which", return_value="/usr/bin/tool"),
        patch("subprocess.run", side_effect=_all_ok_run),
        patch.object(sys, "version_info", _VersionInfo(3, 12, 0, "final", 0)),
    ):
        result = runner.invoke(cmd, [])
    assert result.exit_code == 0


def test_cli_exits_1_on_error() -> None:
    runner = CliRunner()

    def which_no_cmake(tool):
        return None if tool == "cmake" else "/usr/bin/" + tool

    with (
        patch("shutil.which", side_effect=which_no_cmake),
        patch("subprocess.run", side_effect=_all_ok_run),
        patch.object(sys, "version_info", _VersionInfo(3, 12, 0, "final", 0)),
    ):
        result = runner.invoke(cmd, [])
    assert result.exit_code == 1


def test_cli_json_output() -> None:
    runner = CliRunner()
    with (
        patch("shutil.which", return_value="/usr/bin/tool"),
        patch("subprocess.run", side_effect=_all_ok_run),
        patch.object(sys, "version_info", _VersionInfo(3, 12, 0, "final", 0)),
    ):
        result = runner.invoke(cmd, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("name" in item and "status" in item and "detail" in item for item in data)
