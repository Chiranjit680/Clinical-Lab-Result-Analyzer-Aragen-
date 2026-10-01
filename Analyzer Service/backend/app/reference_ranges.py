"""Curated clinical reference ranges used by the `classify_lab_result` MCP tool.

Until the Kaggle "Laboratory Test Results" dataset is wired in, this module ships a
hand-curated dictionary of common adult reference ranges. `load_from_kaggle_csv`
lets that dataset extend/override these values without touching agent logic.
"""

from typing import Optional, TypedDict


class Range(TypedDict):
    low: float
    high: float
    critical_low: float
    critical_high: float
    unit: str


REFERENCE_RANGES: dict[str, Range] = {
    "hemoglobin": {"low": 12.0, "high": 17.5, "critical_low": 7.0, "critical_high": 20.0, "unit": "g/dL"},
    "wbc": {"low": 4.5, "high": 11.0, "critical_low": 2.0, "critical_high": 30.0, "unit": "x10^3/uL"},
    "platelet count": {"low": 150, "high": 450, "critical_low": 20, "critical_high": 1000, "unit": "x10^3/uL"},
    "rbc": {"low": 4.2, "high": 5.9, "critical_low": 2.0, "critical_high": 7.0, "unit": "x10^6/uL"},
    "hematocrit": {"low": 36, "high": 50, "critical_low": 20, "critical_high": 60, "unit": "%"},
    "glucose": {"low": 70, "high": 100, "critical_low": 40, "critical_high": 400, "unit": "mg/dL"},
    "sodium": {"low": 135, "high": 145, "critical_low": 120, "critical_high": 160, "unit": "mEq/L"},
    "potassium": {"low": 3.5, "high": 5.1, "critical_low": 2.5, "critical_high": 6.5, "unit": "mEq/L"},
    "chloride": {"low": 98, "high": 107, "critical_low": 80, "critical_high": 120, "unit": "mEq/L"},
    "bicarbonate": {"low": 22, "high": 29, "critical_low": 10, "critical_high": 40, "unit": "mEq/L"},
    "bun": {"low": 7, "high": 20, "critical_low": 1, "critical_high": 100, "unit": "mg/dL"},
    "creatinine": {"low": 0.6, "high": 1.3, "critical_low": 0.1, "critical_high": 10.0, "unit": "mg/dL"},
    "calcium": {"low": 8.5, "high": 10.2, "critical_low": 6.0, "critical_high": 13.0, "unit": "mg/dL"},
    "magnesium": {"low": 1.7, "high": 2.2, "critical_low": 1.0, "critical_high": 4.0, "unit": "mg/dL"},
    "total cholesterol": {"low": 125, "high": 200, "critical_low": 50, "critical_high": 300, "unit": "mg/dL"},
    "ldl cholesterol": {"low": 0, "high": 100, "critical_low": 0, "critical_high": 190, "unit": "mg/dL"},
    "hdl cholesterol": {"low": 40, "high": 60, "critical_low": 20, "critical_high": 100, "unit": "mg/dL"},
    "triglycerides": {"low": 0, "high": 150, "critical_low": 0, "critical_high": 500, "unit": "mg/dL"},
    "alt": {"low": 7, "high": 56, "critical_low": 0, "critical_high": 1000, "unit": "U/L"},
    "ast": {"low": 10, "high": 40, "critical_low": 0, "critical_high": 1000, "unit": "U/L"},
    "total bilirubin": {"low": 0.1, "high": 1.2, "critical_low": 0, "critical_high": 15.0, "unit": "mg/dL"},
    "albumin": {"low": 3.5, "high": 5.0, "critical_low": 1.5, "critical_high": 6.0, "unit": "g/dL"},
    "tsh": {"low": 0.4, "high": 4.0, "critical_low": 0.01, "critical_high": 100.0, "unit": "mIU/L"},
    "t4": {"low": 4.5, "high": 11.2, "critical_low": 1.0, "critical_high": 20.0, "unit": "ug/dL"},
    "inr": {"low": 0.8, "high": 1.1, "critical_low": 0.5, "critical_high": 5.0, "unit": "ratio"},
    "hba1c": {"low": 4.0, "high": 5.6, "critical_low": 2.0, "critical_high": 14.0, "unit": "%"},
    # Tests present in the source (Kaggle) dataset
    "ferritin": {"low": 15, "high": 150, "critical_low": 5, "critical_high": 1000, "unit": "ug/L"},
    "free t4": {"low": 0.87, "high": 1.70, "critical_low": 0.4, "critical_high": 4.0, "unit": "ng/dL"},
    "free t3": {"low": 2.3, "high": 4.2, "critical_low": 1.0, "critical_high": 10.0, "unit": "pg/mL"},
    "insulin": {"low": 2.6, "high": 24.9, "critical_low": 1.0, "critical_high": 100.0, "unit": "mU/L"},
    "total ige": {"low": 0.1, "high": 100, "critical_low": 0, "critical_high": 2000, "unit": "KU/L"},
    "vitamin b12": {"low": 200, "high": 900, "critical_low": 100, "critical_high": 2000, "unit": "pg/mL"},
    "neutrophil %": {"low": 50, "high": 70, "critical_low": 20, "critical_high": 90, "unit": "%"},
    "lymphocyte %": {"low": 18, "high": 42, "critical_low": 5, "critical_high": 80, "unit": "%"},
    "monocyte %": {"low": 2, "high": 11, "critical_low": 0, "critical_high": 30, "unit": "%"},
    "rdw": {"low": 11.5, "high": 14.5, "critical_low": 8, "critical_high": 25, "unit": "%"},
}

