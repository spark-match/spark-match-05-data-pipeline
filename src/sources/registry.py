"""Registry of data sources.

Sources register themselves by applying `@register` to their class. The
orchestrator (src/ingestion.py) looks them up by name via `get_cls`.

Why a registry:
- New sources are added in a single place (their own file) without touching
  ingestion.py. The dispatch table is auto-populated at import time.
- Tests can introspect the registry to assert which sources are available.
- Future CLI flag `--source <name>` works without a manual if/elif chain.

This is a deliberate "plugin-lite" pattern: import the concrete source
module from src/sources/__init__.py so registration happens.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .exceptions import UnknownSourceError

if TYPE_CHECKING:
    from .base import DataSource

logger = logging.getLogger(__name__)


_REGISTRY: dict[str, type[DataSource]] = {}


def register(cls: type[DataSource]) -> type[DataSource]:
    """Class decorator: register a DataSource subclass under its `name`.

    Raises:
        ValueError: If the class does not define `name`, or if another class
            is already registered under that name.
    """
    name = getattr(cls, "name", "")
    if not name:
        raise ValueError(f"{cls.__name__} must define class var `name` to be registered")
    if name in _REGISTRY:
        existing = _REGISTRY[name].__name__
        raise ValueError(
            f"Source name '{name}' already registered to {existing}; cannot re-register to {cls.__name__}"
        )
    _REGISTRY[name] = cls
    logger.debug("Registered source: %s -> %s", name, cls.__name__)
    return cls


def get_cls(name: str) -> type[DataSource]:
    """Look up a registered source class by name.

    Raises:
        UnknownSourceError: If no source is registered under `name`.
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise UnknownSourceError(f"Unknown source '{name}'. Available: {available}")
    return _REGISTRY[name]


def list_sources(*, include_deprecated: bool = False) -> list[str]:
    """Return the sorted names of registered sources.

    Args:
        include_deprecated: If False (default), sources whose class sets
            `deprecated = True` are filtered out. Pass True to include them
            (useful for diagnostics and the CLI --all flag).
    """
    if include_deprecated:
        return sorted(_REGISTRY.keys())
    return sorted(name for name, cls in _REGISTRY.items() if not getattr(cls, "deprecated", False))


def list_deprecated() -> list[str]:
    """Return the sorted names of registered sources marked deprecated."""
    return sorted(name for name, cls in _REGISTRY.items() if getattr(cls, "deprecated", False))


def snapshot() -> dict[str, type[DataSource]]:
    """Return a shallow copy of the registry. Use with `restore()` for tests."""
    return dict(_REGISTRY)


def restore(saved: dict[str, type[DataSource]]) -> None:
    """Restore the registry from a `snapshot()`. Intended for tests only.

    The registry will be in the exact state it was when snapshot() was called,
    regardless of what registrations or resets happened in between.
    """
    _REGISTRY.clear()
    _REGISTRY.update(saved)


def reset() -> None:
    """Clear the registry. Intended for tests only."""
    _REGISTRY.clear()
