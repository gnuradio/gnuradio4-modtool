"""Tests for format command."""

from unittest.mock import MagicMock, patch

from gr4_modtool.commands.format import format_files
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(block: str = "MyFilter") -> dict:
    return {
        "group_name": "basic",
        "block_name": block,
        "description": "Test.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": True,
    }


def _mock_popen(returncode: int = 0):
    mock = MagicMock()
    mock.wait.return_value = returncode
    return mock


def test_format_collects_hpp_and_cpp_files(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    with (
        patch("shutil.which", return_value="/usr/bin/clang-format"),
        patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen,
    ):
        format_files(project)
    file_args = mock_popen.call_args[0][0]
    assert any(f.endswith(".hpp") for f in file_args)
    assert any(f.endswith(".cpp") for f in file_args)


def test_format_check_mode_uses_dry_run(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    with (
        patch("shutil.which", return_value="/usr/bin/clang-format"),
        patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen,
    ):
        format_files(project, check_only=True)
    cmd_args = mock_popen.call_args[0][0]
    assert "--dry-run" in cmd_args
    assert "--Werror" in cmd_args
    assert "-i" not in cmd_args


def test_format_graceful_if_not_installed(project: ProjectConfig) -> None:
    with patch("shutil.which", return_value=None):
        rc = format_files(project)
    assert rc == 0


def test_format_group_filter(project_two_groups: ProjectConfig) -> None:
    cfg = project_two_groups
    write_block_files(cfg, _basic_answers())
    with (
        patch("shutil.which", return_value="/usr/bin/clang-format"),
        patch("subprocess.Popen", return_value=_mock_popen()) as mock_popen,
    ):
        format_files(cfg, groups=["basic"])
    file_args = mock_popen.call_args[0][0]
    # Should not include paths from the "filter" group directory (use /filter/ to
    # avoid matching the test function name in the pytest tmp_path)
    assert not any("/filter/" in f for f in file_args)
