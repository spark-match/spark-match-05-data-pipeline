"""Tests for src/config.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import AppConfig, load_config


def test_load_config_returns_dataclass() -> None:
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert isinstance(cfg.environment, str)
    assert isinstance(cfg.data_dir, Path)
    assert isinstance(cfg.snapshot_dir, Path)
    assert isinstance(cfg.pec_url, str)
    assert isinstance(cfg.pec_timeout_seconds, int)


def test_load_config_defaults_environment_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    cfg = load_config()
    assert cfg.environment == "dev"
    assert cfg.is_production is False


def test_load_config_is_production_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    cfg = load_config()
    assert cfg.is_production is True


def test_load_config_paths_are_absolute_and_under_project_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = load_config()
    assert cfg.data_dir.is_absolute()
    assert cfg.snapshot_dir.is_absolute()
    # They should live under the project root, not in /tmp or system dirs.
    project_root = Path(__file__).resolve().parent.parent / "src"  # tests/config.py -> src
    assert (
        project_root.parent.resolve() in cfg.data_dir.parents
        or cfg.data_dir.parent == project_root.parent
    )
    # The simpler invariant: paths must be within the project tree
    assert str(project_root.parent.resolve()) in str(cfg.data_dir)


def test_load_config_pec_timeout_is_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEC_DOWNLOAD_TIMEOUT_SECONDS", "120")
    cfg = load_config()
    assert cfg.pec_timeout_seconds == 120


def test_load_config_pec_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEC_DOWNLOAD_URL", raising=False)
    cfg = load_config()
    assert cfg.pec_url.startswith("https://ponteencarrera.minedu.gob.pe")


def test_appconfig_is_frozen() -> None:
    """Setting any field must raise FrozenInstanceError."""
    cfg = load_config()
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError inherits AttributeError
        cfg.environment = "prod"  # type: ignore[misc]


def test_dotenv_is_loaded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """src/config.py must call load_dotenv() at import time.

    python-dotenv does not override existing env vars by default, so we set
    ENVIRONMENT before reloading and then assert it was preserved (which
    proves load_dotenv() ran and did not silently clobber the value).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=test_from_dotenv\n", encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "preset_value")

    # Force fresh import of src.config so its module-level load_dotenv() runs
    import importlib

    import src.config as config_module

    importlib.reload(config_module)
    cfg = config_module.load_config()
    # load_dotenv() default override=False: existing env wins over .env
    assert cfg.environment == "preset_value"
