"""Utility decorators for meadows-tui."""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from textual.css.query import NoMatches

F = TypeVar("F", bound=Callable[..., Any])


def ignore_no_match(func: F) -> F:
    """Decorator: silently return if a `query_one` raises `NoMatches`.

    Intended for theme-application and focus methods that may run
    before the target widget is mounted.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NoMatches:
            return None

    return wrapper  # type: ignore[return-value]


__all__ = ["ignore_no_match"]
