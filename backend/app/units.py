"""Unit compatibility between a reported result and the reference range it is
compared against.

This only matters when a result is classified against the **curated dictionary**
(`reference_ranges.py`). When the source row carries its own Min/Max_Reference,
the value and its range are in the same unit by construction and no mismatch is
possible.

Most real-world "mismatches" are the same unit written differently
("10^3/uL" vs "x10^3/uL") or genuinely interchangeable ("mmol/L" vs "mEq/L" for a
monovalent ion). Those must not raise false alarms. What must be caught is a true
scale difference — g/L against g/dL is a factor of 10, and silently comparing them
produces a confident, wrong severity.
"""

import re
from typing import Optional, Tuple

# --- normalisation ---------------------------------------------------------

_UNIT_ALIASES = {
    # cell counts — all of these denote the same quantity
    "10^3/ul": "10^3/ul",
    "x10^3/ul": "10^3/ul",
    "10*3/ul": "10^3/ul",
    "10e3/ul": "10^3/ul",
    "k/ul": "10^3/ul",
    "10^9/l": "10^3/ul",  # 10^9/L == 10^3/uL
    "10^6/ul": "10^6/ul",
    "x10^6/ul": "10^6/ul",
    "10*6/ul": "10^6/ul",
    "m/ul": "10^6/ul",
    "10^12/l": "10^6/ul",  # 10^12/L == 10^6/uL
    # mass concentration equivalences
    "ug/l": "ng/ml",  # 1 ug/L == 1 ng/mL
    "mcg/l": "ng/ml",
    "ng/ml": "ng/ml",
    "pg/ml": "pg/ml",
    "ng/l": "pg/ml",  # 1 ng/L == 1 pg/mL
    # activity
    "miu/l": "miu/l",
    "uiu/ml": "miu/l",  # 1 uIU/mL == 1 mIU/L
    "iu/l": "iu/l",
    "u/l": "u/l",
    # misc
    "%": "%",
    "ratio": "ratio",
    "-": "",
    "": "",
}

# Monovalent ions: for these, mmol/L and mEq/L are numerically identical.
# (Deliberately not generalised — for divalent ions such as calcium the factor
# is 2, so treating them as interchangeable would be wrong.)
_MONOVALENT = {"sodium", "potassium", "chloride", "bicarbonate"}

# Escape hatch for pairs the generic dimensional parser cannot derive.
# Prefer adding to the parser over adding entries here.
_SCALE: dict[Tuple[str, str], float] = {}

# Analyte-specific molar conversions, which need the molecular weight and so
# cannot be derived from the unit strings alone.
# test key -> factor to convert mg/dL into mmol/L.
_MG_DL_TO_MMOL_L = {
    "glucose": 0.0555,
    "total cholesterol": 0.02586,
    "ldl cholesterol": 0.02586,
    "hdl cholesterol": 0.02586,
    "triglycerides": 0.01129,
    "calcium": 0.2495,
    "magnesium": 0.4114,
    # Deliberately omitted: analytes conventionally reported in umol/L rather
    # than mmol/L (bilirubin, creatinine). Adding them here with their umol
    # factors would be wrong by a factor of 1000.
}


# --- generic dimensional parsing ------------------------------------------
#
# Rather than enumerating every convertible pair, a unit is parsed into
# (kind, numerator scale, denominator volume in litres). Two units are
# convertible when their kinds match, and the factor follows arithmetically.
# This makes "/uL" -> "/mL", "cells/uL" -> "cells/mL" and "Leu/uL" -> "Leu/L"
# all work without anticipating the exact strings.

_VOLUMES_IN_LITRES = {"l": 1.0, "dl": 0.1, "cl": 0.01, "ml": 1e-3, "ul": 1e-6, "nl": 1e-9, "pl": 1e-12}

_MASS_IN_GRAMS = {"kg": 1e3, "g": 1.0, "mg": 1e-3, "ug": 1e-6, "mcg": 1e-6, "ng": 1e-9, "pg": 1e-12}

_MOLES = {"mol": 1.0, "mmol": 1e-3, "umol": 1e-6, "nmol": 1e-9, "pmol": 1e-12}

_ACTIVITY = {"u": 1.0, "iu": 1.0, "miu": 1e-3, "uiu": 1e-6, "mu": 1e-3}

# Numerator tokens that denote a bare count of things.
_COUNT_WORDS = {"", "cells", "cell", "leu", "ery", "rbc", "wbc", "count"}


