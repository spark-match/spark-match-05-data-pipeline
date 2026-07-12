import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait

# =====================================================
# CONFIG
# =====================================================

URL = "https://ponteencarrera.minedu.gob.pe/pec-portal-web/Home/DondeEstudiar"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOT_DIR = PROJECT_ROOT / "snapshots"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

RAW_FILE = DATA_DIR / "raw.xlsx"


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

logger = logging.getLogger(__name__)


# =====================================================
# SELENIUM
# =====================================================


def connect_to_page():

    logger.info("Opening Ponte en Carrera")

    chrome_options = webdriver.ChromeOptions()

    prefs = {
        "download.default_directory": str(DATA_DIR.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }

    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)

    driver.maximize_window()

    driver.get(URL)

    logger.info("Website loaded")

    return driver


def click_search_button(driver):

    logger.info("Searching search button")

    wait = WebDriverWait(driver, 20)

    search_button = wait.until(EC.element_to_be_clickable((By.ID, "btnBuscar")))

    search_button.click()

    logger.info("Search button clicked")

    time.sleep(5)


def click_excel_button(driver):

    logger.info("Searching Excel button")

    wait = WebDriverWait(driver, 20)

    excel_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href,'descargarDondeEstudioExcel')]"))
    )

    driver.execute_script("arguments[0].click();", excel_button)

    logger.info("Excel download started")


# =====================================================
# FILE MANAGEMENT
# =====================================================


def wait_for_download(timeout=60):

    logger.info("Waiting for download")

    start = time.time()

    while time.time() - start < timeout:
        xlsx_files = list(DATA_DIR.glob("*.xlsx"))

        xlsx_files = [file for file in xlsx_files if file.name != "raw.xlsx"]

        if xlsx_files:
            downloaded_file = max(xlsx_files, key=lambda x: x.stat().st_mtime)

            logger.info(f"Downloaded file detected: {downloaded_file.name}")

            return downloaded_file

        time.sleep(1)

    raise TimeoutError("Download timeout")


def save_snapshot(downloaded_file):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    snapshot_file = SNAPSHOT_DIR / f"raw_{timestamp}.xlsx"

    shutil.copy2(downloaded_file, snapshot_file)

    logger.info(f"Snapshot saved: {snapshot_file.name}")

    return snapshot_file


def update_raw_file(downloaded_file):

    if RAW_FILE.exists():
        RAW_FILE.unlink()

    shutil.move(downloaded_file, RAW_FILE)

    logger.info(f"Raw dataset updated: {RAW_FILE}")


# =====================================================
# DATA
# =====================================================


def load_excel(file_path):

    logger.info(f"Loading Excel: {file_path.name}")

    df = pd.read_excel(file_path)

    logger.info(f"Rows: {len(df)}")

    logger.info(f"Columns: {len(df.columns)}")

    return df


# =====================================================
# MAIN
# =====================================================


def run_ingestion():

    logger.info("========== INGESTION START ==========")

    driver = connect_to_page()

    try:
        click_search_button(driver)

        click_excel_button(driver)

        downloaded_file = wait_for_download()

        save_snapshot(downloaded_file)

        update_raw_file(downloaded_file)

        df = load_excel(RAW_FILE)

        logger.info("========== INGESTION FINISHED ==========")

        return df

    finally:
        driver.quit()


if __name__ == "__main__":
    dataframe = run_ingestion()

    print(dataframe.head())
