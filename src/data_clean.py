import logging
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FILE = PROJECT_ROOT / "data" / "raw.xlsx"
FILTERED_FILE = PROJECT_ROOT / "data" / "filtered.csv"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

COLUMN_MAPPING = {
    "N°": "id",
    "Familia Carrera": "career_family",
    "Carrera": "career",
    "Institución": "institution",
    "Ubicación": "location",
    "Tipo institución": "institution_type",
    "Tipo gestión": "management_type",
    "Duración": "duration_years",
    "Costo anual": "annual_cost",
    "Ingresantes/Postulantes (%)": "admission_rate",
    "Ingreso mensual": "monthly_income",
    "Becas educativas": "scholarships",
    "Ingresantes": "admitted",
    "Postulantes": "applicants",
    "Matriculados": "enrolled",
}

NUMERIC_COLUMNS = [
    "duration_years",
    "annual_cost",
    "admission_rate",
    "monthly_income",
    "admitted",
    "applicants",
    "enrolled",
]

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------


def load_raw_data(file_path: Path) -> pd.DataFrame:
    """
    Load raw Ponte en Carrera dataset.

    Parameters
    ----------
    file_path : Path
        Path to raw Excel file.

    Returns
    -------
    pd.DataFrame
    """
    logger.info("Loading raw dataset...")

    if not file_path.exists():
        raise FileNotFoundError(f"Raw dataset not found: {file_path}")

    df = pd.read_excel(file_path, header=6)

    logger.info("Dataset loaded successfully (%s rows, %s columns)", len(df), len(df.columns))

    return df


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename columns to standardized snake_case names.
    """
    logger.info("Standardizing column names...")

    return df.rename(columns=COLUMN_MAPPING)


def remove_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows without career or institution.
    """
    initial_rows = len(df)

    df = df.dropna(subset=["career", "institution"])

    removed_rows = initial_rows - len(df)

    logger.info("Removed %s empty rows", removed_rows)

    return df


def convert_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert numeric columns to numeric dtype.
    """
    logger.info("Converting numeric columns...")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def save_filtered_dataset(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save filtered dataset as CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info("Filtered dataset saved to %s", output_path)


def run_filtering() -> None:
    """
    Main filtering pipeline.
    """
    logger.info("=" * 60)
    logger.info("FILTERING PIPELINE STARTED")
    logger.info("=" * 60)

    df = load_raw_data(RAW_FILE)

    logger.info("Initial shape: %s", df.shape)

    df = standardize_columns(df)

    df = remove_empty_rows(df)

    df = convert_data_types(df)

    logger.info("Final shape: %s", df.shape)

    save_filtered_dataset(df, FILTERED_FILE)

    logger.info("=" * 60)
    logger.info("FILTERING PIPELINE FINISHED")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_filtering()
