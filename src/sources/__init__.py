"""Data sources for the Spark Match data pipeline.

Each source knows how to fetch its raw data from an external system and
load it into a DataFrame. Sources register themselves with the registry
when their module is imported.

To add a new source:
    1. Create `src/sources/<my_source>.py` with a class that subclasses
       `DataSource` and is decorated with `@register`.
    2. Add an `import` line below for the new module so its
       `@register` decorator runs at import time.
    3. Optionally extend `src/config.py` if the source needs new env vars.

The orchestrator (`src/ingestion.py`) only needs to know the source name;
how the data is fetched is opaque to it.
"""

from __future__ import annotations

from .base import DataSource, IngestionResult
from .exceptions import SourceError, SourceFetchError, SourceLoadError, UnknownSourceError

# Import concrete sources so their @register decorators run on package import.
# Order does not matter; each source is independent.
from .ponte_en_carrera import PonteEnCarreraSource
from .registry import (
    get_cls,
    list_deprecated,
    list_sources,
    register,
    reset,
    restore,
    snapshot,
)

__all__ = [
    "DataSource",
    "IngestionResult",
    "PonteEnCarreraSource",
    "SourceError",
    "SourceFetchError",
    "SourceLoadError",
    "UnknownSourceError",
    "get_cls",
    "list_deprecated",
    "list_sources",
    "register",
    "reset",
    "restore",
    "snapshot",
]
