"""End-to-end smoke test: POST each CSV in /test_data to a running backend and
report what came back.

Start the server first (from backend/):
    python -m app.main

Then, from backend/:
    python smoke_test.py            # all CSVs
    python smoke_test.py 02 09      # only files whose name contains these

Each abnormal result triggers a literature search plus two LLM calls, so a full
run over every file takes a few minutes.
"""

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TEST_DATA_DIR = Path(__file__).resolve().parent.parent / "test_data"

# Severity each file is built to produce, so the smoke test can actually check
# the outcome rather than just printing whatever came back.
EXPECTED = {
    "01_critical_low_hemoglobin.csv": "Critical",
    "02_critical_low_platelet.csv": "Critical",
    "03_critical_high_potassium.csv": "Critical",
    "04_warning_high_hba1c.csv": "Warning",
    "05_warning_low_ferritin.csv": "Warning",
    "06_warning_high_tsh.csv": "Warning",
    "07_normal_hemoglobin.csv": "Normal",
    "08_qualitative_normal_protein.csv": "Normal",
    "09_qualitative_abnormal_blood.csv": "Critical",
    # 10 resolves through the LLM reference_range_lookup fallback, so its final
    # severity depends on what the model returns — any classification is a pass.
    "10_unknown_test_no_range.csv": None,
}


def load_csv(path: Path) -> list[dict]:
    """Rows are passed through as-is; the backend schema maps the dataset's
    column names (Test_Name, Result, Min_Reference, ...) via field aliases."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def post_analyze(labs: list[dict]) -> dict:
    data = json.dumps({"labs": labs}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/analyze_labs",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def check_backend() -> None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5):
            return
    except (urllib.error.URLError, OSError):
        print(f"Cannot reach the backend at {BASE_URL}.")
        print("Start it first, from backend/:  python -m app.main")
        sys.exit(1)


def main() -> None:
    check_backend()

    csv_files = sorted(TEST_DATA_DIR.glob("*.csv"))
    if len(sys.argv) > 1:
        wanted = sys.argv[1:]
        csv_files = [p for p in csv_files if any(w in p.name for w in wanted)]

    if not csv_files:
        print(f"No matching CSVs in {TEST_DATA_DIR}")
        sys.exit(1)

    failures = []
    for csv_file in csv_files:
        labs = load_csv(csv_file)
        started = time.perf_counter()
        try:
            result = post_analyze(labs)
        except Exception as exc:
            print(f"FAIL  {csv_file.name}: request failed — {exc}")
            failures.append(csv_file.name)
            continue

        elapsed = time.perf_counter() - started
        flat = [r for bucket in ("critical", "warning", "unknown", "normal") for r in result["results"][bucket]]

        problems = []
        expected = EXPECTED.get(csv_file.name)
        got = flat[0]["status"] if flat else None
        if expected and got != expected:
            problems.append(f"expected {expected}, got {got}")
        if not flat and not result["errors"]:
            problems.append("no results and no errors")
        # Every returned result should carry the explainability payload.
        for r in flat:
            if not r.get("explanation"):
                problems.append(f"{r['test_name']}: empty explanation")
            if not r.get("next_steps"):
                problems.append(f"{r['test_name']}: empty next_steps")

        status = "FAIL" if problems else "ok  "
        print(f"{status}  {csv_file.name:38} {str(got):9} {elapsed:5.1f}s  {result['summary']}")
        for problem in problems:
            print(f"        - {problem}")
        if problems:
            failures.append(csv_file.name)

    print()
    if failures:
        print(f"{len(failures)} of {len(csv_files)} file(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print(f"All {len(csv_files)} file(s) passed.")


if __name__ == "__main__":
    main()
