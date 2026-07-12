"""Tests for src/sources/base.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.sources.base import DataSource, IngestionResult


class DummySource(DataSource):
    """Minimal concrete subclass used to exercise DataSource behavior."""

    name = "dummy_test"

    def __init__(self, *, data_dir: Path, snapshot_dir: Path) -> None:
        super().__init__(data_dir=data_dir, snapshot_dir=snapshot_dir)
        self.fetched_marker: Path | None = None

    def fetch(self) -> Path:
        # Create a fake "downloaded" file inside data_dir.
        marker = self.data_dir / self.name / "downloaded.xlsx"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_bytes(b"fake xlsx bytes")
        self.fetched_marker = marker
        return marker

    def load(self, path: Path) -> pd.DataFrame:
        # Return a 3x2 DataFrame to keep the run() flow simple.
        return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


def test_cannot_instantiate_data_source_directly():
    with pytest.raises(TypeError):
        DataSource(data_dir=Path("/tmp"), snapshot_dir=Path("/tmp"))  # type: ignore[abstract]


def test_subclass_without_name_raises_at_init(tmp_path: Path):
    class Nameless(DataSource):
        name = ""

        def fetch(self):
            raise NotImplementedError

        def load(self, path):
            raise NotImplementedError

    with pytest.raises(ValueError, match="must define class var `name`"):
        Nameless(data_dir=tmp_path, snapshot_dir=tmp_path)


def test_run_returns_ingestion_result_with_metadata(tmp_path: Path):
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    result = src.run()

    assert isinstance(result, IngestionResult)
    assert result.source_name == "dummy_test"
    assert result.rows == 3
    assert result.columns == 2
    assert result.raw_path.exists()
    assert result.snapshot_path is not None and result.snapshot_path.exists()


def test_persist_renames_to_raw_ext(tmp_path: Path):
    """The persisted file should be named raw.<ext>, not the temp name."""
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    result = src.run()

    assert result.raw_path.name == "raw.xlsx"
    assert result.raw_path.parent == tmp_path / "data" / "dummy_test"


def test_persist_replaces_existing_file(tmp_path: Path):
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    src.run()
    src.run()  # second run should not fail if raw.xlsx already exists

    final = tmp_path / "data" / "dummy_test" / "raw.xlsx"
    assert final.exists()


def test_snapshot_filename_includes_timestamp(tmp_path: Path):
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    result = src.run()

    assert result.snapshot_path is not None
    assert "raw_" in result.snapshot_path.name
    assert result.snapshot_path.suffix == ".xlsx"


def test_two_runs_produce_distinct_snapshots(tmp_path: Path):
    """Two runs in the same second should still produce different snapshots.

    Implementation detail: the timestamp uses %Y%m%d_%H%M%S_%f (microseconds).
    This avoids accidental overwrites when scripts run in tight loops or
    when CI re-runs a failed job within the same second.
    """
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    first = src.run()
    second = src.run()

    assert first.snapshot_path != second.snapshot_path
    assert first.snapshot_path.exists()
    assert second.snapshot_path.exists()


def test_snapshot_returns_none_if_downloaded_missing(tmp_path: Path):
    """If the source has already moved the file before snapshot, return None."""
    src = DummySource(data_dir=tmp_path / "data", snapshot_dir=tmp_path / "snap")
    # Run once to consume the normal flow
    src.run()
    # Snapshot a path that doesn't exist
    missing = tmp_path / "data" / "dummy_test" / "never_existed.xlsx"
    assert src._snapshot(missing) is None
