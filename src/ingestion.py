"""Entry point for data ingestion.

Usage:
    uv run python -m src.ingestion ponte_en_carrera
    uv run python -m src.ingestion                   # defaults to ponte_en_carrera
    uv run python -m src.ingestion --list            # show registered sources

This module is intentionally thin: it parses argv, loads config, looks
up the source class via the registry, and delegates to `source.run()`.
All the actual work (Selenium scraping, file persistence, DataFrame
loading) lives in the source's class under `src/sources/`.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .sources import UnknownSourceError, get_cls, list_sources

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


def run(source_name: str) -> None:
    """Fetch + persist + load a single source."""
    logger.info("========== INGESTION START (source=%s) ==========", source_name)
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
        names = list_sources()
        if names:
            print("Registered sources:")
            for name in names:
                print(f"  - {name}")
        else:
            print("No sources registered.")
        return 0
    try:
        run(args.source)
    except UnknownSourceError as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