ALIASES: dict[str, str] = {
    "hgb": "hemoglobin",
    "hb": "hemoglobin",
    "white blood cell count": "wbc",
    "white blood cells": "wbc",
    "white blood cell": "wbc",
    "platelets": "platelet count",
    "plt": "platelet count",
    "red blood cell count": "rbc",
    "red blood cells": "rbc",
    "hct": "hematocrit",
    "blood glucose": "glucose",
    "fasting glucose": "glucose",
    "blood sugar": "glucose",
    "na": "sodium",
    "na+": "sodium",
    "k": "potassium",
    "k+": "potassium",
    "cl": "chloride",
    "cl-": "chloride",
    "co2": "bicarbonate",
    "blood urea nitrogen": "bun",
    "cr": "creatinine",
    "ca": "calcium",
    "cholesterol": "total cholesterol",
    "ldl": "ldl cholesterol",
    "hdl": "hdl cholesterol",
    "triglyceride": "triglycerides",
    "alanine aminotransferase": "alt",
    "aspartate aminotransferase": "ast",
    "bilirubin": "total bilirubin",
    "thyroid stimulating hormone": "tsh",
    "thyroxine": "t4",
    "international normalized ratio": "inr",
    "hemoglobin a1c": "hba1c",
    "a1c": "hba1c",
    # Turkish names from the source dataset (diacritics folded by _normalize)
    "trombosit": "platelet count",
    "lokosit": "wbc",
    "eritrosit": "rbc",
    "hematokrit": "hematocrit",
    "potasyum": "potassium",
    "sodyum": "sodium",
    "klor": "chloride",
    "kalsiyum": "calcium",
    "kreatinin": "creatinine",
    "glukoz": "glucose",
    "glikozile hemoglobin (hba1c)": "hba1c",
    "serbest t4": "free t4",
    "serbest t3": "free t3",
    "insulin": "insulin",
    "notrofil%": "neutrophil %",
    "notrofil %": "neutrophil %",
    "lenfosit%": "lymphocyte %",
    "lenfosit %": "lymphocyte %",
    "monosit%": "monocyte %",
    "monosit %": "monocyte %",
}


def _normalize(name: str) -> str:
    """Lowercase, collapse whitespace, and strip diacritics.

    The source dataset uses Turkish test names ("Lökosit", "İnsülin"), so
    diacritics are folded to ASCII to let one alias table match both forms.
    """
    import unicodedata

    text = name.strip().replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


def canonical_key(test_name: str) -> str:
    """Normalised, alias-resolved dictionary key for a test name.

    'Potasyum' -> 'potassium', 'Lökosit' -> 'wbc'. Callers that need to reason
    about the *test* (not just look up its range) should use this — normalising
    alone leaves the Turkish name in place.
    """
    key = _normalize(test_name)
    return ALIASES.get(key, key)


def get_reference_range(test_name: str) -> Optional[Range]:
    return REFERENCE_RANGES.get(canonical_key(test_name))


def load_from_kaggle_csv(csv_path: str) -> int:
    """Extend REFERENCE_RANGES from the Kaggle 'Laboratory Test Results' CSV.

    Expects columns roughly: test_name, reference_low, reference_high, unit
    (optionally critical_low / critical_high). Column names may need adjusting
    once the actual dataset file is available. No-op if the path doesn't exist.
    Returns the number of tests loaded/updated.
    """
    import csv
    import os

    if not os.path.exists(csv_path):
        return 0

    loaded = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _normalize(row.get("test_name", ""))
            if not name:
                continue
            try:
                low = float(row["reference_low"])
                high = float(row["reference_high"])
            except (KeyError, ValueError):
                continue
            REFERENCE_RANGES[name] = {
                "low": low,
                "high": high,
                "critical_low": float(row.get("critical_low") or low * 0.5),
                "critical_high": float(row.get("critical_high") or high * 1.5),
                "unit": row.get("unit", ""),
            }
            loaded += 1
    return loaded
