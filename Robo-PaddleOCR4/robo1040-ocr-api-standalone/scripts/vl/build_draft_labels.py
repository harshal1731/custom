"""Draft ground-truth labels from all sample PDFs via live API.

Output is a starting label set for fine-tuning. Fields with low confidence
are set to null so they don't poison training — review those manually.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (scripts/vl -> ../..)
BASE = ROOT.parent / "01 - ROBO - Sample PDF Document - 10 Set"
OUT_DIR = ROOT / "training"
OUT_JSON = OUT_DIR / "ground_truth_draft.json"
OUT_REVIEW = OUT_DIR / "needs_review.json"

FOLDERS = [
    ("W-2", "01 - W2 Form - Sample Document (10 Set)", "W-2"),
    ("1099-INT", "02 - 1099 INT - Sample Document (10 Set)", "1099-INT"),
    ("1099-DIV", "03 - 1099 DIV - Sample Document (10 Set)", "1099-DIV"),
    (
        "Brokerage",
        "04 - Consolidated Brokerage Statement - Sample Document (10 Set)",
        "Consolidated Brokerage Statement",
    ),
    ("5498-SA", "05 - 5498 SA - Sample Document (10 Set)", "5498-SA"),
]

MIN_CONF = 0.75


def api_key() -> str:
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("API_KEY", "robo1040")


def extract(pdf: Path, key: str) -> dict:
    cmd = [
        "curl.exe",
        "-s",
        "-m",
        "120",
        "-H",
        f"X-API-Key: {key}",
        "-F",
        f"file=@{pdf};type=application/pdf",
        "http://127.0.0.1:8010/api/v1/extract",
    ]
    raw = subprocess.check_output(cmd)
    return json.loads(raw.decode("utf-8", errors="replace"))


def main() -> int:
    if not BASE.exists():
        print(f"Sample folder not found: {BASE}", file=sys.stderr)
        return 1

    key = api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ground: dict = {}
    review: list = []

    for _label, folder, expected_type in FOLDERS:
        dir_path = BASE / folder
        for pdf in sorted(dir_path.glob("*.pdf")):
            print(f"Labeling {folder}/{pdf.name} ...", flush=True)
            try:
                data = extract(pdf, key)
            except Exception as exc:
                print(f"  FAIL: {exc}")
                ground[pdf.name] = {
                    "form_type": expected_type,
                    "fields": {},
                    "status": "extract_failed",
                    "error": str(exc),
                }
                continue

            form_type = data.get("form_type") or expected_type
            fields = data.get("fields") or {}
            conf = data.get("field_confidence") or {}

            cleaned: dict = {}
            low: dict = {}
            for k, v in fields.items():
                if v in (None, ""):
                    cleaned[k] = None
                    continue
                c = float(conf.get(k) or 0.0)
                if c >= MIN_CONF:
                    cleaned[k] = v
                else:
                    cleaned[k] = None
                    low[k] = {"value": v, "confidence": c}

            ground[pdf.name] = {
                "form_type": form_type if form_type != "Unknown" else expected_type,
                "expected_form_type": expected_type,
                "fields": cleaned,
                "extraction_source": data.get("extraction_source"),
                "status": "draft",
            }
            if low or form_type != expected_type:
                review.append(
                    {
                        "file": pdf.name,
                        "folder": folder,
                        "classified_as": form_type,
                        "expected": expected_type,
                        "low_confidence_fields": low,
                    }
                )
            filled = sum(1 for v in cleaned.values() if v not in (None, ""))
            print(f"  -> {form_type} kept={filled} review_fields={len(low)}")

    OUT_JSON.write_text(json.dumps(ground, indent=2), encoding="utf-8")
    OUT_REVIEW.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_REVIEW} ({len(review)} files need review)")
    print(
        "Next: manually fix null/wrong fields in ground_truth_draft.json, "
        "save as training/ground_truth.json, then run prepare_finetune_data.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
