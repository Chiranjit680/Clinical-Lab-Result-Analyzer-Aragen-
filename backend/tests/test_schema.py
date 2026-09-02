"""Tests for LabRecord — the intake schema.

Validation decides which rows reach the agent at all, so these cover the
"invalid lab names / missing data / out-of-range values" error handling the
brief asks for. Rows that fail here land in the response's `errors[]` rather
than failing the whole batch.
"""

import pytest
from pydantic import ValidationError

from app.schemas import LabRecord


def record(**overrides):
    row = {"Test_Name": "Hemoglobin", "Result": "12.9", "Unit": "g/dL"}
    row.update(overrides)
    return row


class TestValidRows:
    def test_kaggle_columns_map_via_aliases(self):
        lab = LabRecord.model_validate(
            {
                "Date": "2025-08-12",
                "Test_Name": "Hemoglobin",
                "Result": "12.9",
                "Unit": "g/dL",
                "Reference_Range": "12-15",
                "Status": "Normal",
                "Comment": "Anemi yok",
                "Min_Reference": "12",
                "Max_Reference": "15",
                "Unit_Description": "Gram/Desilitre",
                "Recommended_Followup": "Rutin kontrol",
            }
        )
        assert lab.test_name == "Hemoglobin"
        assert lab.result == 12.9
        assert lab.min_reference == 12.0
        assert lab.max_reference == 15.0
        assert lab.recommended_followup == "Rutin kontrol"
        assert not lab.is_qualitative

    def test_only_name_and_result_are_required(self):
        lab = LabRecord.model_validate({"Test_Name": "Glucose", "Result": "92"})
        assert lab.unit is None
        assert lab.min_reference is None

    def test_extra_columns_are_ignored(self):
        lab = LabRecord.model_validate(record(Something_Unexpected="x"))
        assert lab.test_name == "Hemoglobin"


class TestResultCoercion:
    @pytest.mark.parametrize("raw,expected", [("12.9", 12.9), (12.9, 12.9), ("267", 267.0), ("1,02", 1.02)])
    def test_numeric_values_become_floats(self, raw, expected):
        """Comma decimal separators appear in the source data."""
        assert LabRecord.model_validate(record(Result=raw)).result == expected

    @pytest.mark.parametrize("raw", ["Negatif", "Normal", "1+", "3+", "Pozitif"])
    def test_qualitative_values_are_kept_as_strings(self, raw):
        lab = LabRecord.model_validate(record(Result=raw))
        assert lab.result == raw
        assert lab.is_qualitative

    def test_blank_reference_bounds_become_none(self):
        """Qualitative rows leave Min/Max_Reference empty."""
        lab = LabRecord.model_validate(record(Result="Negatif", Min_Reference="", Max_Reference=""))
        assert lab.min_reference is None
        assert lab.max_reference is None


class TestRejectedRows:
    @pytest.mark.parametrize("name", ["", "   ", None])
    def test_missing_test_name_is_rejected(self, name):
        with pytest.raises(ValidationError):
            LabRecord.model_validate(record(Test_Name=name))

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_missing_result_is_rejected(self, value):
        with pytest.raises(ValidationError):
            LabRecord.model_validate(record(Result=value))

    def test_missing_result_key_entirely_is_rejected(self):
        with pytest.raises(ValidationError):
            LabRecord.model_validate({"Test_Name": "Hemoglobin"})

    def test_non_numeric_result_with_numeric_range_is_rejected(self):
        """A corrupt value on a test that clearly expects a number must be an
        error, not silently treated as a qualitative result."""
        with pytest.raises(ValidationError):
            LabRecord.model_validate(record(Result="ABC", Min_Reference="15", Max_Reference="150"))

    def test_qualitative_result_without_range_still_accepted(self):
        """The guard above must not break genuine urine-strip rows."""
        lab = LabRecord.model_validate(
            record(Test_Name="Protein (Strip)", Result="Negatif", Min_Reference="", Max_Reference="")
        )
        assert lab.is_qualitative

    def test_error_identifies_the_offending_field(self):
        """The response surfaces this field name to the user."""
        with pytest.raises(ValidationError) as exc:
            LabRecord.model_validate(record(Test_Name=""))
        assert any("Test_Name" in str(e["loc"]) for e in exc.value.errors())
