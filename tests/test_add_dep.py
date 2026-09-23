"""Tests for the add-dep command."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.add_dep import add_cmake_dep

_DEPS_CMAKE_CONTENT = """\
include_guard(GLOBAL)

find_package(PkgConfig REQUIRED)

function(gr4_mymod_resolve_dependencies)
  pkg_check_modules(GR4_OOT_GR4 REQUIRED IMPORTED_TARGET gnuradio4)
  set(GR4_OOT_GNURADIO4_TARGET PkgConfig::GR4_OOT_GR4 PARENT_SCOPE)
endfunction()
"""


@pytest.fixture()
def deps_cmake(tmp_path: Path) -> Path:
    cmake_dir = tmp_path / "cmake"
    cmake_dir.mkdir()
    p = cmake_dir / "Dependencies.cmake"
    p.write_text(_DEPS_CMAKE_CONTENT)
    return p


def test_add_dep_pkg_config_cmake(deps_cmake: Path) -> None:
    add_cmake_dep(deps_cmake, "FFTW3", pkg_name="fftw3", cmake_pkg=None)
    text = deps_cmake.read_text()
    assert "pkg_check_modules(FFTW3" in text
    assert "fftw3" in text
    assert "FFTW3_TARGET" in text


def test_add_dep_cmake_package(deps_cmake: Path) -> None:
    add_cmake_dep(deps_cmake, "Eigen3", pkg_name=None, cmake_pkg="Eigen3")
    text = deps_cmake.read_text()
    assert "find_package(Eigen3 REQUIRED)" in text
    assert "Eigen3_TARGET" in text


def test_add_dep_raises_if_already_present(deps_cmake: Path) -> None:
    add_cmake_dep(deps_cmake, "FFTW3", pkg_name="fftw3", cmake_pkg=None)
    with pytest.raises(ValueError, match="FFTW3"):
        add_cmake_dep(deps_cmake, "FFTW3", pkg_name="fftw3", cmake_pkg=None)
