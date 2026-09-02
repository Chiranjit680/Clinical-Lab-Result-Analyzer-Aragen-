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
}


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def get_reference_range(test_name: str) -> Optional[Range]:
    key = _normalize(test_name)
    key = ALIASES.get(key, key)
    return REFERENCE_RANGES.get(key)


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
