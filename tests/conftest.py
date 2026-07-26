"""Shared pytest fixtures for the data-pipeline test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Project root (parent of tests/)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def project_data_dir(project_root: Path) -> Path:
    """Repo's `data/` directory, where legacy raw.xlsx lives for now.

    Used by tests that need a real file as fixture (e.g., PEC load()).
    Will be removed in Fase 2 when DVC takes over data tracking.
    """
    return project_root / "data"
