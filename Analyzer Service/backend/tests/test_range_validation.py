"""Tests for sanity-checking LLM-supplied reference ranges.

An unvalidated range is the worst failure mode in the system: a range returned
in the wrong units yields a confident, plausible-looking, completely wrong
severity. These cover the guards in `_validate_looked_up_range`.
"""

import pytest

from app.mcp_server import _validate_looked_up_range

GOOD = {"low": 0.87, "high": 1.70, "critical_low": 0.4, "critical_high": 4.0, "unit": "ng/dL"}


class TestAccepted:
    def test_well_formed_range_passes_through(self):
        out = _validate_looked_up_range(GOOD, value=1.14)
        assert out["found"] is True
        assert (out["low"], out["high"]) == (0.87, 1.70)
        assert (out["critical_low"], out["critical_high"]) == (0.4, 4.0)
        assert out["unit"] == "ng/dL"
        assert out["warnings"] == []

    def test_numeric_strings_are_coerced(self):
        out = _validate_looked_up_range(
            {"low": "0.87", "high": "1.70", "critical_low": "0.4", "critical_high": "4.0"}, value=1.14
        )
        assert out["found"] is True
        assert out["low"] == 0.87

    def test_missing_critical_bounds_default_to_the_normal_band(self):
        out = _validate_looked_up_range({"low": 10, "high": 20}, value=15)
        assert out["found"] is True
        assert out["critical_low"] == 10
        assert out["critical_high"] == 20

    def test_genuine_clinical_extreme_is_still_accepted(self):
        """Ferritin 2000 against a 15-150 range is >13x high but real —
        the scale guard must not reject legitimate outliers."""
        out = _validate_looked_up_range(
            {"low": 15, "high": 150, "critical_low": 5, "critical_high": 1000}, value=2000
        )
        assert out["found"] is True

    def test_no_value_supplied_skips_the_scale_check(self):
        assert _validate_looked_up_range(GOOD, value=None)["found"] is True


class TestRejected:
    @pytest.mark.parametrize(
        "data",
        [
            {},                                    # nothing at all
            {"low": 10},                           # high missing
            {"low": "abc", "high": 20},            # non-numeric
            {"low": None, "high": 20},
        ],
    )
    def test_missing_or_unparseable_bounds(self, data):
        out = _validate_looked_up_range(data, value=15)
        assert out["found"] is False
        assert "reason" in out

    @pytest.mark.parametrize("low,high", [(20, 10), (10, 10)])
    def test_low_must_be_below_high(self, low, high):
        out = _validate_looked_up_range({"low": low, "high": high}, value=15)
        assert out["found"] is False
        assert "not below" in out["reason"]

    def test_non_finite_bounds(self):
        out = _validate_looked_up_range({"low": float("nan"), "high": 20}, value=15)
        assert out["found"] is False

    def test_unit_mismatch_far_above_is_rejected(self):
        """A range quoted in g/L for a value reported in mg/dL."""
        out = _validate_looked_up_range({"low": 0.012, "high": 0.015}, value=12.9)
        assert out["found"] is False
        assert "implausibly far above" in out["reason"]

    def test_unit_mismatch_far_below_is_rejected(self):
        out = _validate_looked_up_range({"low": 12000, "high": 15000}, value=12.9)
        assert out["found"] is False
        assert "implausibly far below" in out["reason"]


class TestClamping:
    def test_critical_low_inside_the_band_is_clamped(self):
        """critical_low must sit at or below the normal low, otherwise values
        inside the normal band would classify as Critical."""
        out = _validate_looked_up_range(
            {"low": 10, "high": 20, "critical_low": 15, "critical_high": 25}, value=12
        )
        assert out["found"] is True
        assert out["critical_low"] == 10
        assert any("critical_low" in w for w in out["warnings"])

    def test_critical_high_inside_the_band_is_clamped(self):
        out = _validate_looked_up_range(
            {"low": 10, "high": 20, "critical_low": 5, "critical_high": 15}, value=12
        )
        assert out["found"] is True
        assert out["critical_high"] == 20
        assert any("critical_high" in w for w in out["warnings"])

    def test_clamped_band_no_longer_misclassifies_a_normal_value(self):
        """Regression guard: with critical_low=15 unclamped, a value of 12 —
        inside the normal 10-20 band — would have been flagged Critical."""
        out = _validate_looked_up_range(
            {"low": 10, "high": 20, "critical_low": 15, "critical_high": 25}, value=12
        )
        value = 12
        assert not (value < out["critical_low"] or value > out["critical_high"])
        assert not (value < out["low"] or value > out["high"])
