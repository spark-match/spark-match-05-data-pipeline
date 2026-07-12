"""Ponte en Carrera (MINEDU) data source.

Pulls the "Donde Estudiar" Excel from https://ponteencarrera.minedu.gob.pe
using Selenium + headless Chrome, persists it under
`data/ponte_en_carrera/raw.xlsx`, and loads it as a raw DataFrame.

Browser is launched with auto-managed chromedriver (webdriver-manager),
so no manual binary download is required.

Future maintenance notes:
- The portal occasionally restructures; selectors `btnBuscar` and the
  XPath containing 'descargarDondeEstudioExcel' may break. When that
  happens, update `_click_search_button` / `_click_excel_button` and
  add a regression test against a recorded HTML snapshot.
- MINEDU does not publish a public API; this is the only documented
  public export path.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812 (selenium convention)
from selenium.webdriver.support.ui import WebDriverWait

from .base import DataSource
from .exceptions import SourceFetchError
from .registry import register

logger = logging.getLogger(__name__)


@register
class PonteEnCarreraSource(DataSource):
    """Scraper for the MINEDU 'Donde Estudiar' Excel export."""

    name = "ponte_en_carrera"

    def __init__(
        self,
        *,
        url: str,
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
        """Drive Selenium to download the Excel; return path to downloaded file."""
        driver = self._connect_to_page()
        try:
            self._click_search_button(driver)
            self._click_excel_button(driver)
            downloaded = self._wait_for_download()
            return downloaded
        finally:
            driver.quit()

    def load(self, path: Path) -> pd.DataFrame:
        """Load the persisted Excel into a raw DataFrame (no cleaning)."""
        logger.info("Loading Excel: %s", path.name)
        df = pd.read_excel(path)
        logger.info("Rows: %d", len(df))
        logger.info("Columns: %d", len(df.columns))
        return df

    def _connect_to_page(self) -> webdriver.Chrome:
        logger.info("Opening Ponte en Carrera: %s", self.url)
        chrome_options = webdriver.ChromeOptions()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        download_dir = (self.data_dir / self.name).resolve()
        download_dir.mkdir(parents=True, exist_ok=True)
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
        driver.get(self.url)
        logger.info("Website loaded")
        return driver

    def _click_search_button(self, driver: webdriver.Chrome) -> None:
        logger.info("Locating search button")
        wait = WebDriverWait(driver, 20)
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "btnBuscar")))
        search_button.click()
        logger.info("Search button clicked")
        time.sleep(5)

    def _click_excel_button(self, driver: webdriver.Chrome) -> None:
        logger.info("Locating Excel download button")
        wait = WebDriverWait(driver, 20)
        excel_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href,'descargarDondeEstudioExcel')]")
            )
        )
        driver.execute_script("arguments[0].click();", excel_button)
        logger.info("Excel download started")

    def _wait_for_download(self) -> Path:
        """Poll the download dir until a fresh .xlsx file appears."""
        download_dir = (self.data_dir / self.name).resolve()
        expected = download_dir / "raw.xlsx"
        logger.info("Waiting for download (timeout=%ds)", self.download_timeout_seconds)
        start = time.time()
        while time.time() - start < self.download_timeout_seconds:
            xlsx_files = [
                p
                for p in download_dir.glob("*.xlsx")
                if p.name != expected.name and not p.name.startswith(".")
            ]
            if xlsx_files:
                downloaded_file = max(xlsx_files, key=lambda p: p.stat().st_mtime)
                logger.info("Downloaded file detected: %s", downloaded_file.name)
                return downloaded_file
            time.sleep(1)
        raise SourceFetchError(
            f"Download timeout after {self.download_timeout_seconds}s in {download_dir}"
        )


__all__ = ["PonteEnCarreraSource"]
