"""Assign a RIASEC (Holland) profile to every unique career in the catalog.

The economic dataset from Ponte en Carrera has no vocational dimension, so the
affinity term of the scoring formula cannot be computed. This module fills that
gap: it tags each of the ~554 unique careers once (not the 6,208 career x
institution rows) and leaves the join to the caller.

Uses ``langchain_aws.ChatBedrock`` (same Bedrock client as the agent in
``08-deep-agent``) so the team shares one auth path and one model-id format.
"""

from itertools import permutations
from pathlib import Path
import json
import logging
import os

import pandas as pd

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FEATURES_FILE = PROJECT_ROOT / "data" / "features.csv"
TAGS_FILE = PROJECT_ROOT / "data" / "riasec_tags.csv"
VALIDATION_SAMPLE_FILE = PROJECT_ROOT / "data" / "riasec_validation_sample.csv"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# ChatBedrock uses the raw Bedrock model / inference-profile id (no `anthropic.`
# prefix). Same format the agent uses in `08-deep-agent`.
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514"
)

MAX_RETRIES = 3

VALIDATION_SAMPLE_SIZE = 300
VALIDATION_SEED = 42

# Every valid Holland code: 3 distinct letters, order matters (120 in total).
RIASEC_CODES = frozenset("".join(code) for code in permutations("RIASEC", 3))

SYSTEM_PROMPT = (
    "Eres un orientador vocacional experto en el modelo RIASEC de Holland. "
    "Asignas a cada carrera su código Holland de 3 letras, ordenado de la "
    "dimensión más dominante a la menos dominante.\n"
    "Dimensiones: R=Realista (manual, mecánico), I=Investigativo (analítico, "
    "científico), A=Artístico (creativo, expresivo), S=Social (ayudar, "
    "enseñar), E=Emprendedor (liderar, persuadir), C=Convencional (organizar, "
    "detalle)."
)

# Seed examples reused from the agent catalog (repo 08-deep-agent).
SEED_EXAMPLES = [
    ("Ciencias de la Computación", "Tecnología", "IRC"),
    ("Medicina", "Salud", "ISR"),
    ("Arquitectura", "Diseño / Ingeniería", "AIR"),
    ("Psicología", "Ciencias Sociales", "SIA"),
    ("Administración de Empresas", "Negocios", "ECS"),
    ("Ciencia de Datos", "Tecnología / Ciencia", "ICR"),
    ("Diseño Gráfico", "Artes / Comunicación", "AER"),
    ("Ingeniería Civil", "Ingeniería", "RIC"),
    ("Marketing Digital", "Negocios / Comunicación", "EAC"),
    ("Educación / Pedagogía", "Educación", "SAE"),
]

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------


def build_llm(model_id: str | None = None):
    """
    Build the Bedrock chat model (same client as the agent: ``ChatBedrock``).

    Imported lazily so the module stays usable (and testable with a fake LLM)
    without ``langchain-aws`` or AWS credentials installed.

    Returns
    -------
    ChatBedrock
    """
    from langchain_aws import ChatBedrock

    return ChatBedrock(
        model_id=model_id or BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
    )


def load_unique_careers(features_file: Path) -> pd.DataFrame:
    """
    Extract one row per unique career from the features dataset.

    A handful of careers appear under more than one family; the most frequent
    family wins, so the fallback in `apply_family_fallback` stays deterministic.

    Parameters
    ----------
    features_file : Path
        Path to `features.csv`.

    Returns
    -------
    pd.DataFrame
        Columns `career`, `career_family`.
    """
    logger.info("Loading careers from %s", features_file)

    if not features_file.exists():
        raise FileNotFoundError(
            f"Features dataset not found: {features_file}"
        )

    df = pd.read_csv(features_file)

    careers = (
        df.groupby("career")["career_family"]
        .agg(lambda families: families.mode().iat[0])
        .reset_index()
    )

    logger.info(
        "Found %s unique careers (from %s rows)",
        len(careers),
        len(df)
    )

    return careers


def build_prompt(career: str, career_family: str) -> str:
    """
    Build a single few-shot prompt string (same style as the agent's judge).
    """
    examples = "\n".join(
        f"- Carrera: {name} | Familia: {family} -> {code}"
        for name, family, code in SEED_EXAMPLES
    )

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Ejemplos:\n{examples}\n\n"
        f"Asigna el código RIASEC de esta carrera:\n"
        f"- Carrera: {career} | Familia: {career_family}\n\n"
        'Responde SOLO con este JSON, sin texto adicional:\n'
        '{"riasec_profile": "XXX", "confidence": 0.0}\n'
        "donde XXX son 3 letras distintas de RIASEC y confidence va de 0 a 1."
    )


def _extract_json(text: str) -> dict:
    """
    Parse the model's reply into a dict, stripping ```` ``` ```` fences if present.

    Mirrors the parsing in the agent's `SparkMatchJudge`.
    """
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    return json.loads(cleaned)


