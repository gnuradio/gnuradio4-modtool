"""Tests for newbench command."""

import pytest

from gr4_modtool.commands.newbench import write_bench_file
from gr4_modtool.commands.newblock import write_block_files
from gr4_modtool.project.discovery import ProjectConfig


def _basic_answers(block: str = "MyFilter") -> dict:
    return {
        "group_name": "basic",
        "block_name": block,
        "description": "Test block.",
        "template_params": ["T"],
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
        "type_list": "float, double",
        "gen_test": False,
    }


def test_newbench_creates_file(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    written = write_bench_file(project, "basic", "MyFilter")
    assert (project.group_bench_dir("basic") / "bench_MyFilter.cpp").exists()
    assert any("bench_MyFilter.cpp" in str(p) for p in written)


def test_newbench_content_has_chrono(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter")
    text = (project.group_bench_dir("basic") / "bench_MyFilter.cpp").read_text()
    assert "#include <chrono>" in text


def test_newbench_content_has_csv_output(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter")
    text = (project.group_bench_dir("basic") / "bench_MyFilter.cpp").read_text()
    assert "throughput" in text.lower() or "MSas" in text or "printf" in text


def test_newbench_wire_build_creates_cmake(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter", wire_build=True)
    assert (project.group_bench_dir("basic") / "CMakeLists.txt").exists()


def test_newbench_wire_build_appends_cmake_entry(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter", wire_build=True)
    cmake_text = (project.group_bench_dir("basic") / "CMakeLists.txt").read_text()
    assert "bench_MyFilter" in cmake_text


def test_newbench_wire_build_updates_group_cmake(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter", wire_build=True)
    group_cmake = project.group_path("basic") / "CMakeLists.txt"
    text = group_cmake.read_text()
    assert "ENABLE_BENCHMARKING" in text
    assert "add_subdirectory(benchmarks)" in text


def test_newbench_wire_build_subdir_idempotent(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter", wire_build=True)
    write_block_files(project, _basic_answers("MyFilter2"))
    write_bench_file(project, "basic", "MyFilter2", wire_build=True)
    group_cmake = project.group_path("basic") / "CMakeLists.txt"
    text = group_cmake.read_text()
    assert text.count("add_subdirectory(benchmarks)") == 1


def test_newbench_raises_if_header_missing(project: ProjectConfig) -> None:
    with pytest.raises(FileNotFoundError):
        write_bench_file(project, "basic", "Ghost")


def test_newbench_raises_if_bench_exists(project: ProjectConfig) -> None:
    write_block_files(project, _basic_answers())
    write_bench_file(project, "basic", "MyFilter")
    with pytest.raises(FileExistsError):
        write_bench_file(project, "basic", "MyFilter")
