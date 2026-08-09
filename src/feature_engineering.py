import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
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

FILTERED_FILE = PROJECT_ROOT / "data" / "filtered.csv"
FEATURES_FILE = PROJECT_ROOT / "data" / "features.csv"

FEATURE_CONFIG_FILE = PROJECT_ROOT / "data" / "feature_config.json"

SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"

FEATURES_SNAPSHOTS_DIR = SNAPSHOTS_DIR / "features"

CONFIG_SNAPSHOTS_DIR = SNAPSHOTS_DIR / "configs"

FEATURE_CONFIG = {
    "duration_institute_fallback": 4,
    "duration_university_fallback": 5,
    "duration_max_valid": 10,
    "admission_max_valid": 90,
    "income_fallback": 1100,
    "cost_fallback": 0,
    "admission_fallback": 0,
}

# -----------------------------------------------------------------------------
# Load Data
# -----------------------------------------------------------------------------


def load_filtered_dataset(file_path: Path) -> pd.DataFrame:
    """
    Load filtered dataset.
    """
    logger.info("Loading filtered dataset...")

    if not file_path.exists():
        raise FileNotFoundError(f"Filtered dataset not found: {file_path}")

    df = pd.read_csv(file_path)

    logger.info("Dataset loaded (%s rows, %s columns)", len(df), len(df.columns))

    return df


# -----------------------------------------------------------------------------
# Flags
# -----------------------------------------------------------------------------


def create_imputation_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create flags identifying records requiring imputation.
    """

    df["duration_imputed_flag"] = (
        (df["duration_years"] <= 0) | (df["duration_years"] > 10) | (df["duration_years"].isna())
    )

    df["monthly_income_imputed_flag"] = (df["monthly_income"] <= 0) | (df["monthly_income"].isna())

    df["annual_cost_imputed_flag"] = (df["annual_cost"] <= 0) | (df["annual_cost"].isna())

    df["admission_rate_imputed_flag"] = (
        (df["admission_rate"] <= 0) | (df["admission_rate"] > 90) | (df["admission_rate"].isna())
    )

    return df


# -----------------------------------------------------------------------------
# Fallback Rules
# -----------------------------------------------------------------------------


def duration_fallback(row):

    if row["institution_type"] == "Instituto":
        return FEATURE_CONFIG["duration_institute_fallback"]

    return FEATURE_CONFIG["duration_university_fallback"]


def income_fallback(row):

    return FEATURE_CONFIG["income_fallback"]


def cost_fallback(row):

    return FEATURE_CONFIG["cost_fallback"]


def admission_fallback(row):

    return FEATURE_CONFIG["admission_fallback"]


# -----------------------------------------------------------------------------
# Generic Imputation
# -----------------------------------------------------------------------------


def impute_variable(
    df: pd.DataFrame, source_column: str, target_column: str, fallback_function
) -> pd.DataFrame:
    """
    Imputation strategy:

    1. career_family + institution_type median
    2. career_family median
    3. fallback value
    """

    logger.info("Imputing %s...", source_column)

    df[target_column] = df[source_column]

    if source_column == "admission_rate":
        df[target_column] = df[target_column].clip(lower=0, upper=90)

    if source_column == "duration_years":
        df.loc[(df[target_column] <= 0) | (df[target_column] > 10), target_column] = np.nan

    else:
        df.loc[df[target_column] <= 0, target_column] = np.nan

    valid_data = df.loc[pd.notna(df[target_column])]

    median_cf_inst = valid_data.groupby(["career_family", "institution_type"])[
        target_column
    ].median()

    median_cf = valid_data.groupby("career_family")[target_column].median()

    def fill_value(row):

        if pd.notna(row[target_column]):
            return row[target_column]

        value = median_cf_inst.get((row["career_family"], row["institution_type"]), np.nan)

        if pd.notna(value):
            return value

        value = median_cf.get(row["career_family"], np.nan)

        if pd.notna(value):
            return value

        return fallback_function(row)

    df[target_column] = df.apply(fill_value, axis=1)

    return df


# -----------------------------------------------------------------------------
# Scoring Features
# -----------------------------------------------------------------------------


def minmax_scale(series: pd.Series) -> pd.Series:
    """
    Scale variable to [0, 1].
    """

    min_value = series.min()
    max_value = series.max()

    if min_value == max_value:
        return pd.Series(np.ones(len(series)), index=series.index)

    return (series - min_value) / (max_value - min_value)


def create_norm_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create normalized variables.
    """

    logger.info("Creating normalized features...")

    df["income_norm"] = minmax_scale(np.log1p(df["monthly_income_imputed"]))

    df["admission_norm"] = minmax_scale(df["admission_rate_imputed"])

    df["cost_norm"] = 1 - minmax_scale(np.log1p(df["annual_cost_imputed"]))

    df["duration_norm"] = 1 - minmax_scale(df["duration_years_imputed"])

    return df


# -----------------------------------------------------------------------------
# Save
# -----------------------------------------------------------------------------


def save_features_dataset(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save features dataset.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info("Features dataset saved to %s", output_path)


def save_feature_config() -> None:

    FEATURE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(FEATURE_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(FEATURE_CONFIG, file, indent=4, ensure_ascii=False)

    logger.info("Feature config saved to %s", FEATURE_CONFIG_FILE)


def save_feature_snapshot(df: pd.DataFrame) -> None:

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    FEATURES_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_file = FEATURES_SNAPSHOTS_DIR / f"features_{timestamp}.csv"

    df.to_csv(snapshot_file, index=False, encoding="utf-8-sig")

    logger.info("Feature snapshot saved to %s", snapshot_file)


def save_config_snapshot() -> None:

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    CONFIG_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_file = CONFIG_SNAPSHOTS_DIR / f"feature_config_{timestamp}.json"

    with open(snapshot_file, "w", encoding="utf-8") as file:
        json.dump(FEATURE_CONFIG, file, indent=4, ensure_ascii=False)

    logger.info("Feature config snapshot saved to %s", snapshot_file)


# -----------------------------------------------------------------------------
# Main Pipeline
# -----------------------------------------------------------------------------


def run_feature_engineering() -> None:

    logger.info("=" * 60)
    logger.info("FEATURE ENGINEERING STARTED")
    logger.info("=" * 60)

    df = load_filtered_dataset(FILTERED_FILE)

    df = create_imputation_flags(df)

    df = impute_variable(
        df=df,
        source_column="duration_years",
        target_column="duration_years_imputed",
        fallback_function=duration_fallback,
    )

    df = impute_variable(
        df=df,
        source_column="monthly_income",
        target_column="monthly_income_imputed",
        fallback_function=income_fallback,
    )

    df = impute_variable(
        df=df,
        source_column="annual_cost",
        target_column="annual_cost_imputed",
        fallback_function=cost_fallback,
    )

    df = impute_variable(
        df=df,
        source_column="admission_rate",
        target_column="admission_rate_imputed",
        fallback_function=admission_fallback,
    )

    df = create_norm_features(df)

    save_features_dataset(df, FEATURES_FILE)

    logger.info("=" * 60)
    logger.info("FEATURE ENGINEERING FINISHED")
    logger.info("=" * 60)

    save_features_dataset(df, FEATURES_FILE)

    save_feature_config()

    save_feature_snapshot(df)

    save_config_snapshot()


if __name__ == "__main__":
    run_feature_engineering()
