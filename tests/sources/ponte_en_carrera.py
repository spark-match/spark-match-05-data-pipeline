"""Tests for src/sources/ponte_en_carrera.py.

The Selenium flow is NOT tested here (it requires a live browser and the
upstream portal, which are not available in CI). Only the pure parts are
exercised:
- construction
- load() against a fixture file
- wiring via _build_source in ingestion.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.sources.ponte_en_carrera import PonteEnCarreraSource

URL = "https://ponteencarrera.minedu.gob.pe/pec-portal-web/Home/DondeEstudiar"


@pytest.fixture
def pec(tmp_path: Path) -> PonteEnCarreraSource:
    return PonteEnCarreraSource(
        url=URL,
        data_dir=tmp_path / "data",
        snapshot_dir=tmp_path / "snap",
        download_timeout_seconds=5,
        headless=True,
    )


def test_construction_sets_attributes(pec: PonteEnCarreraSource) -> None:
    assert pec.name == "ponte_en_carrera"
    assert pec.url == URL
    assert pec.download_timeout_seconds == 5
    assert pec.headless is True


def test_load_reads_excel(pec: PonteEnCarreraSource, project_data_dir: Path) -> None:
    """Smoke test: PEC.load() should read a real Excel file successfully.

    project_data_dir is a session-scoped fixture that points to the
    repo's `data/` directory, where the per-source raw file is checked
    in for backward compat. This test will be removed in Fase 3 when
    DVC takes over data tracking.
    """
    pec_raw = project_data_dir / "ponte_en_carrera" / "raw.xlsx"
    if not pec_raw.exists():
        pytest.skip(f"Fixture not available: {pec_raw}")

    df = pec.load(pec_raw)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert len(df.columns) > 0


def test_source_is_registered() -> None:
    from src.sources import get_cls, list_sources

    assert "ponte_en_carrera" in list_sources()
    assert get_cls("ponte_en_carrera") is PonteEnCarreraSource


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
    assert source.url == URL
