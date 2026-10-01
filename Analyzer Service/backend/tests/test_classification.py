"""Tests for the classification layer — the deterministic core of the agent.

These call the MCP tool functions directly rather than over the MCP transport:
the transport is exercised by smoke_test.py, while these cover the decision
logic, which is where the subtle bugs live. No LLM or network calls, so the
whole suite runs in well under a second.
"""

import pytest

from app.mcp_server import classify_lab_result, classify_qualitative_result
from app.reference_ranges import get_reference_range


class TestNumericClassification:
    """Severity from a value plus the row's own reference range."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (12.9, "Normal"),   # mid-range
            (12.0, "Normal"),   # exactly the low bound — inclusive
            (15.0, "Normal"),   # exactly the high bound — inclusive
            (11.2, "Warning"),  # just below normal
            (16.0, "Warning"),  # just above normal
            (6.4, "Critical"),  # below the curated critical_low (7.0)
            (21.0, "Critical"),  # above the curated critical_high (20.0)
        ],
    )
    def test_hemoglobin_boundaries(self, value, expected):
        result = classify_lab_result("Hemoglobin", value, "g/dL", 12.0, 15.0)
        assert result["status"] == expected

    def test_wide_range_uses_curated_critical_bounds(self):
        """Regression: deriving critical bounds from the range span put
        platelets' critical_low at 0 (150 - 0.5*300), so 18 — a genuine
        emergency — was only flagged Warning."""
        assert classify_lab_result("Trombosit", 18, "10^3/uL", 150, 450)["status"] == "Critical"
        assert classify_lab_result("Trombosit", 120, "10^3/uL", 150, 450)["status"] == "Warning"
        assert classify_lab_result("Trombosit", 267, "10^3/uL", 150, 450)["status"] == "Normal"

    def test_mismatched_scale_falls_back_to_derivation(self):
        """Free T4 (0.87-1.70 ng/dL) must not borrow total T4's critical bounds
        (4.5-11.2 ug/dL) — the overlap guard should reject the curated entry."""
        result = classify_lab_result("Serbest T4", 1.14, "ng/dL", 0.87, 1.70)
        assert result["status"] == "Normal"

    def test_deviation_is_reported_for_abnormal(self):
        """The 'why' behind a flag is required by the explainability constraint."""
        low = classify_lab_result("Hemoglobin", 8.2, "g/dL", 12.0, 15.0)
        assert "below" in low["deviation"]
        assert "3.80" in low["deviation"]

        high = classify_lab_result("Hemoglobin", 17.0, "g/dL", 12.0, 15.0)
        assert "above" in high["deviation"]

        assert classify_lab_result("Hemoglobin", 13.0, "g/dL", 12.0, 15.0)["deviation"] is None

    def test_unknown_test_without_range(self):
        result = classify_lab_result("Prokalsitonin", 4.8, "ng/mL", None, None)
        assert result["status"] == "Unknown"
        assert result["reference_range"] is None

    def test_falls_back_to_curated_dict_when_row_has_no_range(self):
        result = classify_lab_result("TSH", 9.8, "mIU/L", None, None)
        assert result["status"] == "Warning"
        assert result["reference_range"] is not None


class TestQualitativeClassification:
    """Urine-strip results have no numeric bounds."""

    @pytest.mark.parametrize(
        "value,reference,expected",
        [
            ("Negatif", "Negatif", "Normal"),
            ("Normal", "Normal", "Normal"),
            ("1+", "Negatif", "Warning"),
            ("2+", "Negatif", "Warning"),
            ("3+", "Negatif", "Critical"),
            ("4+", "Negatif", "Critical"),
            ("Pozitif", "Negatif", "Warning"),
        ],
    )
    def test_grades(self, value, reference, expected):
        result = classify_qualitative_result("Protein (Strip)", value, reference, "mg/dL")
        assert result["status"] == expected
        assert result["qualitative"] is True

    def test_case_and_whitespace_insensitive(self):
        assert classify_qualitative_result("X", "  NEGATIF ", "Negatif", "")["status"] == "Normal"

    def test_unrecognised_value_is_unknown_not_a_crash(self):
        assert classify_qualitative_result("X", "???", "Negatif", "")["status"] == "Unknown"


class TestReferenceRangeLookup:
    """The source dataset is Turkish; names must normalise to the curated dict."""

    @pytest.mark.parametrize(
        "name",
        ["Trombosit", "trombosit", "  Trombosit  ", "Platelet Count", "PLT"],
    )
    def test_aliases_resolve_to_same_entry(self, name):
        assert get_reference_range(name) == get_reference_range("platelet count")

    @pytest.mark.parametrize(
        "turkish,english",
        [
            ("Lökosit", "wbc"),
            ("Eritrosit", "rbc"),
            ("Hematokrit", "hematocrit"),
            ("Potasyum", "potassium"),
            ("İnsülin", "insulin"),
            ("Glikozile Hemoglobin (HbA1c)", "hba1c"),
        ],
    )
    def test_turkish_diacritics_are_folded(self, turkish, english):
        """'Lökosit'/'İnsülin' must match despite ö, ü, İ."""
        assert get_reference_range(turkish) == get_reference_range(english)

    def test_unknown_test_returns_none(self):
        assert get_reference_range("Definitely Not A Real Test") is None
