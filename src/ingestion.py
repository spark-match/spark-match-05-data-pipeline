"""Entry point for data ingestion.

Usage:
    uv run python -m src.ingestion ponte_en_carrera
    uv run python -m src.ingestion                   # defaults to ponte_en_carrera
    uv run python -m src.ingestion --list            # show active sources
    uv run python -m src.ingestion --list --all      # include deprecated sources
    uv run python -m src.ingestion --list-deprecated # show only deprecated sources

Deprecated sources can still be invoked explicitly (e.g., for diagnostics),
but the CLI prints a warning and the source's fetch() will likely raise.
See src/sources/README.md for the status of each registered source.

This module is intentionally thin: it parses argv, loads config, looks
up the source class via the registry, and delegates to `source.run()`.
The actual data acquisition logic lives in each source's class under
src/sources/.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .sources import UnknownSourceError, get_cls, list_deprecated, list_sources

logger = logging.getLogger(__name__)


def _build_source(source_name: str):
    """Resolve source name -> class -> instance from AppConfig.

    Centralizes the wiring between AppConfig and each source's specific
    constructor signature. Adding a new source here is the only change
    needed in the orchestrator.
    """
    config = load_config()
    cls = get_cls(source_name)  # raises UnknownSourceError

    if cls.__name__ == "PonteEnCarreraSource":
        return cls(
            data_dir=config.data_dir,
            snapshot_dir=config.snapshot_dir,
            url=config.pec_url,
            download_timeout_seconds=config.pec_timeout_seconds,
        )
    raise UnknownSourceError(f"No wiring defined for source class {cls.__name__}")


def _warn_if_deprecated(source_name: str, cls: type) -> None:
    """Log a clear warning if the requested source is marked deprecated."""
    if getattr(cls, "deprecated", False):
        logger.warning(
            "Source '%s' (%s) is DEPRECATED. Its fetch() will likely raise. "
            "See src/sources/README.md for status and replacement candidates.",
            source_name,
            cls.__name__,
        )


def run(source_name: str) -> None:
    """Fetch + persist + load a single source."""
    logger.info("========== INGESTION START (source=%s) ==========", source_name)
    cls = get_cls(source_name)
    _warn_if_deprecated(source_name, cls)
    source = _build_source(source_name)
    result = source.run()
    logger.info(
        "Source %s: %d rows x %d columns -> %s",
        result.source_name,
        result.rows,
        result.columns,
        result.raw_path,
    )
    if result.snapshot_path:
        logger.info("Snapshot: %s", result.snapshot_path)
    logger.info("========== INGESTION FINISHED ==========")


def _print_sources(
    active: list[str], deprecated: list[str], *, show_deprecated_marker: bool
) -> None:
    if active:
        print("Active sources:")
        for name in active:
            marker = " (deprecated)" if show_deprecated_marker and name in deprecated else ""
            print(f"  - {name}{marker}")
    else:
        print("No active sources registered.")
    if show_deprecated_marker and deprecated:
        names_in_active = set(active)
        only_deprecated = [n for n in deprecated if n not in names_in_active]
        if only_deprecated:
            print()
            print(
                "Deprecated sources (hidden from default --list, use --list-deprecated to inspect):"
            )
            for name in only_deprecated:
                print(f"  - {name}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ingestion",
        description="Run a data source ingestion",
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="ponte_en_carrera",
        help="Registered source name (default: ponte_en_carrera). Use --list to see all.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print registered source names and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --list: include deprecated sources in the listing",
    )
    parser.add_argument(
        "--list-deprecated",
        action="store_true",
        help="Print only deprecated source names and exit",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if args.list:
        active = list_sources(include_deprecated=args.all)
        deprecated = list_deprecated() if args.all else []
        _print_sources(active, deprecated, show_deprecated_marker=args.all)
        return 0
    if args.list_deprecated:
        deprecated = list_deprecated()
        if deprecated:
            print("Deprecated sources:")
            for name in deprecated:
                print(f"  - {name}")
        else:
            print("No deprecated sources registered.")
        return 0
    try:
        run(args.source)
    except UnknownSourceError as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