def _parse_numerator(token: str) -> Optional[Tuple[str, float]]:
    """Return (kind, scale) for the part before the slash."""
    token = token.strip()

    # Scientific-notation multipliers used for cell counts: 10^3, 10*6, 10e9.
    match = re.fullmatch(r"x?10[\^*e](\d+)", token)
    if match:
        return "count", 10.0 ** int(match.group(1))
    if token in _COUNT_WORDS:
        return "count", 1.0
    if token in _MASS_IN_GRAMS:
        return "mass", _MASS_IN_GRAMS[token]
    if token in _MOLES:
        return "mole", _MOLES[token]
    if token in _ACTIVITY:
        return "activity", _ACTIVITY[token]
    return None


def _parse_unit(unit: str) -> Optional[Tuple[str, float, float]]:
    """Parse 'mg/dL' or '10^3/uL' into (kind, numerator scale, litres)."""
    if "/" not in unit:
        return None  # dimensionless ('%', 'ratio') — nothing to convert
    numerator, _, denominator = unit.partition("/")
    volume = _VOLUMES_IN_LITRES.get(denominator.strip())
    if volume is None:
        return None
    parsed = _parse_numerator(numerator)
    if parsed is None:
        return None
    kind, scale = parsed
    return kind, scale, volume


def _dimensional_factor(observed: str, expected: str) -> Optional[float]:
    """Multiplier converting a value in `observed` into `expected`, or None."""
    a, b = _parse_unit(observed), _parse_unit(expected)
    if a is None or b is None:
        return None
    kind_a, num_a, den_a = a
    kind_b, num_b, den_b = b
    if kind_a != kind_b:
        return None  # e.g. mass vs moles — needs the molar mass, handled separately
    factor = (num_a / num_b) * (den_b / den_a)
    # Chained division of powers of ten leaves artefacts (1000.0000000000001),
    # which would surface in the user-facing conversion note.
    return float(f"{factor:.12g}")


def normalize_unit(unit: Optional[str]) -> str:
    """Lower-case, strip spacing/punctuation noise, and fold known aliases."""
    if not unit:
        return ""
    text = unit.strip().lower()
    text = text.replace("μ", "u").replace("µ", "u")
    text = re.sub(r"\s+", "", text)
    text = text.replace("×", "x").replace("**", "^")
    return _UNIT_ALIASES.get(text, text)


def check_compatibility(test_key: str, observed: Optional[str], expected: Optional[str]):
    """Compare a reported unit against a reference range's unit.

    Returns (status, factor, note) where status is one of:
      "match"        — same unit (possibly after alias folding); factor 1.0
      "convertible"  — different but convertible; multiply the value by `factor`
      "unknown"      — one side has no unit; assume compatible, factor 1.0
      "mismatch"     — incompatible; the caller should not trust a comparison
    """
    obs = normalize_unit(observed)
    exp = normalize_unit(expected)

    if not obs or not exp:
        return "unknown", 1.0, "no unit given on one side; assumed compatible"

    if obs == exp:
        return "match", 1.0, ""

    # mmol/L == mEq/L, but only for monovalent ions.
    if {obs, exp} == {"mmol/l", "meq/l"}:
        if test_key in _MONOVALENT:
            return "match", 1.0, f"mmol/L and mEq/L are equivalent for {test_key}"
        return (
            "mismatch",
            None,
            f"mmol/L and mEq/L are not interchangeable for {test_key} (valency differs)",
        )

    # Generic dimensional conversion: same kind, differing prefix and/or
    # volume denominator (g/L -> g/dL, /uL -> /mL, 10^3/uL -> 10^9/L, ...).
    factor = _dimensional_factor(obs, exp)
    if factor is not None:
        if factor == 1.0:
            return "match", 1.0, f"'{observed}' and '{expected}' are the same quantity"
        return "convertible", factor, f"converted {observed} to {expected} (x{factor:g})"

    # Explicit overrides for pairs the generic parser cannot derive.
    factor = _SCALE.get((obs, exp))
    if factor is not None:
        return "convertible", factor, f"converted {observed} to {expected} (x{factor})"

    # Molar conversion, analyte-specific.
    if (obs, exp) == ("mg/dl", "mmol/l") and test_key in _MG_DL_TO_MMOL_L:
        return "convertible", _MG_DL_TO_MMOL_L[test_key], f"converted mg/dL to mmol/L for {test_key}"
    if (obs, exp) == ("mmol/l", "mg/dl") and test_key in _MG_DL_TO_MMOL_L:
        return "convertible", 1 / _MG_DL_TO_MMOL_L[test_key], f"converted mmol/L to mg/dL for {test_key}"

    return "mismatch", None, f"'{observed}' is not comparable with the reference unit '{expected}'"
