"""E2E build tests — actually compile and run generated code.

These tests are marked ``slow`` and are skipped unless:
  * cmake is installed
  * gnuradio4 pkg-config package is available

Run with:  pytest tests/e2e/test_build_and_run.py -m slow -v
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from gr4_modtool.commands.newmod import write_project
from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke, write_spec

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.slow


def _cmake_available() -> bool:
    return bool(shutil.which("cmake"))


def _installed_gr4_compiler() -> tuple[str, int] | None:
    """Return ("gcc"|"clang", major) that built the installed libgnuradio-core.a, or None."""
    try:
        result = subprocess.run(
            ["pkg-config", "--variable=libdir", "gnuradio4"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = (Path(result.stdout.strip()) / "libgnuradio-core.a").read_bytes()
    except Exception:
        return None
    match = re.search(rb"GCC: \([^)]*\) (\d+)\.", data)
    if match:
        return ("gcc", int(match.group(1)))
    match = re.search(rb"clang version (\d+)\.", data)
    if match:
        return ("clang", int(match.group(1)))
    return None


def _cxx14_compiler() -> str | None:
    """Return path to a C++23-capable compiler (g++-14 or later), or None.

    Candidates from the same family as — but older than — the compiler that
    built the installed gnuradio4 are skipped: their standard library may
    lack symbols the library references.
    """
    lib_compiler = _installed_gr4_compiler()
    for candidate in ("g++-14", "g++-15", "g++-16", "clang++-19", "clang++-18"):
        path = shutil.which(candidate)
        if not path:
            continue
        match = re.fullmatch(r"(g\+\+|clang\+\+)-(\d+)", candidate)
        if match and lib_compiler is not None:
            family = "gcc" if match.group(1) == "g++" else "clang"
            if family == lib_compiler[0] and int(match.group(2)) < lib_compiler[1]:
                continue
        return path
    return None


def _gnuradio4_available() -> bool:
    """Return True if gnuradio4 pkg-config package is present AND a C++23 compiler is available."""
    if not _cmake_available():
        return False
    if not _cxx14_compiler():
        return False
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", "gnuradio4"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


skip_no_build = pytest.mark.skipif(not _cmake_available(), reason="cmake not installed")
skip_no_gr4 = pytest.mark.skipif(
    not _gnuradio4_available(),
    reason="gnuradio4 not available or no C++23-capable compiler found",
)


# ---------------------------------------------------------------------------
# Buildable project fixtures
# ---------------------------------------------------------------------------


def _make_buildable_project(root: Path, flat: bool = False) -> ProjectConfig:
    """Create a complete cmake-able project using write_project."""
    root.mkdir(parents=True, exist_ok=True)
    first_group = "" if flat else "basic"
    groups = {} if flat else {"basic": "blocks/basic"}
    cfg = ProjectConfig(
        root=root,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups=groups,
        flat=flat,
    )
    write_project(
        cfg,
        first_group,
        gen_git=False,
        gen_devcontainer=False,
        gen_clang=False,
        gen_ci_clang=False,
        gen_presets=False,
        gen_ci_sanitizers=False,
        gen_ci_matrix=False,
        gen_vscode=False,
        gen_ci_coverage=False,
        gen_ci_release=False,
        gen_precommit=False,
        gen_doxyfile=False,
    )
    return cfg


@pytest.fixture()
def project_buildable(tmp_path: Path) -> ProjectConfig:
    """Complete cmake-able grouped project (basic group, cmake only)."""
    return _make_buildable_project(tmp_path / "project")


@pytest.fixture()
def project_flat_buildable(tmp_path: Path) -> ProjectConfig:
    """Complete cmake-able flat project (cmake only, no groups)."""
    return _make_buildable_project(tmp_path / "project", flat=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmake_build(project_root: Path, build_dir: Path) -> subprocess.CompletedProcess:
    """Configure and build the project; return the cmake --build result."""
    build_dir.mkdir(parents=True, exist_ok=True)
    compiler = _cxx14_compiler()
    cmake_args = ["cmake", str(project_root), "-G", "Ninja", "-DENABLE_TESTING=ON"]
    if compiler:
        cmake_args.append(f"-DCMAKE_CXX_COMPILER={compiler}")
    configure = subprocess.run(
        cmake_args,
        cwd=build_dir,
        capture_output=True,
        text=True,
    )
    assert configure.returncode == 0, (
        f"cmake configure failed:\n{configure.stdout}\n{configure.stderr}"
    )
    build = subprocess.run(
        ["cmake", "--build", str(build_dir), "-j4"],
        capture_output=True,
        text=True,
    )
    return build


def _ctest(build_dir: Path, test_name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-R", test_name, "--output-on-failure"],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Grouped project — build and test
# ---------------------------------------------------------------------------


@skip_no_build
@skip_no_gr4
def test_grouped_project_builds(project_buildable: ProjectConfig, tmp_path: Path) -> None:
    """A generated grouped project configures and builds with cmake."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_buildable.root, "newblock", "--spec", str(spec))

    build_dir = tmp_path / "build"
    result = _cmake_build(project_buildable.root, build_dir)
    assert result.returncode == 0, f"Build failed:\n{result.stdout}\n{result.stderr}"


