"""Environment-driven configuration loaded from .env and process env vars.

The pipeline never reads env vars directly at module import time (which
would break tests and frozen apps). Instead, `load_config()` builds an
`AppConfig` snapshot on demand. The snapshot is frozen (immutable) so
downstream code can rely on the values.

Precedence (highest to lowest):
    1. Process env vars (set by GH Actions from GH Secrets, or by `direnv`)
    2. .env file (loaded by python-dotenv at first call)
    3. Built-in defaults (defined here)

To add a new env var:
    1. Add a field to `AppConfig`.
    2. Read it in `load_config()` with a sensible default.
    3. Document it in `.env.example`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env once at import time so `load_config()` is a pure read.
# Safe to call multiple times; python-dotenv is idempotent.
load_dotenv()


def _project_root() -> Path:
    """Resolve the project root (parent of the `src/` directory)."""
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration.

    Attributes:
        environment: One of 'dev' | 'prod'. Selects DVC remote, AWS role, etc.
        data_dir: Directory where raw per-source data files live
            (e.g., <data_dir>/ponte_en_carrera/raw.xlsx).
        snapshot_dir: Directory where timestamped copies of raw files are stored.
        pec_url: URL of the Ponte en Carrera 'Donde Estudiar' page.
        pec_timeout_seconds: How long to wait for the Chrome download to finish.
    """

    environment: str
    data_dir: Path
    snapshot_dir: Path
    pec_url: str
    pec_timeout_seconds: int

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


def load_config() -> AppConfig:
    """Build an AppConfig snapshot from env vars + .env.

    All paths are resolved to absolute paths under the project root.
    """
    root = _project_root()
    return AppConfig(
        environment=os.environ.get("ENVIRONMENT", "dev"),
        data_dir=(root / os.environ.get("DATA_DIR", "data")).resolve(),
        snapshot_dir=(root / os.environ.get("SNAPSHOT_DIR", "snapshots")).resolve(),
        pec_url=os.environ.get(
            "PEC_DOWNLOAD_URL",
            "https://ponteencarrera.minedu.gob.pe/pec-portal-web/Home/DondeEstudiar",
        ),
        pec_timeout_seconds=int(os.environ.get("PEC_DOWNLOAD_TIMEOUT_SECONDS", "60")),
    )
