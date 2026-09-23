"""Tests for project name → namespace / cmake-prefix derivation."""

from __future__ import annotations

import pytest

from gr4_modtool.project.discovery import default_cmake_prefix, default_namespace


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("mymod", "gr::mymod"),
        ("gr4_josh", "gr::josh"),
        ("gr4-josh", "gr::josh"),
        ("gr_josh", "gr::josh"),
        ("gr-josh", "gr::josh"),
        ("My Blocks", "gr::my_blocks"),
        ("gr4_", "gr::gr4_"),  # degenerate name: never strip down to empty
    ],
)
def test_default_namespace(name: str, expected: str) -> None:
    assert default_namespace(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("mymod", "gr4_mymod"),
        ("gr4_josh", "gr4_josh"),
        ("gr-josh", "gr4_josh"),
    ],
)
def test_default_cmake_prefix(name: str, expected: str) -> None:
    assert default_cmake_prefix(name) == expected
