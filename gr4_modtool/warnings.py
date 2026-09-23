"""GR4-modtools warnings module."""

from __future__ import annotations

import functools as _functools
import warnings as _warnings
from typing import TYPE_CHECKING, ParamSpec, TypeVar, overload

if TYPE_CHECKING:
    from collections.abc import Callable

_P = ParamSpec("_P")
_R = TypeVar("_R")


class ExperimentalWarning(UserWarning):
    """Warning for experimental features."""


class Gr4DeprecationWarning(DeprecationWarning):
    """Warning for deprecated gr4_modtool features."""


# DeprecationWarning is ignored by default outside __main__; make both
# categories visible (once per location) to CLI users.
_warnings.simplefilter("default", ExperimentalWarning)
_warnings.simplefilter("default", Gr4DeprecationWarning)


def _mark(
    category: type[Warning],
    label: str,
    reason: str | Callable[_P, _R],
) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        message = f"{func.__qualname__} is {label}"
        if isinstance(reason, str) and reason:
            message += f": {reason}"

        @_functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            _warnings.warn(message, category, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    # Support bare @experimental / @deprecated (no parentheses).
    if callable(reason):
        return decorator(reason)
    return decorator


@overload
def experimental(reason: Callable[_P, _R]) -> Callable[_P, _R]: ...
@overload
def experimental(reason: str = ...) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...
def experimental(
    reason: str | Callable[_P, _R] = "",
) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Mark a function as experimental; calls emit an ExperimentalWarning."""
    return _mark(ExperimentalWarning, "experimental", reason)


@overload
def deprecated(reason: Callable[_P, _R]) -> Callable[_P, _R]: ...
@overload
def deprecated(reason: str = ...) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...
def deprecated(
    reason: str | Callable[_P, _R] = "",
) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Mark a function as deprecated; calls emit a Gr4DeprecationWarning."""
    return _mark(Gr4DeprecationWarning, "deprecated", reason)


def warn_experimental(feature: str, reason: str = "", stacklevel: int = 2) -> None:
    """Emit an ExperimentalWarning for *feature* at the caller's location.

    ``stacklevel`` counts from this helper like ``warnings.warn``: the
    default of 2 attributes the warning to the caller.
    """
    message = f"{feature} is experimental"
    if reason:
        message += f": {reason}"
    _warnings.warn(message, ExperimentalWarning, stacklevel=stacklevel)


def warn_deprecated(feature: str, reason: str = "", stacklevel: int = 2) -> None:
    """Emit a Gr4DeprecationWarning for *feature* at the caller's location.

    ``stacklevel`` counts from this helper like ``warnings.warn``: the
    default of 2 attributes the warning to the caller.
    """
    message = f"{feature} is deprecated"
    if reason:
        message += f": {reason}"
    _warnings.warn(message, Gr4DeprecationWarning, stacklevel=stacklevel)
