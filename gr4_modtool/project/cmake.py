"""CMakeLists.txt line-based reader/writer."""

from __future__ import annotations

import re
from pathlib import Path

from gr4_modtool.fileops import write_text
from gr4_modtool.log import get_logger

log = get_logger(__name__)


def append_test_entry(cmake_path: Path, block_name: str, target_libs: str) -> None:
    """Add a gr4_modtool_add_ut_test + target_link_libraries pair."""
    text = cmake_path.read_text()
    new_entry = (
        f"\ngr4_modtool_add_ut_test(qa_{block_name} qa_{block_name}.cpp)\n"
        f"target_link_libraries(qa_{block_name} PRIVATE {target_libs})\n"
    )
    log.debug("adding test target qa_%s to %s", block_name, cmake_path)
    write_text(cmake_path, text.rstrip() + new_entry)


def remove_test_entry(cmake_path: Path, block_name: str) -> bool:
    """Remove the ut_test + target_link_libraries lines for block_name. Returns True if found."""
    text = cmake_path.read_text()
    pattern = (
        rf"\ngr4_modtool_add_ut_test\(qa_{re.escape(block_name)}[^\n]*\)\n"
        rf"target_link_libraries\(qa_{re.escape(block_name)}[^\n]*\)\n?"
    )
    new_text, count = re.subn(pattern, "\n", text)
    if count:
        log.debug("removing test target qa_%s from %s", block_name, cmake_path)
        write_text(cmake_path, new_text)
    else:
        log.debug("no test target qa_%s found in %s", block_name, cmake_path)
    return count > 0


def rename_test_entry(cmake_path: Path, old_name: str, new_name: str) -> bool:
    """Rename old_name → new_name in ut_test + target_link_libraries lines."""
    text = cmake_path.read_text()
    new_text = re.sub(
        rf"\bqa_{re.escape(old_name)}\b",
        f"qa_{new_name}",
        text,
    )
    changed = new_text != text
    if changed:
        log.debug("renaming test target qa_%s -> qa_%s in %s", old_name, new_name, cmake_path)
        write_text(cmake_path, new_text)
    else:
        log.debug("no test target qa_%s found in %s", old_name, cmake_path)
    return changed


def add_subdirectory(cmake_path: Path, subdir: str) -> None:
    """Append add_subdirectory(subdir) if not already present."""
    text = cmake_path.read_text()
    entry = f"add_subdirectory({subdir})"
    if entry not in text:
        write_text(cmake_path, text.rstrip() + f"\n{entry}\n")
    else:
        log.debug("%s already has %s", cmake_path, entry)


def append_bench_entry(cmake_path: Path, block_name: str, target_libs: str) -> None:
    """Add an add_executable + target_link_libraries pair for a benchmark."""
    text = cmake_path.read_text()
    new_entry = (
        f"\nadd_executable(bench_{block_name} bench_{block_name}.cpp)\n"
        f"target_link_libraries(bench_{block_name} PRIVATE {target_libs})\n"
    )
    log.debug("adding benchmark target bench_%s to %s", block_name, cmake_path)
    write_text(cmake_path, text.rstrip() + new_entry)


def remove_bench_entry(cmake_path: Path, block_name: str) -> bool:
    """Remove add_executable + target_link_libraries for bench_block_name. Returns True if found."""
    text = cmake_path.read_text()
    pattern = (
        rf"\nadd_executable\(bench_{re.escape(block_name)}[^\n]*\)\n"
        rf"target_link_libraries\(bench_{re.escape(block_name)}[^\n]*\)\n?"
    )
    new_text, count = re.subn(pattern, "\n", text)
    if count:
        log.debug("removing benchmark target bench_%s from %s", block_name, cmake_path)
        write_text(cmake_path, new_text)
    else:
        log.debug("no benchmark target bench_%s found in %s", block_name, cmake_path)
    return count > 0


def rename_bench_entry(cmake_path: Path, old_name: str, new_name: str) -> bool:
    """Rename old_name → new_name in bench_ cmake entries."""
    text = cmake_path.read_text()
    new_text = re.sub(
        rf"\bbench_{re.escape(old_name)}\b",
        f"bench_{new_name}",
        text,
    )
    changed = new_text != text
    if changed:
        log.debug(
            "renaming benchmark target bench_%s -> bench_%s in %s", old_name, new_name, cmake_path
        )
        write_text(cmake_path, new_text)
    else:
        log.debug("no benchmark target bench_%s found in %s", old_name, cmake_path)
    return changed


def add_bench_subdirectory(cmake_path: Path) -> None:
    """Append ENABLE_BENCHMARKING-guarded benchmarks subdir to a group CMakeLists.txt."""
    text = cmake_path.read_text()
    if "add_subdirectory(benchmarks)" not in text:
        block = "\nif(ENABLE_BENCHMARKING)\n  add_subdirectory(benchmarks)\nendif()\n"
        write_text(cmake_path, text.rstrip() + block)


def add_group_to_blocks_cmake(blocks_cmake: Path, group_name: str, cmake_prefix: str) -> None:
    """Wire a new group into blocks/CMakeLists.txt:
    - add_subdirectory(group_name)
    - target_link_libraries on the aggregate blocks_headers target
    """
    text = blocks_cmake.read_text()

    # Add add_subdirectory before the aggregate library block
    subdir_line = f"add_subdirectory({group_name})"
    if subdir_line not in text:
        # Insert before the add_library(... blocks_headers ...) line
        text = re.sub(
            r"(add_library\([^\n]*blocks_headers[^\n]*\))",
            f"{subdir_line}\n\n\\1",
            text,
            count=1,
        )

    # Add link to aggregate target
    link_line = f"  {cmake_prefix}::blocks_{group_name}_headers"
    if link_line not in text:
        text = re.sub(
            r"(target_link_libraries\([^\n]*blocks_headers[^\n]*\n(?:[^\)]*\n)*?)(\))",
            rf"\1{link_line}\n\2",
            text,
            count=1,
        )

    log.debug("wiring group '%s' into %s", group_name, blocks_cmake)
    write_text(blocks_cmake, text)
