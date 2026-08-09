"""Abstract base class for all data sources.

A data source is any external system we pull raw data from: a government
portal scraped with Selenium, an API returning JSON, a CSV exported by a
partner, etc. This module defines the contract every source must satisfy.

Design notes:
- A source's lifecycle is split into two pure steps (fetch + load) and one
  orchestrating step (run). The split makes each step independently
  testable: you can test load() on a fixture file without driving a browser.
- Persistence (moving the downloaded file into DATA_DIR) and snapshotting
  (timestamped copy in SNAPSHOT_DIR) are shared concerns implemented here
  so subclasses do not reinvent them.
- Sources register themselves by class name through `registry.register`
  (see `registry.py`). No central list to maintain.
"""

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of a successful source run.

    Attributes:
        source_name: Registered name of the source.
        raw_path: Path to the persisted raw file (input to load()).
        rows: Number of rows in the loaded DataFrame.
        columns: Number of columns in the loaded DataFrame.
        snapshot_path: Path to the timestamped snapshot, or None if skipped.
    """

    source_name: str
    raw_path: Path
    rows: int
    columns: int
    snapshot_path: Path | None = None


class DataSource(ABC):
    """Abstract base class for all data sources.

    Subclasses must define:
        - `name` (class variable): unique identifier used by the registry.
        - `fetch()`: download/copy the raw file. Returns the downloaded path.
        - `load(path)`: read the raw file into a DataFrame. Pure function.

    Subclasses inherit:
        - `run()`: default orchestrator (fetch -> snapshot -> persist -> load).
        - `_persist(downloaded)`: move to `data_dir / name / <filename>`.
        - `_snapshot(downloaded)`: copy to `snapshots / name / raw_<ts>.<ext>`.

    Subclasses may define:
        - `deprecated` (class var, default False): if True, the source is
          excluded from `registry.list_sources()` by default and the CLI
          prints a warning before invoking it. Deprecated sources typically
          have a `fetch()` that raises `SourceFetchError` explaining why
          (e.g., upstream portal decommissioned), but keep `load()` working
          so any historical data already persisted can still be read.
    """

    name: str = ""
    deprecated: bool = False

    def __init__(
        self,
        *,
        data_dir: Path,
        snapshot_dir: Path,
    ) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define class var `name`")
        self.data_dir = data_dir
        self.snapshot_dir = snapshot_dir

    @abstractmethod
    def fetch(self) -> Path:
        """Download the raw file from the upstream source.

        Returns:
            Path to the downloaded file (in a temp/location the source chooses).
            The caller will then call _snapshot and _persist on this path.
        """
        raise NotImplementedError

    @abstractmethod
    def load(self, path: Path) -> pd.DataFrame:
        """Load a raw file into a DataFrame.

        This is a pure function: same input -> same output. Sources should
        not perform any I/O or side effects here; that belongs in fetch().

        Args:
            path: Location of a raw file, as produced by fetch() + _persist().

        Returns:
            DataFrame with the source's raw schema (no cleaning, no renaming).
        """
        raise NotImplementedError

    def run(self) -> IngestionResult:
        """Default end-to-end orchestration: fetch, snapshot, persist, load.

        Subclasses should NOT need to override this. If a source has a more
        complex flow (e.g., multi-file, paginated API), override `run` and
        call super() for the common parts.
        """
        logger.info("=== %s: fetch ===", self.name)
        downloaded = self.fetch()

        logger.info("=== %s: snapshot ===", self.name)
        snapshot_path = self._snapshot(downloaded)

        logger.info("=== %s: persist ===", self.name)
        raw_path = self._persist(downloaded)

        logger.info("=== %s: load ===", self.name)
        df = self.load(raw_path)

        return IngestionResult(
            source_name=self.name,
            raw_path=raw_path,
            rows=len(df),
            columns=len(df.columns),
            snapshot_path=snapshot_path,
        )

    def _persist(self, downloaded: Path) -> Path:
        """Move the downloaded file into `data_dir / self.name / raw.<ext>`.

        Canonicalizes the filename to `raw.<ext>` regardless of what the
        upstream source called it. Replaces any existing target.
        """
        target_dir = self.data_dir / self.name
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"raw{downloaded.suffix}"
        if target.exists():
            target.unlink()
        shutil.move(str(downloaded), str(target))
        logger.info("Raw dataset updated: %s", target)
        return target

    def _snapshot(self, downloaded: Path) -> Path | None:
        """Save a timestamped copy in `snapshot_dir / self.name / raw_<ts>.<ext>`.

        Returns None if the downloaded file no longer exists (e.g., already
        moved by a custom run() implementation).
        """
        if not downloaded.exists():
            return None
        target_dir = self.snapshot_dir / self.name
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = target_dir / f"raw_{timestamp}{downloaded.suffix}"
        shutil.copy2(downloaded, target)
        logger.info("Snapshot saved: %s", target.name)
        return target
