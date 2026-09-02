"""Tests for unit compatibility checking.

Two failure modes matter equally here: raising a false alarm on units that are
actually the same (which would drop good rows), and silently comparing across
a real scale difference (which produces a confident wrong severity).
"""

import pytest

from app.units import check_compatibility, normalize_unit


class TestNormalisation:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("10^3/uL", "10^3/ul"),
            ("x10^3/uL", "10^3/ul"),
            ("10^9/L", "10^3/ul"),   # 10^9/L == 10^3/uL
            ("K/uL", "10^3/ul"),
            ("10^6/uL", "10^6/ul"),
            ("10^12/L", "10^6/ul"),
            ("ug/L", "ng/ml"),        # 1 ug/L == 1 ng/mL
            ("ng/L", "pg/ml"),
            ("uIU/mL", "miu/l"),
            ("  G/DL  ", "g/dl"),
        ],
    )
    def test_aliases_fold_to_a_canonical_form(self, raw, expected):
        assert normalize_unit(raw) == expected

    def test_micro_sign_variants(self):
        assert normalize_unit("µg/L") == normalize_unit("ug/L")

    @pytest.mark.parametrize("raw", [None, "", "  ", "-"])
    def test_empty_units(self, raw):
        assert normalize_unit(raw) == ""


class TestNoFalseAlarms:
    """These pairs appear in the real dataset and must NOT be flagged."""

    def test_platelet_count_string_variant(self):
        status, factor, _ = check_compatibility("platelet count", "10^3/uL", "x10^3/uL")
        assert status == "match"
        assert factor == 1.0

    def test_potassium_mmol_vs_meq(self):
        """Equivalent for a monovalent ion."""
        status, factor, _ = check_compatibility("potassium", "mmol/L", "mEq/L")
        assert status == "match"
        assert factor == 1.0

    @pytest.mark.parametrize("test_key", ["sodium", "chloride", "bicarbonate"])
    def test_other_monovalent_ions(self, test_key):
        assert check_compatibility(test_key, "mmol/L", "mEq/L")[0] == "match"

    @pytest.mark.parametrize("source_name", ["Potasyum", "potasyum", "K+", "Potassium"])
    def test_turkish_and_alias_names_resolve_before_the_valency_check(self, source_name):
        """Regression: the monovalent check keys off the English dictionary
        name, so the source name must be alias-resolved first. Passing the
        folded Turkish 'potasyum' straight through wrongly reported a
        mismatch and dropped a valid row."""
        from app.reference_ranges import canonical_key

        status, factor, _ = check_compatibility(canonical_key(source_name), "mmol/L", "mEq/L")
        assert status == "match"
        assert factor == 1.0

    def test_missing_unit_is_assumed_compatible(self):
        status, factor, _ = check_compatibility("hemoglobin", "", "g/dL")
        assert status == "unknown"
        assert factor == 1.0


class TestRealMismatches:
    def test_divalent_ion_is_not_interchangeable(self):
        """Calcium is divalent — mmol/L and mEq/L differ by a factor of 2, so
        treating them as equal would be wrong."""
        status, factor, note = check_compatibility("calcium", "mmol/L", "mEq/L")
        assert status == "mismatch"
        assert factor is None
        assert "valency" in note

    def test_incomparable_units(self):
        status, _, _ = check_compatibility("hemoglobin", "%", "g/dL")
        assert status == "mismatch"


class TestConversions:
    @pytest.mark.parametrize(
        "observed,expected,factor",
        [
            ("g/L", "g/dL", 0.1),
            ("g/dL", "g/L", 10.0),
            ("mg/L", "mg/dL", 0.1),
            ("ng/dL", "ng/mL", 0.01),
        ],
    )
    def test_scale_conversions(self, observed, expected, factor):
        status, got, _ = check_compatibility("hemoglobin", observed, expected)
        assert status == "convertible"
        assert got == pytest.approx(factor)

    def test_scale_conversion_produces_the_right_value(self):
        """129 g/L is 12.9 g/dL — a normal haemoglobin, not a wild outlier."""
        _, factor, _ = check_compatibility("hemoglobin", "g/L", "g/dL")
        assert 129 * factor == pytest.approx(12.9)

    def test_molar_conversion_is_analyte_specific(self):
        status, factor, _ = check_compatibility("glucose", "mg/dL", "mmol/L")
        assert status == "convertible"
        # 92 mg/dL is about 5.1 mmol/L
        assert 92 * factor == pytest.approx(5.1, abs=0.1)

    def test_molar_conversion_unavailable_for_unknown_analyte(self):
        assert check_compatibility("some unknown test", "mg/dL", "mmol/L")[0] == "mismatch"


class TestVolumeDenominators:
    """Counts per volume: the denominator alone differs, so the conversion is
    derived generically rather than from an enumerated pair list."""

    @pytest.mark.parametrize(
        "observed,expected,factor",
        [
            ("/uL", "/mL", 1000.0),
            ("/mL", "/uL", 0.001),
            ("/uL", "/L", 1e6),
            ("/L", "/uL", 1e-6),
            ("/uL", "/dL", 1e5),
        ],
    )
    def test_bare_counts(self, observed, expected, factor):
        status, got, _ = check_compatibility("wbc", observed, expected)
        assert status == "convertible"
        assert got == pytest.approx(factor, rel=1e-9)

    @pytest.mark.parametrize("word", ["cells", "Leu", "ery", "RBC"])
    def test_count_words_are_handled_generically(self, word):
        """Any count noun works — not just strings anticipated in a table."""
        status, factor, _ = check_compatibility("wbc", f"{word}/uL", f"{word}/mL")
        assert status == "convertible"
        assert factor == pytest.approx(1000.0)

    def test_conversion_produces_the_right_count(self):
        """6370 cells/uL is 6.37 million cells/mL."""
        _, factor, _ = check_compatibility("wbc", "cells/uL", "cells/mL")
        assert 6370 * factor == pytest.approx(6_370_000)

    def test_scientific_multiplier_with_differing_denominator(self):
        """10^3/uL and 10^9/L are the same quantity — factor exactly 1."""
        status, factor, _ = check_compatibility("wbc", "10^3/uL", "10^9/L")
        assert factor == pytest.approx(1.0)
        assert status == "match"

    def test_factor_has_no_floating_point_artefacts(self):
        """Chained division of powers of ten yielded 1000.0000000000001,
        which would show up in the user-facing conversion note."""
        _, factor, _ = check_compatibility("wbc", "/uL", "/mL")
        assert factor == 1000.0

    def test_count_and_mass_are_not_interchangeable(self):
        assert check_compatibility("wbc", "g/dL", "cells/uL")[0] == "mismatch"

    def test_dimensionless_units_are_not_converted(self):
        assert check_compatibility("hematocrit", "%", "g/dL")[0] == "mismatch"
