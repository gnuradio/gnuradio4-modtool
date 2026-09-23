"""Shared pytest fixtures for gr4_modtool tests."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from pathlib import Path

import pytest

from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.log import ROOT_NAME
from gr4_modtool.project.discovery import ProjectConfig, save_config


@pytest.fixture(autouse=True)
def isolate_logging():
    """Undo any configure_logging() a test performed, so handlers never leak."""
    logger = logging.getLogger(ROOT_NAME)
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        if handler not in handlers:
            handler.close()
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate


def async_test(coro_func):
    """Decorator that runs an async test function via asyncio.run().

    Sets __signature__ explicitly so pytest can still discover fixture parameters.
    """

    @functools.wraps(coro_func)
    def wrapper(*args, **kwargs):
        asyncio.run(coro_func(*args, **kwargs))

    wrapper.__signature__ = inspect.signature(coro_func)
    return wrapper


@pytest.fixture()
def project(tmp_path: Path) -> ProjectConfig:
    """Create a minimal fake project tree with one group ('basic')."""
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)

    # blocks/ directory
    blocks = tmp_path / "blocks"
    blocks.mkdir()
    (blocks / "CMakeLists.txt").write_text(
        "add_library(gr4_testmod_blocks_headers INTERFACE)\n"
        "add_library(gr4_testmod::blocks_headers ALIAS gr4_testmod_blocks_headers)\n"
        "target_link_libraries(gr4_testmod_blocks_headers INTERFACE)\n"
    )

    write_group_skeleton(cfg, "basic")
    return cfg


@pytest.fixture()
def project_flat(tmp_path: Path) -> ProjectConfig:
    """Minimal flat project — no groups."""
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={},
        flat=True,
    )
    save_config(cfg)
    blocks = tmp_path / "blocks"
    blocks.mkdir()
    cfg.block_include_dir().mkdir(parents=True)
    cfg.block_test_dir().mkdir(parents=True)
    (cfg.block_test_dir() / "CMakeLists.txt").write_text("# Tests for testmod blocks\n")
    (blocks / "CMakeLists.txt").write_text(
        "add_library(gr4_testmod_blocks_headers INTERFACE)\n"
        "add_library(gr4_testmod::blocks_headers ALIAS gr4_testmod_blocks_headers)\n"
        "target_link_libraries(gr4_testmod_blocks_headers INTERFACE)\n"
        "if(ENABLE_TESTING)\n  add_subdirectory(test)\nendif()\n"
    )
    return cfg


@pytest.fixture()
def project_two_groups(tmp_path: Path) -> ProjectConfig:
    """Minimal project with two groups: 'basic' and 'filter'."""
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic", "filter": "blocks/filter"},
    )
    save_config(cfg)

    blocks = tmp_path / "blocks"
    blocks.mkdir()
    (blocks / "CMakeLists.txt").write_text(
        "add_library(gr4_testmod_blocks_headers INTERFACE)\n"
        "add_library(gr4_testmod::blocks_headers ALIAS gr4_testmod_blocks_headers)\n"
        "target_link_libraries(gr4_testmod_blocks_headers INTERFACE)\n"
    )

    write_group_skeleton(cfg, "basic")
    write_group_skeleton(cfg, "filter")
    return cfg
