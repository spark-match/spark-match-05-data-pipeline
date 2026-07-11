"""Tests for the RIASEC tagging step.

The Bedrock model is faked (a stand-in for ``ChatBedrock``), so these run
without ``langchain-aws`` or AWS credentials.
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
# Fakes  (mimic langchain_aws.ChatBedrock: `.invoke(prompt)` -> obj with `.content`)
# -----------------------------------------------------------------------------


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChatBedrock:
    """Replays a queued script; a str is returned as content, an Exception raised."""

    def __init__(self, script=()):
        self.script = list(script)
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        step = self.script.pop(0) if self.script else self._default()

        if isinstance(step, Exception):
            raise step

        return FakeMessage(step)

    @staticmethod
    def _default():
        return json.dumps({"riasec_profile": "IRC", "confidence": 0.9})


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
    llm = FakeChatBedrock([ok("ISR")])

    result = request_riasec_code(llm, "Medicina", "Salud")

    assert result["riasec_profile"] == "ISR"


def test_request_riasec_code_strips_markdown_fences():
    fenced = "```json\n" + ok("AIR") + "\n```"
    llm = FakeChatBedrock([fenced])

    result = request_riasec_code(llm, "Arquitectura", "Diseno")

    assert result["riasec_profile"] == "AIR"


def test_request_riasec_code_retries_then_succeeds():
    llm = FakeChatBedrock([RuntimeError("boom"), ok("AIR")])

    result = request_riasec_code(llm, "Arquitectura", "Diseno")

    assert result["riasec_profile"] == "AIR"
    assert llm.calls == 2


def test_request_riasec_code_rejects_invalid_code_and_retries():
    # "XYZ" is not a valid Holland code -> should be retried, not accepted.
    llm = FakeChatBedrock([ok("XYZ"), ok("SIA")])

    result = request_riasec_code(llm, "Psicologia", "Sociales")

    assert result["riasec_profile"] == "SIA"
    assert llm.calls == 2


def test_request_riasec_code_gives_up_after_three_attempts():
    llm = FakeChatBedrock([RuntimeError("boom")] * 3)

    assert request_riasec_code(llm, "X", "Y") is None
    assert llm.calls == 3


def test_tag_careers_marks_failures_as_pending(features):
    careers = load_unique_careers(features)  # Enfermeria, Redes, Software

    # Enfermeria succeeds, Redes fails 3x, Software succeeds.
    llm = FakeChatBedrock(
        [ok("SIA")] + [RuntimeError("boom")] * 3 + [ok("IRC")]
    )

    tagged = tag_careers(careers, llm)

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
