"""Tests for the RIASEC tagging step.

The Bedrock client is faked, so these run without AWS credentials.
"""

from pathlib import Path
import json
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.riasec_tagging import (  # noqa: E402
    RIASEC_CODES,
    apply_family_fallback,
    load_unique_careers,
    merge_tags_into_features,
    request_riasec_code,
    tag_careers,
    validate_sample,
)

# -----------------------------------------------------------------------------
# Fakes
# -----------------------------------------------------------------------------


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


class FakeMessages:
    """Replays a queued script of responses; a str is returned, an Exception raised."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        step = self.script.pop(0) if self.script else self.script_default()

        if isinstance(step, Exception):
            raise step

        return FakeResponse(step)

    def script_default(self):
        return json.dumps({"riasec_profile": "IRC", "confidence": 0.9})


class FakeClient:
    def __init__(self, script=()):
        self.messages = FakeMessages(script)


def ok(code="IRC"):
    return json.dumps({"riasec_profile": code, "confidence": 0.95})


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def features(tmp_path):
    """Two careers in 'Tec', one in 'Salud'; 'Redes' spans two rows."""
    df = pd.DataFrame({
        "career": ["Software", "Redes", "Redes", "Enfermeria"],
        "career_family": ["Tec", "Tec", "Tec", "Salud"],
        "institution": ["A", "B", "C", "D"],
    })

    path = tmp_path / "features.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")

    return path


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_riasec_codes_are_120_distinct_letter_triples():
    assert len(RIASEC_CODES) == 120
    assert all(len(set(code)) == 3 for code in RIASEC_CODES)


def test_load_unique_careers_collapses_duplicate_rows(features):
    careers = load_unique_careers(features)

    assert len(careers) == 3
    assert set(careers["career"]) == {"Software", "Redes", "Enfermeria"}


def test_load_unique_careers_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_unique_careers(tmp_path / "nope.csv")


def test_request_riasec_code_parses_a_valid_response():
    client = FakeClient([ok("ISR")])

    result = request_riasec_code(client, "Medicina", "Salud")

    assert result["riasec_profile"] == "ISR"


def test_request_riasec_code_retries_then_succeeds():
    client = FakeClient([RuntimeError("boom"), ok("AIR")])

    result = request_riasec_code(client, "Arquitectura", "Diseno")

    assert result["riasec_profile"] == "AIR"
    assert client.messages.calls == 2


def test_request_riasec_code_gives_up_after_three_attempts():
    client = FakeClient([RuntimeError("boom")] * 3)

    assert request_riasec_code(client, "X", "Y") is None
    assert client.messages.calls == 3


def test_tag_careers_marks_failures_as_pending(features):
    careers = load_unique_careers(features)  # Enfermeria, Redes, Software

    # Enfermeria succeeds, Redes fails 3x, Software succeeds.
    client = FakeClient(
        [ok("SIA")] + [RuntimeError("boom")] * 3 + [ok("IRC")]
    )

    tagged = tag_careers(careers, client)

    by_career = tagged.set_index("career")
    assert by_career.loc["Enfermeria", "riasec_source"] == "llm_tagged"
    assert by_career.loc["Redes", "riasec_source"] == "pending"
    assert pd.isna(by_career.loc["Redes", "riasec_profile"])


def test_apply_family_fallback_fills_pending_from_its_family():
    tagged = pd.DataFrame({
        "career": ["Software", "Redes", "Enfermeria"],
        "career_family": ["Tec", "Tec", "Salud"],
        "riasec_profile": ["IRC", None, "SIA"],
        "riasec_source": ["llm_tagged", "pending", "llm_tagged"],
    })

    filled = apply_family_fallback(tagged)

    redes = filled.set_index("career").loc["Redes"]
    assert redes["riasec_profile"] == "IRC"
    assert redes["riasec_source"] == "family_fallback"
    assert filled["riasec_profile"].notna().all()


def test_apply_family_fallback_raises_when_a_whole_family_is_pending():
    tagged = pd.DataFrame({
        "career": ["Software", "Enfermeria"],
        "career_family": ["Tec", "Salud"],
        "riasec_profile": ["IRC", None],
        "riasec_source": ["llm_tagged", "pending"],
    })

    with pytest.raises(ValueError, match="no RIASEC code"):
        apply_family_fallback(tagged)


def test_merge_propagates_one_code_to_every_institution_row(features):
    features_df = pd.read_csv(features)

    tagged = pd.DataFrame({
        "career": ["Software", "Redes", "Enfermeria"],
        "riasec_profile": ["IRC", "RIC", "SIA"],
        "riasec_source": ["llm_tagged"] * 3,
    })

    merged = merge_tags_into_features(features_df, tagged)

    assert len(merged) == len(features_df)
    assert merged["riasec_profile"].notna().all()
    # Both 'Redes' rows carry the same code.
    assert set(merged.loc[merged["career"] == "Redes", "riasec_profile"]) == {"RIC"}


def test_validate_sample_is_deterministic_and_only_llm_tagged(tmp_path):
    tagged = pd.DataFrame({
        "career": [f"C{i}" for i in range(10)],
        "career_family": ["Tec"] * 10,
        "riasec_profile": ["IRC"] * 10,
        "riasec_source": ["llm_tagged"] * 8 + ["family_fallback"] * 2,
    })

    out = validate_sample(tagged, tmp_path / "sample.csv", sample_size=5)
    first = pd.read_csv(out)

    out = validate_sample(tagged, tmp_path / "sample2.csv", sample_size=5)
    second = pd.read_csv(out)

    assert list(first["career"]) == list(second["career"])
    assert set(first["riasec_source"]) == {"llm_tagged"}
    assert {"revisado_por", "correcto", "notas"} <= set(first.columns)
