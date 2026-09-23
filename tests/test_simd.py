"""Tests for --simd flag on newblock."""

from __future__ import annotations

from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig


def _simd_answers(style: str = "processOne", simd: bool = True) -> dict:
    return {
        "group_name": "basic",
        "block_name": "VectorScale",
        "description": "Scales each sample by a constant.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": style,
        "type_list": "float, double",
        "gen_test": False,
        "simd": simd,
    }


def test_simd_block_creates_header(project: ProjectConfig) -> None:
    written = write_block_files(project, _simd_answers())
    header = project.group_include_dir("basic") / "VectorScale.hpp"
    assert header in written
    assert header.exists()


def test_simd_uses_process_bulk(project: ProjectConfig) -> None:
    write_block_files(project, _simd_answers())
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "processBulk" in text


def test_simd_has_span_in_signature(project: ProjectConfig) -> None:
    write_block_files(project, _simd_answers())
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "std::span" in text


def test_simd_no_process_one(project: ProjectConfig) -> None:
    write_block_files(project, _simd_answers())
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "processOne" not in text


def test_simd_has_pragma_ivdep(project: ProjectConfig) -> None:
    write_block_files(project, _simd_answers())
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "#pragma GCC ivdep" in text


def test_simd_has_loop_skeleton(project: ProjectConfig) -> None:
    write_block_files(project, _simd_answers())
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "for (std::size_t i = 0; i != n; ++i)" in text


def test_simd_forces_process_bulk_even_if_style_is_process_one(project: ProjectConfig) -> None:
    """simd=True overrides processing_style=processOne."""
    answers = _simd_answers(style="processOne", simd=True)
    write_block_files(project, answers)
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "processBulk" in text
    assert "processOne" not in text


def test_regular_block_uses_process_one(project: ProjectConfig) -> None:
    """Without --simd, a filter archetype block keeps processOne."""
    answers = _simd_answers(style="processOne", simd=False)
    write_block_files(project, answers)
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "processOne" in text
    assert "#pragma GCC ivdep" not in text


def test_simd_sink_no_output_loop(project: ProjectConfig) -> None:
    """Sink block (no out_ports) generates loop without output assignment line."""
    answers = {
        "group_name": "basic",
        "block_name": "VectorScale",
        "description": "Sink.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [],
        "processing_style": "processBulk",
        "type_list": "float, double",
        "gen_test": False,
        "simd": True,
    }
    write_block_files(project, answers)
    text = (project.group_include_dir("basic") / "VectorScale.hpp").read_text()
    assert "#pragma GCC ivdep" in text
    assert "for (std::size_t i" in text


def test_simd_cli_flag(project: ProjectConfig) -> None:
    """--simd flag accepted by the CLI (integration smoke test via write_block_files)."""
    answers = _simd_answers(simd=True)
    write_block_files(project, answers)
    header = project.group_include_dir("basic") / "VectorScale.hpp"
    assert header.exists()
    assert "#pragma GCC ivdep" in header.read_text()
