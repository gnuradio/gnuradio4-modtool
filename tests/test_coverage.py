"""Tests for the coverage command and its public helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from gr4_modtool.commands.coverage import (
    _coverage_flags,
    _detect_tool,
    _run_gcovr,
    coverage_test_env,
    detect_coverage_tool,
    regenerate_coverage_report,
    run_coverage,
)


def _mock_popen(returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.wait.return_value = returncode
    return m


# ---------------------------------------------------------------------------
# _detect_tool / detect_coverage_tool
# ---------------------------------------------------------------------------


def test_detect_tool_gcovr() -> None:
    with patch("shutil.which", side_effect=lambda t: "/usr/bin/gcovr" if t == "gcovr" else None):
        assert _detect_tool("gcovr") == "gcovr"


def test_detect_tool_llvm_cov() -> None:
    with patch(
        "shutil.which", side_effect=lambda t: "/usr/bin/llvm-cov" if t == "llvm-cov" else None
    ):
        assert _detect_tool("llvm-cov") == "llvm-cov"


def test_detect_tool_auto_prefers_gcovr() -> None:
    with patch("shutil.which", return_value="/usr/bin/tool"):
        assert _detect_tool("auto") == "gcovr"


def test_detect_tool_auto_falls_back_to_llvm_cov() -> None:
    with patch("shutil.which", side_effect=lambda t: None if t == "gcovr" else "/usr/bin/llvm-cov"):
        assert _detect_tool("auto") == "llvm-cov"


def test_detect_tool_returns_none_when_missing() -> None:
    with patch("shutil.which", return_value=None):
        assert _detect_tool("auto") is None


def test_detect_coverage_tool_public_matches_private() -> None:
    with patch("shutil.which", return_value="/usr/bin/gcovr"):
        assert detect_coverage_tool("auto") == _detect_tool("auto")


# ---------------------------------------------------------------------------
# _coverage_flags
# ---------------------------------------------------------------------------


def test_coverage_flags_gcovr(tmp_path: Path) -> None:
    cmake_args, test_env = _coverage_flags("gcovr", tmp_path)
    assert any("--coverage" in a for a in cmake_args)
    assert test_env == {}


def test_coverage_flags_llvm_cov(tmp_path: Path) -> None:
    cmake_args, test_env = _coverage_flags("llvm-cov", tmp_path)
    assert any("-fprofile-instr-generate" in a for a in cmake_args)
    assert "LLVM_PROFILE_FILE" in test_env


# ---------------------------------------------------------------------------
# coverage_test_env
# ---------------------------------------------------------------------------


def test_coverage_test_env_gcovr_is_empty(tmp_path: Path) -> None:
    assert coverage_test_env("gcovr", tmp_path) == {}


def test_coverage_test_env_llvm_cov_has_profile_file(tmp_path: Path) -> None:
    env = coverage_test_env("llvm-cov", tmp_path)
    assert "LLVM_PROFILE_FILE" in env
    assert str(tmp_path) in env["LLVM_PROFILE_FILE"]


# ---------------------------------------------------------------------------
# regenerate_coverage_report
# ---------------------------------------------------------------------------


def test_regenerate_report_calls_gcovr(tmp_path: Path) -> None:
    build_dir = tmp_path / "build-coverage"
    build_dir.mkdir()
    output_dir = tmp_path / "coverage"
    output_dir.mkdir()
    with (
        patch("gr4_modtool.commands.coverage._detect_tool", return_value="gcovr"),
        patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen,
    ):
        rc = regenerate_coverage_report(tmp_path, build_dir, "gcovr", output_dir)
    assert rc == 0
    args = mock_popen.call_args[0][0]
    assert args[0] == "gcovr"


def test_regenerate_report_no_tool_returns_error(tmp_path: Path) -> None:
    with patch("gr4_modtool.commands.coverage._detect_tool", return_value=None):
        rc = regenerate_coverage_report(tmp_path, tmp_path, "auto", tmp_path / "cov")
    assert rc == 1


def test_regenerate_report_creates_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "new_coverage_dir"
    assert not output_dir.exists()
    with (
        patch("gr4_modtool.commands.coverage._detect_tool", return_value="gcovr"),
        patch("subprocess.Popen", return_value=_mock_popen()),
    ):
        regenerate_coverage_report(tmp_path, tmp_path, "gcovr", output_dir)
    assert output_dir.exists()


# ---------------------------------------------------------------------------
# _run_gcovr
# ---------------------------------------------------------------------------


def test_run_gcovr_command(tmp_path: Path) -> None:
    output_dir = tmp_path / "coverage"
    output_dir.mkdir()
    build_dir = tmp_path / "build-coverage"
    build_dir.mkdir()
    with patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen:
        _run_gcovr(tmp_path, build_dir, output_dir)
    args = mock_popen.call_args[0][0]
    assert args[0] == "gcovr"
    assert "--html-details" in args
    assert str(output_dir / "index.html") in args


# ---------------------------------------------------------------------------
# run_coverage — browser and no-browser
# ---------------------------------------------------------------------------


def test_coverage_opens_browser(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("")
    (tmp_path / "build-coverage").mkdir()
    html = tmp_path / "coverage" / "index.html"

    with (
        patch("gr4_modtool.commands.coverage._detect_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.coverage.run_build", return_value=0),
        patch("gr4_modtool.commands.coverage._run_tests", return_value=0),
        patch(
            "gr4_modtool.commands.coverage._run_gcovr",
            side_effect=lambda *_: (
                html.parent.mkdir(parents=True, exist_ok=True) or html.write_text("") or 0
            ),
        ),
        patch("gr4_modtool.commands.coverage.webbrowser") as mock_wb,
    ):
        run_coverage(tmp_path, tmp_path / "build-coverage", open_browser=True)

    mock_wb.open.assert_called_once()
    assert "index.html" in mock_wb.open.call_args[0][0]


def test_coverage_no_open_skips_browser(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("")
    (tmp_path / "build-coverage").mkdir()
    html = tmp_path / "coverage" / "index.html"

    with (
        patch("gr4_modtool.commands.coverage._detect_tool", return_value="gcovr"),
        patch("gr4_modtool.commands.coverage.run_build", return_value=0),
        patch("gr4_modtool.commands.coverage._run_tests", return_value=0),
        patch(
            "gr4_modtool.commands.coverage._run_gcovr",
            side_effect=lambda *_: (
                html.parent.mkdir(parents=True, exist_ok=True) or html.write_text("") or 0
            ),
        ),
        patch("gr4_modtool.commands.coverage.webbrowser") as mock_wb,
    ):
        run_coverage(tmp_path, tmp_path / "build-coverage", open_browser=False)

    mock_wb.open.assert_not_called()