@skip_no_build
@skip_no_gr4
def test_grouped_project_test_passes(project_buildable: ProjectConfig, tmp_path: Path) -> None:
    """The generated qa_* test binary runs and exits 0 under ctest."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_buildable.root, "newblock", "--spec", str(spec))

    build_dir = tmp_path / "build"
    _cmake_build(project_buildable.root, build_dir)
    result = _ctest(build_dir, "qa_MyFilter")
    assert result.returncode == 0, f"ctest failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# Flat project — build and test
# ---------------------------------------------------------------------------


@skip_no_build
@skip_no_gr4
def test_flat_project_builds(project_flat_buildable: ProjectConfig, tmp_path: Path) -> None:
    """A flat project configures and builds with cmake."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="", archetype="sync")
    invoke(project_flat_buildable.root, "newblock", "--spec", str(spec))

    build_dir = tmp_path / "build"
    result = _cmake_build(project_flat_buildable.root, build_dir)
    assert result.returncode == 0, f"Build failed:\n{result.stdout}\n{result.stderr}"


@skip_no_build
@skip_no_gr4
def test_flat_project_test_passes(project_flat_buildable: ProjectConfig, tmp_path: Path) -> None:
    """The flat-project qa_* test runs and exits 0 under ctest."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="", archetype="sync")
    invoke(project_flat_buildable.root, "newblock", "--spec", str(spec))

    build_dir = tmp_path / "build"
    _cmake_build(project_flat_buildable.root, build_dir)
    result = _ctest(build_dir, "qa_MyFilter")
    assert result.returncode == 0, f"ctest failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# Rename → build ensures renamed project still compiles
# ---------------------------------------------------------------------------


@skip_no_build
@skip_no_gr4
def test_renamed_block_builds(project_buildable: ProjectConfig, tmp_path: Path) -> None:
    """A block renamed via CLI still compiles under cmake."""
    spec = write_spec(tmp_path / "spec.yaml", "Alpha", group="basic")
    invoke(project_buildable.root, "newblock", "--spec", str(spec))
    invoke(project_buildable.root, "rename", "--group", "basic", "Alpha", "Beta", "-y")

    build_dir = tmp_path / "build"
    result = _cmake_build(project_buildable.root, build_dir)
    assert result.returncode == 0, f"Build failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# gr4_modtool build command (end-to-end via CLI)
# ---------------------------------------------------------------------------


@skip_no_build
@skip_no_gr4
def test_build_command_configures_and_builds(
    project_buildable: ProjectConfig, tmp_path: Path
) -> None:
    """The 'build' CLI command exits 0 on a well-formed grouped project."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_buildable.root, "newblock", "--spec", str(spec))
    compiler = _cxx14_compiler()
    extra = ["--cmake-args", f"-DCMAKE_CXX_COMPILER={compiler}"] if compiler else []
    invoke(project_buildable.root, "build", *extra)


@skip_no_build
@skip_no_gr4
def test_build_and_test_command(project_buildable: ProjectConfig, tmp_path: Path) -> None:
    """The 'build --test' CLI command builds and runs tests, exits 0."""
    spec = write_spec(tmp_path / "spec.yaml", "MyFilter", group="basic")
    invoke(project_buildable.root, "newblock", "--spec", str(spec))
    compiler = _cxx14_compiler()
    extra = ["--cmake-args", f"-DCMAKE_CXX_COMPILER={compiler}"] if compiler else []
    invoke(project_buildable.root, "build", "--test", *extra)
