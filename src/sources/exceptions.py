"""Exceptions raised by data sources."""

from __future__ import annotations


class SourceError(Exception):
    """Base class for all data-source errors."""


class SourceFetchError(SourceError):
    """Raised when a source fails to fetch its raw data.

    Typical causes: network timeout, HTTP 5xx, browser crash, auth failure,
    source website restructured.
    """


class SourceLoadError(SourceError):
    """Raised when a source fails to load the fetched file into a DataFrame.

    Typical causes: corrupted download, unexpected schema change, missing
    columns the source used to provide.
    """


class UnknownSourceError(SourceError):
    """Raised when looking up a source name that is not registered."""
