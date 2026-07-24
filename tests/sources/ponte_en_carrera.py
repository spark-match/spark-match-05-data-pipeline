"""Tests for src/sources/ponte_en_carrera.py.

PEC is deprecated (upstream portal decommissioned 2026-07-12). Tests cover:
- Construction still works (kept for backward compat with existing wiring).
- load() still works on historical raw files (so data_clean.py can process
  the git-tracked raw.xlsx).
- fetch() raises SourceFetchError with a clear, actionable message.
- Source is registered but flagged deprecated; list_sources() hides it
  by default but include_deprecated=True reveals it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.sources import SourceFetchError
from src.sources.ponte_en_carrera import DEPRECATED_URL, PonteEnCarreraSource


@pytest.fixture
def pec(tmp_path: Path) -> PonteEnCarreraSource:
    return PonteEnCarreraSource(
        url=DEPRECATED_URL,
        data_dir=tmp_path / "data",
        snapshot_dir=tmp_path / "snap",
        download_timeout_seconds=5,
        headless=True,
    )


def test_construction_sets_attributes(pec: PonteEnCarreraSource) -> None:
    assert pec.name == "ponte_en_carrera"
    assert pec.url == DEPRECATED_URL
    assert pec.download_timeout_seconds == 5
    assert pec.headless is True


def test_is_marked_deprecated() -> None:
    """PEC must be flagged deprecated so registry/list_sources filters it out by default."""
    assert PonteEnCarreraSource.deprecated is True


def test_fetch_raises_source_fetch_error(pec: PonteEnCarreraSource) -> None:
    """fetch() must always raise because the upstream portal is decommissioned."""
    with pytest.raises(SourceFetchError) as exc_info:
        pec.fetch()
    msg = str(exc_info.value)
    assert "decommissioned" in msg.lower()
    assert "ponte en carrera" in msg.lower()


def test_load_reads_excel(pec: PonteEnCarreraSource, project_data_dir: Path) -> None:
    """load() still works on historical raw files committed to git."""
    pec_raw = project_data_dir / "ponte_en_carrera" / "raw.xlsx"
    if not pec_raw.exists():
        pytest.skip(f"Fixture not available: {pec_raw}")

    df = pec.load(pec_raw)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert len(df.columns) > 0


def test_source_is_registered() -> None:
    from src.sources import get_cls, list_deprecated, list_sources

    # Registered and discoverable when explicitly including deprecated sources.
    assert "ponte_en_carrera" in list_sources(include_deprecated=True)
    assert "ponte_en_carrera" in list_deprecated()
    assert get_cls("ponte_en_carrera") is PonteEnCarreraSource


def test_source_hidden_from_default_list() -> None:
    """Deprecated sources must not appear in the default list_sources() output."""
    from src.sources import list_sources

    # Default behaviour (no include_deprecated): PEC must be hidden so the CLI
    # default doesn't surface decommissioned sources to users.
    assert "ponte_en_carrera" not in list_sources()


def test_source_can_be_built_via_orchestrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """src.ingestion._build_source('ponte_en_carrera') wires AppConfig -> source."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snap"))

    from src.ingestion import _build_source

    source = _build_source("ponte_en_carrera")
    assert isinstance(source, PonteEnCarreraSource)
    assert source.data_dir == (tmp_path / "data").resolve()
    assert source.snapshot_dir == (tmp_path / "snap").resolve()
    assert source.url == DEPRECATED_URL
