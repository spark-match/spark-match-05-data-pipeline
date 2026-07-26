"""Ponte en Carrera (MINEDU) data source.

DEPRECATED as of 2026-07-12: MINEDU is decommissioning the
ponteencarrera.minedu.gob.pe portal. The "¿Dónde estudio?" endpoint
returns HTTP 500 and the page surfaces a generic "el enlace está dañado"
error. A teammate confirmed the platform is being sunset.

Status:
- `fetch()` raises `SourceFetchError` — the upstream is unreachable.
- `load()` is kept working so the historical raw file
  (data/ponte_en_carrera/raw.xlsx, committed to git as a snapshot)
  can still be read by data_clean.py. This lets the pipeline run on
  historical data until a replacement source is wired in.
- The source stays registered (marked `deprecated = True`) so existing
  dvc.yaml stages, tests, and CLI invocations keep working without
  import errors.

Replacement investigation is tracked in src/sources/README.md.

Historical context (kept for reference):
    The portal was scraped with Selenium + headless Chrome. The download
    flow clicked a button with id `btnBuscar` (later replaced by an
    <a class="opcion__button"> element pointing to
    /pec-portal-web/inicio/donde-estudiar), then clicked an <a> with
    href containing 'descargarDondeEstudioExcel'. Both selectors and the
    backend route are now broken.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .base import DataSource
from .exceptions import SourceFetchError
from .registry import register

logger = logging.getLogger(__name__)


# Last known URL of the upstream portal, kept for diagnostics only.
DEPRECATED_URL = "https://ponteencarrera.minedu.gob.pe/pec-portal-web/inicio/donde-estudiar"


@register
class PonteEnCarreraSource(DataSource):
    """Historical scraper for the MINEDU 'Donde Estudiar' Excel export.

    Deprecated: see module docstring. `load()` still works on historical
    raw files; `fetch()` raises.
    """

    name = "ponte_en_carrera"
    deprecated = True

    def __init__(
        self,
        *,
        url: str = DEPRECATED_URL,
        data_dir: Path,
        snapshot_dir: Path,
        download_timeout_seconds: int = 60,
        headless: bool = True,
    ) -> None:
        super().__init__(data_dir=data_dir, snapshot_dir=snapshot_dir)
        self.url = url
        self.download_timeout_seconds = download_timeout_seconds
        self.headless = headless

    def fetch(self) -> Path:
        """Always raises: MINEDU is decommissioning the PEC portal.

        See the module docstring and src/sources/README.md for the
        investigation status and replacement candidates.
        """
        raise SourceFetchError(
            "Ponte en Carrera (MINEDU) is decommissioned as of 2026-07-12. "
            f"The portal at {self.url} returns HTTP 500 and the platform is "
            "being sunset per a teammate's report. Use the historical "
            "data/ponte_en_carrera/raw.xlsx snapshot already committed to git, "
            "or wire a replacement source (see src/sources/README.md)."
        )

    def load(self, path: Path) -> pd.DataFrame:
        """Read a persisted raw Excel into a DataFrame (no cleaning).

        Kept functional so data_clean.py can still process the historical
        raw.xlsx committed to git.
        """
        logger.info("Loading Excel: %s", path.name)
        df = pd.read_excel(path)
        logger.info("Rows: %d", len(df))
        logger.info("Columns: %d", len(df.columns))
        return df


__all__ = ["DEPRECATED_URL", "PonteEnCarreraSource"]