def request_riasec_code(llm, career: str, career_family: str) -> dict | None:
    """
    Ask the model for one career's Holland code.

    Validates the returned code against `RIASEC_CODES`, so an invalid or
    malformed answer is retried instead of poisoning the dataset. Returns None
    once the retries are exhausted.
    """
    prompt = build_prompt(career, career_family)

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = llm.invoke(prompt)

            text = response.content if hasattr(response, "content") else str(response)

            data = _extract_json(text)

            code = str(data["riasec_profile"]).strip().upper()

            if code not in RIASEC_CODES:
                raise ValueError(f"invalid RIASEC code: {code!r}")

            return {"riasec_profile": code, "confidence": data.get("confidence")}

        except Exception as error:
            logger.warning(
                "Attempt %s/%s failed for '%s': %s",
                attempt,
                MAX_RETRIES,
                career,
                error
            )

    logger.error("Giving up on '%s' after %s attempts", career, MAX_RETRIES)

    return None


def tag_careers(careers_df: pd.DataFrame, llm) -> pd.DataFrame:
    """
    Tag every career, marking the ones the model could not resolve as pending.

    Returns
    -------
    pd.DataFrame
        `careers_df` plus `riasec_profile` and `riasec_source`.
    """
    logger.info("Tagging %s careers via Bedrock...", len(careers_df))

    profiles = []
    sources = []

    for row in careers_df.itertuples(index=False):

        result = request_riasec_code(llm, row.career, row.career_family)

        if result is None:
            profiles.append(None)
            sources.append("pending")
        else:
            profiles.append(result["riasec_profile"])
            sources.append("llm_tagged")

    tagged = careers_df.copy()
    tagged["riasec_profile"] = profiles
    tagged["riasec_source"] = sources

    pending = (tagged["riasec_source"] == "pending").sum()

    logger.info(
        "Tagged %s careers (%s pending)",
        len(tagged) - pending,
        pending
    )

    return tagged


def apply_family_fallback(tagged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill pending careers with the most common code of their family.

    Raises
    ------
    ValueError
        If any career is still untagged (a whole family failed).
    """
    logger.info("Applying family fallback...")

    resolved = tagged_df[tagged_df["riasec_source"] == "llm_tagged"]

    family_mode = (
        resolved.groupby("career_family")["riasec_profile"]
        .agg(lambda codes: codes.mode().iat[0] if not codes.mode().empty else None)
    )

    df = tagged_df.copy()
    pending = df["riasec_source"] == "pending"

    df.loc[pending, "riasec_profile"] = (
        df.loc[pending, "career_family"].map(family_mode)
    )

    filled = pending & df["riasec_profile"].notna()
    df.loc[filled, "riasec_source"] = "family_fallback"

    logger.info("Filled %s careers from their family", filled.sum())

    missing = df["riasec_profile"].isna()

    if missing.any():
        raise ValueError(
            f"{missing.sum()} careers have no RIASEC code: "
            f"{df.loc[missing, 'career'].tolist()[:5]}"
        )

    return df


def validate_sample(
    tagged_df: pd.DataFrame,
    output_path: Path,
    sample_size: int = VALIDATION_SAMPLE_SIZE,
    seed: int = VALIDATION_SEED
) -> Path:
    """
    Export a deterministic sample of the LLM-tagged careers for human review.
    """
    llm_tagged = tagged_df[tagged_df["riasec_source"] == "llm_tagged"]

    sample = llm_tagged.sample(
        n=min(sample_size, len(llm_tagged)),
        random_state=seed
    )

    sample = sample.assign(revisado_por="", correcto="", notas="")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sample.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(
        "Validation sample (%s careers) saved to %s",
        len(sample),
        output_path
    )

    return output_path


def merge_tags_into_features(
    features_df: pd.DataFrame,
    tagged_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Propagate the per-career codes to all career x institution rows.
    """
    merged = features_df.merge(
        tagged_df[["career", "riasec_profile", "riasec_source"]],
        on="career",
        how="left"
    )

    logger.info(
        "Merged RIASEC into %s feature rows",
        len(merged)
    )

    return merged


def run_tagging() -> None:
    """
    Main tagging pipeline.
    """
    logger.info("=" * 60)
    logger.info("RIASEC TAGGING STARTED")
    logger.info("=" * 60)

    careers = load_unique_careers(FEATURES_FILE)

    tagged = tag_careers(careers, build_llm())

    tagged = apply_family_fallback(tagged)

    validate_sample(tagged, VALIDATION_SAMPLE_FILE)

    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    tagged.to_csv(TAGS_FILE, index=False, encoding="utf-8-sig")

    logger.info("Tags saved to %s", TAGS_FILE)

    logger.info("=" * 60)
    logger.info("RIASEC TAGGING FINISHED")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_tagging()
