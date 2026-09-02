"""Quick end-to-end sanity check: POST each CSV in /test_data to a running
backend and print the summary. Start the server first:
    uvicorn app.main:app --reload --port 8000
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TEST_DATA_DIR = Path(__file__).resolve().parent.parent / "test_data"


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [{"test_name": row["test_name"], "value": row["value"], "unit": row["unit"]} for row in reader]


def post_analyze(labs: list[dict]) -> dict:
    data = json.dumps({"labs": labs}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/analyze_labs",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> None:
    csv_files = sorted(TEST_DATA_DIR.glob("*.csv"))
    if not csv_files:
        print("No test CSVs found in test_data/")
        sys.exit(1)

    for csv_file in csv_files:
        print(f"--- {csv_file.name} ---")
        labs = load_csv(csv_file)
        result = post_analyze(labs)
        print(json.dumps(result["summary"], indent=2))
        if result.get("errors"):
            print("Errors:", result["errors"])
        print()

    print("Smoke test complete.")


if __name__ == "__main__":
    main()
