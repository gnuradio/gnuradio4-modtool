"""Tests for the gr4_modtool.warnings module."""

from __future__ import annotations

import warnings

import pytest

from gr4_modtool.warnings import (
    ExperimentalWarning,
    Gr4DeprecationWarning,
    deprecated,
    experimental,
    warn_deprecated,
    warn_experimental,
)


def test_experimental_warning_is_user_warning() -> None:
    assert issubclass(ExperimentalWarning, UserWarning)


def test_gr4_deprecation_warning_is_deprecation_warning() -> None:
    assert issubclass(Gr4DeprecationWarning, DeprecationWarning)


def test_experimental_decorator_bare() -> None:
    @experimental
    def func() -> int:
        return 42

    with pytest.warns(ExperimentalWarning, match="func is experimental"):
        assert func() == 42


def test_experimental_decorator_with_reason() -> None:
    @experimental("API may change")
    def func() -> int:
        return 42

    with pytest.warns(ExperimentalWarning, match="func is experimental: API may change"):
        assert func() == 42


def test_deprecated_decorator_bare() -> None:
    @deprecated
    def func() -> int:
        return 7

    with pytest.warns(Gr4DeprecationWarning, match="func is deprecated"):
        assert func() == 7


def test_deprecated_decorator_with_reason() -> None:
    @deprecated("use new_func() instead")
    def func() -> int:
        return 7

    with pytest.warns(Gr4DeprecationWarning, match="func is deprecated: use new_func"):
        assert func() == 7


def test_decorator_preserves_metadata() -> None:
    @experimental("unstable")
    def documented() -> None:
        """Docstring survives wrapping."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "Docstring survives wrapping."


def test_decorator_passes_args_and_kwargs() -> None:
    @deprecated
    def add(a: int, b: int = 0) -> int:
        return a + b

    with pytest.warns(Gr4DeprecationWarning):
        assert add(1, b=2) == 3


def test_warning_points_at_caller() -> None:
    @experimental
    def func() -> None:
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        func()

    assert len(caught) == 1
    assert caught[0].filename == __file__


def test_warn_experimental() -> None:
    with pytest.warns(ExperimentalWarning, match="meson backend is experimental"):
        warn_experimental("meson backend")


def test_warn_experimental_with_reason() -> None:
    with pytest.warns(ExperimentalWarning, match="meson backend is experimental: layout may change"):
        warn_experimental("meson backend", "layout may change")


def test_warn_deprecated() -> None:
    with pytest.warns(Gr4DeprecationWarning, match="--old-flag is deprecated"):
        warn_deprecated("--old-flag")


def test_warn_deprecated_with_reason() -> None:
    with pytest.warns(Gr4DeprecationWarning, match="--old-flag is deprecated: use --new-flag"):
        warn_deprecated("--old-flag", "use --new-flag")


def test_warn_helpers_point_at_caller() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_deprecated("--old-flag")

    assert len(caught) == 1
    assert caught[0].filename == __file__


def test_categories_visible_by_default() -> None:
    # The module installs "default" filters so its warnings are not
    # swallowed by Python's default DeprecationWarning suppression.
    with warnings.catch_warnings(record=True) as caught:
        warnings.resetwarnings()
        warnings.simplefilter("default", ExperimentalWarning)
        warnings.simplefilter("default", Gr4DeprecationWarning)
        warn_experimental("thing")
        warn_deprecated("thing")

    categories = {w.category for w in caught}
    assert categories == {ExperimentalWarning, Gr4DeprecationWarning}
